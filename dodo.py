from pathlib import Path
import subprocess
import json
import shutil
import os

import doit.tools
from doit.tools import CmdAction

os.environ.update(
    NODE_OPTS="--max-old-space-size=4096",
    PYTHONIOENCODING="utf-8",
    PIP_DISABLE_PIP_VERSION_CHECK="1",
    MAMBA_NO_BANNER="1",
)

DOIT_CONFIG = {
    "backend": "sqlite3",
    "verbosity": 2,
    "par_type": "thread",
    "default_tasks": ["binder"],
}


def task_binder():
    """get ready to run on binder"""
    return dict(
        file_dep=[L.DEV_STATIC_PACKAGE, L.DEV_STATIC_LICENSES],
        actions=[
            lambda: [shutil.rmtree(P.APP_DIR) if P.APP_DIR.exists() else None, None][
                -1
            ],
            lambda: [P.APP_DIR.mkdir(parents=True), None][-1],
            lambda: [shutil.copytree(L.DEV_STATIC, P.APP_STATIC), None][-1],
        ],
        targets=[P.APP_STATIC / "package.json"],
    )


def task_env():
    yield dict(
        name="update",
        file_dep=[P.ENV_YAML],
        actions=[["mamba", "env", "update", "-p", P.ENV, "--file", P.ENV_YAML]],
        targets=[P.ENV_HISTORY],
    )


def task_setup():
    yield dict(
        name="yarn",
        file_dep=[P.ENV_HISTORY, *L.PACKAGES_JSON],
        actions=[CmdAction([*P.YARN, "--ignore-optional"], cwd=L.ROOT, shell=False)],
        targets=[L.YARN_INTEGRITY],
    )

    yield dict(
        name="pip:server",
        file_dep=[P.ENV_HISTORY],
        actions=[CmdAction(P.SETUP_E, cwd=S.ROOT, shell=False)],
    )

    yield dict(
        name="pip:lab",
        task_dep=["setup:pip:server", "setup:yarn"],
        file_dep=[P.ENV_HISTORY],
        actions=[CmdAction(P.SETUP_E, cwd=L.ROOT, shell=False)],
    )

    yield dict(
        name="pip:check",
        task_dep=["setup:pip:lab", "setup:pip:server"],
        actions=[[*P.PIP, "check"]],
    )


def task_lint():
    yield dict(
        name="js",
        task_dep=["setup:pip:lab"],
        file_dep=[L.YARN_INTEGRITY],
        actions=[CmdAction([*P.YARN, "lint"], cwd=L.ROOT, shell=False)],
        # targets=[???]
    )

    lint_py = [
        P.DODO,
        S.ROOT / "jupyterlab_server/licenses_handler.py",
        S.ROOT / "jupyterlab_server/licenses_app.py",
        S.ROOT / "jupyterlab_server/tests/test_licenses_api.py",
    ]

    yield dict(
        name="py",
        file_dep=[P.ENV_HISTORY, *lint_py],
        actions=[[*P.RUN_IN, "black", *lint_py], [*P.RUN_IN, "flake8", *lint_py]],
    )

    prettier = [P.HERE / "README.md"]

    yield dict(
        name="prettier",
        file_dep=[L.YARN_INTEGRITY],
        actions=[
            [
                *L.PRETTIER,
                "--write",
                "--prose-wrap=always",
                "--print-width=88",
                *prettier,
            ]
        ],
    )


def task_integrity():
    yield dict(
        name="buildutils",
        file_dep=L.ALL_BUILDUTILS,
        actions=[CmdAction([*P.YARN, "postinstall"], cwd=L.ROOT, shell=False)],
        targets=[L.BUILDUTILS_TSBUILDINFO, L.BUILDER_TSBULDINFO],
    )

    yield dict(
        name="repo",
        file_dep=[
            L.BUILDUTILS_TSBUILDINFO,
            L.BUILDER_TSBULDINFO,
            *L.ALL_TS_SRC,
            *L.PACKAGES_JSON,
        ],
        actions=[
            (doit.tools.create_folder, [L.BUILD]),
            lambda: [
                L.INTEGRITY_OK.unlink() if L.INTEGRITY_OK.exists() else None,
                None,
            ][-1],
            CmdAction(
                [*P.YARN, "node", "buildutils/lib/ensure-repo.js"],
                cwd=L.ROOT,
                shell=False,
            ),
            L.INTEGRITY_OK.touch,
        ],
        targets=[L.INTEGRITY_OK],
    )


