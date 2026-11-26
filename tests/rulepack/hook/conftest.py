import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def run_hook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("TEMP", str(tmp_path))
    monkeypatch.setenv("TMP", str(tmp_path))

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
