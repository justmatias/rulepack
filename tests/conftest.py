import json
from pathlib import Path

import pytest

from tests.helpers import FIXTURES, REPOSITORY_ROOT, run_command

SGCONFIG = FIXTURES / "lint" / "sgconfig.yml"


@pytest.fixture
def scan_findings():
    def scan(*paths: Path) -> list[dict]:
        completed = run_command(
            [
                "ast-grep",
                "scan",
                "-c",
                str(SGCONFIG),
                "--json=stream",
                *[str(path) for path in paths],
            ],
            REPOSITORY_ROOT,
        )
        return [json.loads(line) for line in completed.stdout.splitlines() if line]

    return scan
