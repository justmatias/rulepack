import json
import shutil
import sys
import sysconfig
from pathlib import Path

from rulepack.lint.command import STEPS, find_tool
from tests.rulepack.lint.helpers import run_git


def test_lint_passes_when_repository_is_clean(run_lint):
    exit_code, report = run_lint()

    assert exit_code == 0, report
    assert list(report) == list(STEPS)
    assert all(step["ok"] for step in report.values())


def test_json_reports_ok_skipped_and_findings_when_lint_runs(run_lint):
    _, report = run_lint()

    assert {tuple(sorted(step)) for step in report.values()} == {
        ("findings", "ok", "skipped")
    }


def test_scan_fails_when_file_is_invalid(
    run_lint, lint_sandbox: Path, bare_except_file: Path
):
    shutil.copy(bare_except_file, lint_sandbox / "valid" / "zz_scan_target.py")

    exit_code, report = run_lint()

    assert exit_code == 1
    assert not report["scan"]["ok"]
    assert {finding["rule"] for finding in report["scan"]["findings"]} == {
        "no-bare-except"
    }
    assert all(report[step]["ok"] for step in STEPS if step != "scan")


def test_changed_fails_when_file_has_a_warning_the_full_scan_tolerates(
    run_lint, lint_sandbox: Path, manual_init_file: Path
):
    run_git(lint_sandbox, "checkout", "--quiet", "-b", "feature")
    shutil.copy(manual_init_file, lint_sandbox / "valid" / "models.py")

    full_exit_code, full = run_lint("--only", "scan")
    changed_exit_code, changed = run_lint("--only", "scan", "--changed")

    assert (full_exit_code, full["scan"]["ok"]) == (0, True)
    assert (changed_exit_code, changed["scan"]["ok"]) == (1, False)


def test_changed_skips_scan_when_nothing_changed(run_lint):
    _, report = run_lint("--only", "scan", "--changed", "--base-ref", "main")

    assert report["scan"]["skipped"] == "no changed files to scan"


def test_files_skips_scan_when_extension_is_not_scanned(run_lint, lint_sandbox: Path):
    (lint_sandbox / "notes.md").write_text("# Notes\n", encoding="utf-8")

    _, report = run_lint("--only", "scan", "--files", "notes.md")

    assert report["scan"]["skipped"] == "no changed files to scan"


def test_files_scan_fails_when_file_has_a_warning(
    run_lint, lint_sandbox: Path, manual_init_file: Path
):
    shutil.copy(manual_init_file, lint_sandbox / "models.py")

    exit_code, report = run_lint("--only", "scan", "--files", "models.py")

    assert exit_code == 1
    assert {finding["rule"] for finding in report["scan"]["findings"]} == {
        "no-manual-init-boilerplate"
    }


def test_lint_runs_given_steps_when_only_is_set(run_lint):
    _, report = run_lint("--only", "scan", "imports")

    assert list(report) == ["scan", "imports"]


def test_lint_leaves_out_given_steps_when_skip_is_set(run_lint):
    _, report = run_lint("--skip", "test", "scan")

    assert list(report) == ["imports"]


def test_imports_is_skipped_when_importlinter_is_missing(run_lint, lint_sandbox: Path):
    (lint_sandbox / ".importlinter").unlink(missing_ok=True)

    _, report = run_lint("--only", "imports")

    assert report["imports"] == {
        "ok": True,
        "skipped": "no .importlinter",
        "findings": [],
    }


def test_imports_passes_when_the_contract_is_kept(run_lint, write_import_contract):
    write_import_contract(core_imports_adapters=False)

    exit_code, report = run_lint("--only", "imports")

    assert exit_code == 0, report


def test_imports_fails_when_the_contract_is_broken(run_lint, write_import_contract):
    write_import_contract(core_imports_adapters=True)

    exit_code, report = run_lint("--only", "imports")

    assert exit_code == 1
    assert any("core-is-pure BROKEN" in line for line in report["imports"]["findings"])


def test_lint_fails_when_base_ref_is_given_without_changed(
    run_rulepack, lint_sandbox: Path
):
    completed = run_rulepack(
        "lint", "--base-ref", "main", working_directory=lint_sandbox
    )

    assert completed.returncode == 2
    assert "need --changed" in completed.stderr


def test_find_tool_returns_bundled_ast_grep_when_it_is_installed():
    resolved = Path(find_tool("ast-grep")).parent

    assert resolved in {
        Path(sysconfig.get_path("scripts")),
        Path(sys.executable).parent,
    }


def test_ast_grep_steps_are_skipped_when_repo_has_no_local_checks(
    run_rulepack, git_repository: Path
):
    completed = run_rulepack(
        "lint", "--json", "--only", "test", "scan", working_directory=git_repository
    )

    assert completed.returncode == 0, completed.stderr
    skipped = {step["skipped"] for step in json.loads(completed.stdout).values()}
    assert skipped == {"no local checks at lint/sgconfig.yml"}


def test_lint_fails_when_configured_sgconfig_is_missing(
    run_rulepack, git_repository: Path, write_config
):
    write_config('sgconfig = "checks/sgconfig.yml"\n')

    completed = run_rulepack(
        "lint", "--json", "--only", "scan", working_directory=git_repository
    )

    assert completed.returncode == 1
    assert "no ast-grep config" in completed.stdout
