import json
import shutil
from pathlib import Path

import pytest

from tests.rulepack.lint.helpers import git, init_git_repository


@pytest.fixture
def commit():
    def run(repository: Path, message: str = "change") -> None:
        git(repository, "add", "--all")
        git(repository, "commit", "--quiet", "-m", message)

    return run


@pytest.fixture
def feature_repository(tmp_path: Path) -> Path:
    """A real git repo with a.py, b.py and notes.txt on main, checked out on feature."""
    repository = tmp_path / "feature"
    repository.mkdir()
    for name in ("a.py", "b.py", "notes.txt"):
        (repository / name).write_text("x = 1\n", encoding="utf-8")
    init_git_repository(repository)
    git(repository, "checkout", "--quiet", "-b", "feature")
    return repository


@pytest.fixture
def lint_sandbox(sample_repository: Path, tmp_path: Path) -> Path:
    """A committed git repo with the sample checks, fixtures and config."""
    sandbox = tmp_path / "sandbox"
    shutil.copytree(
        sample_repository, sandbox, ignore=shutil.ignore_patterns("__pycache__")
    )
    return init_git_repository(sandbox)


@pytest.fixture
def bare_except_file(sample_repository: Path) -> Path:
    return sample_repository / "invalid" / "error-handling" / "bare_except.py"


@pytest.fixture
def manual_init_file(sample_repository: Path) -> Path:
    """Breaks no-manual-init-boilerplate, a warning the full scan tolerates."""
    return sample_repository / "invalid" / "python-models" / "manual_init.py"


@pytest.fixture
def run_lint(run_rulepack, lint_sandbox: Path):
    def run(*arguments: str) -> tuple[int, dict]:
        completed = run_rulepack(
            "lint", "--json", *arguments, working_directory=lint_sandbox
        )
        return completed.returncode, json.loads(completed.stdout)

    return run


@pytest.fixture
def import_contract(lint_sandbox: Path):
    """A package whose core imports its adapters, and a contract forbidding it."""

    def write(core_imports_adapters: bool) -> None:
        package = lint_sandbox / "app"
        (package / "core").mkdir(parents=True)
        (package / "adapters").mkdir()
        for init in (package, package / "core", package / "adapters"):
            (init / "__init__.py").write_text("", encoding="utf-8")
        source = "from app.adapters import store\n" if core_imports_adapters else ""
        (package / "core" / "logic.py").write_text(source, encoding="utf-8")
        (package / "adapters" / "store.py").write_text("", encoding="utf-8")
        (lint_sandbox / ".importlinter").write_text(
            "[importlinter]\nroot_package = app\n\n"
            "[importlinter:contract:core-is-pure]\nname = core-is-pure\n"
            "type = forbidden\nsource_modules = app.core\n"
            "forbidden_modules = app.adapters\n",
            encoding="utf-8",
        )

    return write
