import os
from pathlib import Path
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
    return dict(
        actions=[
            ["echo", "ok"]
        ]
    )

def task_env():
    yield dict(
        name="update",
        file_dep=[P.ENV_YAML],
        actions=[["mamba", "env", "update", "-p", P.ENV, "--file", P.ENV_YAML]],
        targets=[P.ENV_HISTORY]
    )

def task_setup():
    yield dict(
        file_dep=[P.ENV_HISTORY],
        name="server",
        actions=[
            doit.tools.CmdAction(P.SETUP_E, cwd=S.ROOT, shell=False)
        ]
    )

    yield dict(
        task_dep=["setup:server"],
        file_dep=[P.ENV_HISTORY],
        name="lab",
        actions=[
            doit.tools.CmdAction(P.SETUP_E, cwd=L.ROOT, shell=False)
        ]
    )

    yield dict(
        name="check",
        task_dep=["setup:lab", "setup:server"],
        actions=[[*P.PIP, "check"]]
    )


class P:
    DODO = Path(__file__)
    HERE = DODO.parent
    ENV_YAML = HERE / "environment.yml"
    ENV = HERE / ".env"
    ENV_HISTORY = ENV / "conda-meta/history"
    RUN_IN = ["conda", "run", "--no-capture-output", "--prefix", ENV]
    PYM = [*RUN_IN, "python", "-m"]
    PIP = [*PYM, "pip"]
    SETUP_E =  [*PIP, "install", "-e", ".", "--no-deps", "--ignore-installed"]

class L:
    ROOT = P.HERE / "jupyterlab"

class S:
    ROOT = P.HERE / "jupyterlab_server"
