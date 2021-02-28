import os
from pathlib import Path
import subprocess
import json

import doit.tools

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
    return dict(task_dep=["setup"], actions=[["echo", "ready to start lab!"]])


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
        actions=[
            doit.tools.CmdAction(
                [*P.YARN, "--ignore-optional"], cwd=L.ROOT, shell=False
            )
        ],
        targets=[L.YARN_INTEGRITY],
    )

    yield dict(
        name="pip:server",
        file_dep=[P.ENV_HISTORY],
        actions=[doit.tools.CmdAction(P.SETUP_E, cwd=S.ROOT, shell=False)],
    )

    yield dict(
        name="pip:lab",
        task_dep=["setup:pip:server", "setup:yarn"],
        file_dep=[P.ENV_HISTORY],
        actions=[doit.tools.CmdAction(P.SETUP_E, cwd=L.ROOT, shell=False)],
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
        actions=[doit.tools.CmdAction([*P.YARN, "lint"], cwd=L.ROOT, shell=False)],
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


def task_build():
    yield dict(
        name="lib",
        task_dep=["lint:js"],
        file_dep=[L.YARN_INTEGRITY],
        actions=[doit.tools.CmdAction([*P.YARN, "build"], cwd=L.ROOT, shell=False)],
        # targets=[???]
    )

    yield dict(
        name="core",
        task_dep=["build:lib"],
        actions=[
            doit.tools.CmdAction([*P.YARN, "build:core"], cwd=L.ROOT, shell=False)
        ],
        # targets=[???]
    )

    yield dict(
        name="dev:prod",
        task_dep=["build:core"],
        actions=[
            doit.tools.CmdAction([*P.YARN, "build:prod"], cwd=L.DEV_MODE, shell=False)
        ],
        # targets=[???]
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
    if BINDER:
        RUN_IN = []
    else:
        RUN_IN = ["conda", "run", "--no-capture-output", "--prefix", ENV]
    PYM = [*RUN_IN, "python", "-m"]
    PIP = [*PYM, "pip"]
    SETUP_E = [*PIP, "install", "-e", ".", "-vvv", "--no-deps", "--ignore-installed"]
    YARN = [*RUN_IN, "yarn"]


class L:
    ROOT = P.HERE / "jupyterlab"
    BASE_ARGS = [*P.PYM, "jupyter", "lab", "--debug", "--no-browser", "--autoreload"]
    YARN_INTEGRITY = ROOT / "node_modules/.yarn-integrity"
    PACKAGES = ROOT / "packages"
    BUILDER = ROOT / "builder"
    TESTUTILS = ROOT / "testutils"
    DEV_MODE = ROOT / "dev_mode"
    PACKAGES_JSON = [
        *PACKAGES.glob("*/package.json"),
        BUILDER / "package.json",
        ROOT / "package.json",
        TESTUTILS / "package.json",
    ]


class S:
    ROOT = P.HERE / "jupyterlab_server"
