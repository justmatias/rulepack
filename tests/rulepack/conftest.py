import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers import run_command
from tests.rulepack.helpers import init_git_repository, run_git


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
def commit():
    def run(repository: Path, message: str = "change") -> None:
        run_git(repository, "add", "--all")
        run_git(repository, "commit", "--quiet", "-m", message)

    return run


@pytest.fixture
def lint_sandbox(sample_repository: Path, tmp_path: Path) -> Path:
    """A committed git repo with the sample checks, fixtures and config."""
    sandbox = tmp_path / "sandbox"
    shutil.copytree(
        sample_repository, sandbox, ignore=shutil.ignore_patterns("__pycache__")
    )
    return init_git_repository(sandbox)


@pytest.fixture
def _isolate_temp_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(name, str(tmp_path))


@pytest.fixture
def run_hook(tmp_path: Path):
    def run(repository: Path, event: str, **payload: object):
        return subprocess.run(
            [sys.executable, "-m", "rulepack", "hook", event],
            cwd=tmp_path,
            input=json.dumps({"cwd": str(repository), **payload}),
            capture_output=True,
            text=True,
            check=False,
        )

    return run


@pytest.fixture
def bare_except_source() -> str:
    return "try:\n    value = 1\nexcept:\n    raise\n"
