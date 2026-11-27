import subprocess
import sys
from pathlib import Path

import pytest

from rulepack.init.command import main as run_init_command
from tests.rulepack.init.helpers import TerminalInput


@pytest.fixture
def run_init(git_repository: Path):
    def run(*arguments: str, answer: str = "") -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "rulepack", "init", *arguments],
            cwd=git_repository,
            input=answer,
            capture_output=True,
            text=True,
            check=False,
        )

    return run


@pytest.fixture
def run_init_in_terminal(git_repository: Path, monkeypatch: pytest.MonkeyPatch):
    """Runs init in-process, with `answers` typed into a stdin that is a terminal."""
    monkeypatch.chdir(git_repository)

    def run(*arguments: str, answers: str) -> int:
        monkeypatch.setattr(sys, "stdin", TerminalInput(answers))
        return run_init_command(list(arguments))

    return run