def task_build():
    yield dict(
        name="lib",
        file_dep=[L.INTEGRITY_OK, L.YARN_INTEGRITY, *L.ALL_TS_SRC],
        actions=[CmdAction([*P.YARN, "build:packages"], cwd=L.ROOT, shell=False)],
        targets=[L.META_TSBUILDINFO],
    )

    yield dict(
        name="dev:prod",
        doc="do a prod build of dev_mode for licenses",
        file_dep=[
            *L.DEV_MODE.glob("*.js*"),
            L.BUILDUTILS_TSBUILDINFO,
            L.BUILDER_TSBULDINFO,
            L.META_TSBUILDINFO,
        ],
        actions=[
            CmdAction([*P.YARN], cwd=L.DEV_MODE, shell=False),
            CmdAction([*P.YARN, "build:prod"], cwd=L.DEV_MODE, shell=False),
        ],
        targets=[L.DEV_STATIC_PACKAGE, L.DEV_STATIC_LICENSES],
    )


def task_test():
    yield dict(
        name="server",
        task_dep=["setup:pip:check"],
        actions=[
            [
                *P.PYM,
                "pytest",
                "-x",
                "--ff",
                "--pyargs",
                "jupyterlab_server",
                "--cov",
                "jupyterlab_server",
                "--no-cov-on-fail",
                "--cov-report",
                "term-missing:skip-covered",
            ]
        ],
    )


def task_dev_mode():
    """run JupyterLab under dev_mode"""

    return dict(
        uptodate=[lambda: False],
        task_dep=["build:dev:prod"],
        actions=[_make_lab(["--dev-mode", "--ServerApp.base_url", "/dev-mode/"])],
    )


def task_dev_mode_watch():
    """run JupyterLab under dev_mode and watch sources"""

    return dict(
        uptodate=[lambda: False],
        task_dep=["build:dev:prod"],
        actions=[
            _make_lab(["--dev-mode", "--ServerApp.base_url", "/dev-mode/", "--watch"])
        ],
    )


def task_clean_all():
    """ensure every darned thing is cleaned"""
    yarn_path = Path(os.path.expanduser("~/.yarn"))

    return dict(
        uptodate=[lambda: False],
        actions=[
            CmdAction(["git", "clean", "-dxf"], cwd=str(L.ROOT), shell=False),
            CmdAction(["git", "clean", "-dxf"], cwd=str(S.ROOT), shell=False),
            lambda: [shutil.rmtree(yarn_path) if yarn_path.exists() else None, None][
                -1
            ],
            lambda: [shutil.rmtree(P.ENV) if P.ENV.exists() else None, None][-1],
        ],
    )


def task_patched_prod():
    """manually ensure the build in $PREFIX/share uses the up-to-date builder

    this doesn't actually quite work yet because of release stuff
    """

    tpl_json = P.APP_STATIC / "third-party-licenses.json"

    yield dict(
        name="builder:tgz",
        actions=[
            CmdAction([*P.NPM, "pack", "."], cwd=str(L.BUILDER), shell=False),
        ],
        file_dep=[L.BUILDER_TSBULDINFO],
        targets=[L.BUILDER_TGZ],
    )

    build_args = [*P.PYM, "jupyter", "lab", "build", "--debug", "--minimize=False"]

    yield dict(
        name="lab:clean",
        file_dep=[L.BUILDER_TGZ],
        actions=[
            lambda: [shutil.rmtree(P.APP_DIR) if P.APP_DIR.exists() else None, None][
                -1
            ],
            lambda: [subprocess.call(list(map(str, build_args))), None][-1],
        ],
        targets=[P.APP_STAGING / "package.json"],
    )

    yield dict(
        name="lab:build",
        actions=[
            CmdAction([*P.YARN, "cache", "clean"], cwd=str(P.APP_STAGING), shell=False),
            CmdAction(
                [*P.YARN, "add", "--dev", L.BUILDER_TGZ],
                cwd=str(P.APP_STAGING),
                shell=False,
            ),
            CmdAction([*P.YARN, "build:prod"], cwd=str(P.APP_STAGING), shell=False),
        ],
        file_dep=[L.BUILDER_TGZ, P.APP_STAGING / "package.json"],
        targets=[tpl_json],
    )

    yield dict(
        name="lab:run",
        uptodate=[lambda: False],
        file_dep=[tpl_json],
        actions=[_make_lab(["--ServerApp.base_url", "/patched-prod/"])],
    )


