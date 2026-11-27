import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.rulepack.hook.helpers import BARE_EXCEPT


@pytest.fixture
def _isolate_temp_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(name, str(tmp_path))


# The hook keeps its stop marker in the temp directory, so isolate that first.
@pytest.fixture
def run_hook(
    _isolate_temp_directory: None,  # pylint: disable=unused-argument
    tmp_path: Path,
):
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
def violating_target(lint_sandbox: Path) -> Path:
    target = lint_sandbox / "target.py"
    target.write_text(BARE_EXCEPT, encoding="utf-8")
    return target


@pytest.fixture(params=["  *** Add File: target.py", "*** Add File: target.py  "])
def padded_add_header(request: pytest.FixtureRequest) -> str:
    return request.param
