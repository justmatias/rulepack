import json
import shutil
from pathlib import Path

import pytest

from rulepack.packs import fetch
from tests.rulepack.packs.helpers import publish_source, write_source


def test_lint_fails_when_a_git_pack_check_finds_a_violation(locked_consumer, scan):
    exit_code, report = scan(locked_consumer)

    assert exit_code == 1
    assert [finding["rule"] for finding in report["scan"]["findings"]] == [
        "no-bare-except"
    ]


def test_lint_passes_when_the_pack_check_is_disabled(
    locked_consumer, append_config, scan
):
    append_config('\n[pack_overrides]\ndisable = ["no-bare-except"]\n')

    exit_code, report = scan(locked_consumer)

    assert (exit_code, report["scan"]["findings"]) == (0, [])


def test_lint_applies_the_severity_override_when_one_is_set(
    locked_consumer, append_config, scan
):
    append_config('\n[pack_overrides]\nseverity = { no-bare-except = "warning" }\n')

    exit_code, report = scan(locked_consumer)

    assert exit_code == 0
    assert [finding["severity"] for finding in report["scan"]["findings"]] == [
        "warning"
    ]


def test_lint_fails_when_an_override_names_an_unknown_check(
    locked_consumer, append_config, run_in
):
    append_config('\n[pack_overrides]\ndisable = ["no-such-check"]\n')

    completed = run_in(locked_consumer, "lint", "--only", "scan")

    assert completed.returncode == 2
    assert "unknown checks: no-such-check" in completed.stderr


def test_lint_runs_the_pack_rule_tests_when_a_pack_is_selected(locked_consumer, run_in):
    completed = run_in(locked_consumer, "lint", "--only", "test", "--json")

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["test"] == {
        "ok": True,
        "skipped": None,
        "findings": [],
    }


def test_lint_scans_with_a_path_source_when_the_folder_is_not_a_git_repo(
    path_consumer: Path, scan
):
    exit_code, report = scan(path_consumer)

    assert exit_code == 1
    assert report["scan"]["findings"][0]["rule"] == "no-bare-except"
    assert not (path_consumer / "rulepack.lock").exists()


def test_lint_fails_with_the_lock_message_when_the_lock_is_missing(
    consumer: Path, run_in
):
    completed = run_in(consumer, "lint", "--only", "scan")

    assert completed.returncode == 2
    assert "run `rulepack packs lock`" in completed.stderr
    assert not (consumer / "rulepack.lock").exists()


def test_lint_fails_with_the_lock_message_when_the_ref_changed(
    locked_consumer: Path, lock_text: str, run_in
):
    config = locked_consumer / ".rulepack.toml"
    config.write_text(config.read_text().replace('ref = "main"', 'ref = "other"'))

    completed = run_in(locked_consumer, "lint", "--only", "scan")

    assert completed.returncode == 2
    assert "run `rulepack packs lock`" in completed.stderr
    assert (locked_consumer / "rulepack.lock").read_text() == lock_text


def test_lint_fails_when_a_selected_pack_is_not_in_the_source(
    locked_consumer: Path, run_in
):
    config = locked_consumer / ".rulepack.toml"
    config.write_text(config.read_text().replace("team/python-core", "team/missing"))

    completed = run_in(locked_consumer, "lint", "--only", "scan")

    assert completed.returncode == 2
    assert "source 'team' has no pack 'missing'" in completed.stderr


def test_lint_names_both_packs_when_two_packs_define_the_same_check(
    tmp_path: Path, path_consumer: Path, run_in
):
    write_source(tmp_path / "other", {"errors": ["no-bare-except"]})
    config = path_consumer / ".rulepack.toml"
    config.write_text(
        config.read_text().replace(
            '"team/python-core"', '"team/python-core", "other/errors"'
        )
        + '\n[sources.other]\npath = "../other"\n'
    )

    completed = run_in(path_consumer, "lint", "--only", "scan")

    assert completed.returncode == 2
    assert "'team/python-core'" in completed.stderr
    assert "'other/errors'" in completed.stderr


@pytest.mark.usefixtures("_write_local_check_with_pack_id")
def test_lint_uses_the_repo_check_when_it_has_a_pack_check_id(
    locked_consumer: Path, run_in
):
    completed = run_in(locked_consumer, "lint", "--only", "scan")

    assert completed.returncode == 0, completed.stderr
    assert "the repo's check no-bare-except replaces the pack check" in (
        completed.stderr
    )


def test_lint_fetches_the_locked_commits_when_the_cache_is_cold(
    tmp_path: Path, locked_consumer: Path, cache_directory: Path, run_in, scan
):
    second = tmp_path / "second"
    write_source(second, {"errors": ["no-swallowed-exception"]})
    url = publish_source(second, tmp_path / "second.git")
    config = locked_consumer / ".rulepack.toml"
    config.write_text(
        config.read_text().replace(
            '"team/python-core"', '"team/python-core", "second/errors"'
        )
        + f'\n[sources.second]\ngit = "{url}"\nref = "main"\n'
    )
    assert run_in(locked_consumer, "packs", "lock").returncode == 0
    shutil.rmtree(cache_directory, onexc=fetch.retry_after_making_writable)

    exit_code, report = scan(locked_consumer)

    assert exit_code == 1
    assert {finding["rule"] for finding in report["scan"]["findings"]} == {
        "no-bare-except"
    }
    assert len(list(cache_directory.iterdir())) == 2


def test_lint_scans_changed_files_with_pack_checks_when_asked_for_changes(
    locked_consumer: Path, scan
):
    (locked_consumer / "added.py").write_text(
        (locked_consumer / "target.py").read_text()
    )

    exit_code, report = scan(locked_consumer, "--changed", "--base-ref", "HEAD")

    assert exit_code == 1
    assert {finding["file"] for finding in report["scan"]["findings"]} == {"added.py"}


def test_lint_fails_when_the_configured_sgconfig_is_missing_and_packs_are_selected(
    locked_consumer: Path, run_in
):
    config = locked_consumer / ".rulepack.toml"
    config.write_text('sgconfig = "checks/sgconfig.yml"\n' + config.read_text())

    completed = run_in(locked_consumer, "lint", "--only", "scan")

    assert completed.returncode == 2
    assert "no ast-grep config at" in completed.stderr
