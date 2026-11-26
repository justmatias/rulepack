from pathlib import Path

import pytest


@pytest.fixture
def exception_file(tmp_path: Path):
    def write(header: str) -> Path:
        path = tmp_path / "module.py"
        path.write_text(
            f"{header}# ast-grep-ignore: no-manual-init-boilerplate\n"
            "class Foo:\n    def __init__(self, name):\n        self.name = name\n"
        )
        return path

    return write


@pytest.fixture
def shell_exception_file(tmp_path: Path):
    def write(header: str) -> Path:
        path = tmp_path / "task.sh"
        path.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            f'{header}# ast-grep-ignore: no-eval\neval "$1"\n',
            encoding="utf-8",
        )
        return path

    return write


@pytest.fixture
def commit_message(git_repository: Path, run_rulepack):
    """Run rulepack commit-msg on a message, inside a repo with its own config."""

    def check(message: str):
        path = git_repository / "COMMIT_EDITMSG"
        path.write_text(message, encoding="utf-8")
        return run_rulepack("commit-msg", str(path), working_directory=git_repository)

    return check
