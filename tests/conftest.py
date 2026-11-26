import json
from pathlib import Path

import pytest

from tests.helpers import run_command

SAMPLE_REPOSITORY = Path(__file__).resolve().parent / "fixtures"
INVALID_DIRECTORY = SAMPLE_REPOSITORY / "invalid"


@pytest.fixture
def sample_repository() -> Path:
    return SAMPLE_REPOSITORY


@pytest.fixture
def valid_directory(sample_repository: Path) -> Path:
    return sample_repository / "valid"


@pytest.fixture(
    params=sorted(
        path
        for path in INVALID_DIRECTORY.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ),
    ids=lambda path: str(path.relative_to(INVALID_DIRECTORY)),
)
def invalid_file(request: pytest.FixtureRequest) -> Path:
    return request.param


@pytest.fixture
def scan_findings(sample_repository: Path):
    def scan(*paths: Path) -> list[dict]:
        completed = run_command(
            [
                "ast-grep",
                "scan",
                "-c",
                str(sample_repository / "lint" / "sgconfig.yml"),
                "--json=stream",
                *[str(path) for path in paths],
            ],
            sample_repository,
        )
        return [json.loads(line) for line in completed.stdout.splitlines() if line]

    return scan
