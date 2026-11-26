import sys
from pathlib import Path

import pytest

from tests.helpers import run_command


@pytest.fixture
def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def run_rulepack(repository_root: Path):
    def run(command: str, *arguments: str, working_directory: Path = repository_root):
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
def _write_sgconfig_config(write_config) -> None:
    write_config('sgconfig = "checks/sgconfig.yml"\n')


@pytest.fixture
def _change_to_git_repository(git_repository: Path, monkeypatch) -> None:
    monkeypatch.chdir(git_repository)
