import subprocess
import sys
from pathlib import Path

import pytest


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
