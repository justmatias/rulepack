import sys
from pathlib import Path

import pytest

from tests.helpers import REPOSITORY_ROOT, run_command
from tests.rulepack.helpers import git


@pytest.fixture
def run_rulepack():
    def run(command: str, *arguments: str, working_directory: Path = REPOSITORY_ROOT):
        return run_command(
            [sys.executable, "-m", "rulepack", command, *arguments], working_directory
        )

    return run


@pytest.fixture
def git_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    (repository / ".git").mkdir(parents=True)
    return repository


@pytest.fixture
def write_config(git_repository: Path):
    def write(content: str, name: str = ".rulepack.toml") -> Path:
        path = git_repository / name
        path.write_text(content, encoding="utf-8")
        return path

    return write


@pytest.fixture
def commit():
    def run(repository: Path, message: str = "change") -> None:
        git(repository, "add", "--all")
        git(repository, "commit", "--quiet", "-m", message)

    return run