def _make_lab(extra_args=None):
    def lab():
        args = [*L.BASE_ARGS, *(extra_args or [])]
        proc = subprocess.Popen(list(map(str, args)), stdin=subprocess.PIPE)

        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            proc.communicate(b"y\n")

        proc.wait()
        return True

    return doit.tools.PythonInteractiveAction(lab)


class P:
    DODO = Path(__file__)
    HERE = DODO.parent
    BINDER = bool(json.loads(os.environ.get("LAB_LICENSES_BINDER", "0")))
    ENV_YAML = HERE / "environment.yml"
    ENV = HERE / ".env"
    ENV_HISTORY = ENV / "conda-meta/history"
    APP_DIR = ENV / "share/jupyter/lab"
    APP_STAGING = APP_DIR / "staging"
    APP_STATIC = APP_DIR / "static"
    if BINDER:
        RUN_IN = []
    else:
        RUN_IN = ["conda", "run", "--no-capture-output", "--prefix", ENV]
    PYM = [*RUN_IN, "python", "-m"]
    PIP = [*PYM, "pip"]
    SETUP_E = [*PIP, "install", "-e", ".", "-vvv", "--no-deps", "--ignore-installed"]
    YARN = [*RUN_IN, "yarn", "--silent"]
    NPM = [*RUN_IN, "npm"]


class L:
    ROOT = P.HERE / "jupyterlab"
    BASE_ARGS = [*P.PYM, "jupyter", "lab", "--debug", "--no-browser", "--autoreload"]
    NODE_MODULES = ROOT / "node_modules"
    YARN_INTEGRITY = NODE_MODULES / ".yarn-integrity"
    PRETTIER = [*P.RUN_IN, "node", NODE_MODULES / ".bin/prettier"]
    PACKAGES = ROOT / "packages"
    BUILD = ROOT / "build"
    BUILDER = ROOT / "builder"
    BUILDUTILS = ROOT / "buildutils"
    ALL_BUILDUTILS = [
        p
        for p in [
            *(BUILDER / "src").rglob("*.ts"),
            *BUILDER.glob("*.json"),
            *BUILDUTILS.glob("*.json"),
            *BUILDUTILS.rglob("src/**/*"),
            *BUILDUTILS.rglob("template/**/*"),
            YARN_INTEGRITY,
        ]
        if not p.is_dir()
    ]
    BUILDUTILS_TSBUILDINFO = BUILDUTILS / "tsconfig.tsbuildinfo"
    META = PACKAGES / "metapackage"
    META_TSBUILDINFO = META / "tsconfig.tsbuildinfo"
    BUILDER_TSBULDINFO = BUILDER / "tsconfig.tsbuildinfo"
    BUILDER_TGZ = BUILDER / "jupyterlab-builder-3.1.0-alpha.3.tgz"
    INTEGRITY_OK = BUILD / "repo.integrity.log"
    TESTUTILS = ROOT / "testutils"
    DEV_MODE = ROOT / "dev_mode"
    DEV_STATIC = DEV_MODE / "static"
    DEV_STATIC_PACKAGE = DEV_STATIC / "package.json"
    DEV_STATIC_LICENSES = DEV_STATIC / "third-party-licenses.json"
    ALL_TS_SRC = [*PACKAGES.rglob("*/src/**/*.ts*")]
    PACKAGES_JSON = [
        *PACKAGES.glob("*/package.json"),
        BUILDER / "package.json",
        ROOT / "package.json",
        TESTUTILS / "package.json",
    ]


class S:
    ROOT = P.HERE / "jupyterlab_server"
