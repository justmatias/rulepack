from pathlib import Path


def test_scan_reports_no_errors_when_fixtures_are_valid(
    scan_findings, valid_directory: Path
):
    findings = scan_findings(valid_directory)

    assert [finding for finding in findings if finding["severity"] == "error"] == []


def test_scan_reports_findings_when_fixture_is_invalid(
    scan_findings, invalid_file: Path
):
    assert scan_findings(invalid_file) != []
