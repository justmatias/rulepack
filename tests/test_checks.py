from pathlib import Path

import pytest

from tests.helpers import FIXTURES

VALID_DIRECTORY = FIXTURES / "valid"
INVALID_DIRECTORY = FIXTURES / "invalid"
INVALID_FILES = sorted(
    path
    for path in INVALID_DIRECTORY.rglob("*")
    if path.is_file() and "__pycache__" not in path.parts
)


def test_scan_reports_no_errors_when_fixtures_are_valid(scan_findings):
    findings = scan_findings(VALID_DIRECTORY)

    assert [finding for finding in findings if finding["severity"] == "error"] == []


@pytest.mark.parametrize(
    "invalid_file",
    INVALID_FILES,
    ids=lambda path: str(path.relative_to(INVALID_DIRECTORY)),
)
def test_scan_reports_findings_when_fixture_is_invalid(
    scan_findings, invalid_file: Path
):
    assert scan_findings(invalid_file) != []
