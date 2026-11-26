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
