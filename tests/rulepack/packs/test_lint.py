import json
import shutil
from pathlib import Path

from rulepack.packs.sources import make_writable_and_retry
from tests.rulepack.packs.helpers import (
    publish_source,
    write_consumer_config,
    write_local_check,
    write_source,
)


def test_lint_fails_when_a_git_pack_check_finds_a_violation(locked_consumer, scan):
    exit_code, report = scan(locked_consumer)

    assert exit_code == 1
    assert [finding["rule"] for finding in report["scan"]["findings"]] == [
        "no-bare-except"
    ]


def test_lint_passes_when_the_pack_check_is_disabled(locked_consumer, scan):
    config = locked_consumer / ".rulepack.toml"
    config.write_text(
        config.read_text() + '\n[pack_overrides]\ndisable = ["no-bare-except"]\n'
    )

    exit_code, report = scan(locked_consumer)

    assert (exit_code, report["scan"]["findings"]) == (0, [])


def test_lint_runs_the_pack_rule_tests_when_a_pack_is_selected(locked_consumer, run_in):
    completed = run_in(locked_consumer, "lint", "--only", "test", "--json")

    report = json.loads(completed.stdout)
    assert completed.returncode == 0, completed.stderr
    assert report["test"] == {"ok": True, "skipped": None, "findings": []}


def test_lint_applies_severity_override_when_one_is_set(locked_consumer, scan):
    config = locked_consumer / ".rulepack.toml"
    config.write_text(
        config.read_text()
        + '\n[pack_overrides]\nseverity = { no-bare-except = "warning" }\n'
    )

    exit_code, report = scan(locked_consumer)

    assert exit_code == 0
    assert [finding["severity"] for finding in report["scan"]["findings"]] == [
        "warning"
    ]


def test_lint_uses_a_path_source_when_it_has_no_lock_entry(
    tmp_path: Path, source_work: Path, scan, bare_except_source: str
):
    repository = tmp_path / "local"
    repository.mkdir()
    (repository / "target.py").write_text(bare_except_source, encoding="utf-8")
    write_consumer_config(
        repository,
        f'packs = ["team/python-core"]\n\n[sources.team]\npath = "{source_work.as_posix()}"\n',
    )

    exit_code, report = scan(repository)

    assert exit_code == 1
    assert not (repository / "rulepack.lock").exists()
    assert report["scan"]["findings"][0]["rule"] == "no-bare-except"


def test_lint_fails_with_the_lock_message_when_the_lock_is_missing(
    consumer: Path, run_in
):
    completed = run_in(consumer, "lint", "--only", "scan")

    assert completed.returncode == 2
    assert "run `rulepack packs lock`" in completed.stderr
    assert not (consumer / "rulepack.lock").exists()


def test_lint_fails_with_the_lock_message_when_the_ref_changed(
    locked_consumer: Path, run_in
):
    lock = (locked_consumer / "rulepack.lock").read_text()
    config = locked_consumer / ".rulepack.toml"
    config.write_text(config.read_text().replace('ref = "main"', 'ref = "other"'))

    completed = run_in(locked_consumer, "lint", "--only", "scan")

    assert completed.returncode == 2
    assert "run `rulepack packs lock`" in completed.stderr
    assert (locked_consumer / "rulepack.lock").read_text() == lock


def test_lint_rejects_the_manifest_when_a_path_escapes_the_source(
    tmp_path: Path, source_work: Path, scan
):
    write_source(
        source_work, {"python-core": ["no-bare-except"]}, 'checks_dir = "../outside"\n'
    )
    repository = tmp_path / "local"
    repository.mkdir()
    write_consumer_config(
        repository,
        f'packs = ["team/python-core"]\n\n[sources.team]\npath = "{source_work.as_posix()}"\n',
    )

    exit_code, report = scan(repository)

    assert (exit_code, report) == (2, {})


def test_lint_names_both_sources_when_two_packs_define_the_same_check(
    tmp_path: Path, source_work: Path, run_in
):
    write_source(tmp_path / "other", {"errors": ["no-bare-except"]})
    repository = tmp_path / "local"
    repository.mkdir()
    write_consumer_config(
        repository,
        'packs = ["team/python-core", "other/errors"]\n\n'
        f'[sources.team]\npath = "{source_work.as_posix()}"\n\n'
        '[sources.other]\npath = "../other"\n',
    )

    completed = run_in(repository, "lint", "--only", "scan")

    assert completed.returncode == 2
    assert "'team/python-core'" in completed.stderr
    assert "'other/errors'" in completed.stderr


def test_lint_uses_the_repo_check_when_it_has_a_pack_check_id(
    locked_consumer: Path, run_in
):
    write_local_check(locked_consumer, "no-bare-except", "never_called()")

    completed = run_in(locked_consumer, "lint", "--only", "scan")

    assert completed.returncode == 0, completed.stderr
    assert "the repo's check no-bare-except replaces the pack check" in (
        completed.stderr
    )


def test_lint_ignores_host_packs_when_the_repo_has_a_config(
    tmp_path: Path, source_work: Path, run_in
):
    host = tmp_path / "config" / "rulepack"
    host.mkdir(parents=True)
    (host / "config.toml").write_text(
        f'packs = ["team/python-core"]\n\n[sources.team]\npath = "{source_work.as_posix()}"\n'
    )
    repository = tmp_path / "configured"
    repository.mkdir()
    write_consumer_config(repository, "[scan]\nexclude = []\n")

    completed = run_in(repository, "config", "--json")

    settings = json.loads(completed.stdout)["settings"]
    assert settings["packs"] == {"value": [], "source": "default"}


def test_lint_fetches_locked_commits_when_the_cache_is_cold(
    tmp_path: Path, locked_consumer: Path, cache_directory: Path, scan, run_in
):
    second = tmp_path / "second"
    write_source(second, {"errors": ["no-swallowed-exception"]})
    url = publish_source(second, tmp_path / "second.git")
    config = locked_consumer / ".rulepack.toml"
    config.write_text(
        config.read_text().replace(
            'packs = ["team/python-core"]',
            'packs = ["team/python-core", "second/errors"]',
        )
        + f'\n[sources.second]\ngit = "{url}"\nref = "main"\n'
    )
    assert scan(locked_consumer)[0] == 2
    assert run_in(locked_consumer, "packs", "lock").returncode == 0
    shutil.rmtree(cache_directory, onexc=make_writable_and_retry)

    exit_code, report = scan(locked_consumer)

    assert exit_code == 1
    assert {finding["rule"] for finding in report["scan"]["findings"]} == {
        "no-bare-except"
    }
    assert len(list(cache_directory.iterdir())) == 2
