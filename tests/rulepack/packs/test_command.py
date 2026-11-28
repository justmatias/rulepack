import json
import shutil
from pathlib import Path

import pytest

from rulepack.packs import fetch
from tests.rulepack.packs.helpers import read_head_commit, write_source


def test_lock_pins_the_branch_head_when_a_git_source_is_declared(
    lock_text: str, source_work: Path
):
    assert f'commit = "{read_head_commit(source_work)}"' in lock_text
    assert 'ref = "main"' in lock_text


def test_lock_leaves_the_file_unchanged_when_run_twice(
    locked_consumer: Path, lock_text: str, run_in
):
    completed = run_in(locked_consumer, "packs", "lock")

    assert completed.returncode == 0, completed.stderr
    assert (locked_consumer / "rulepack.lock").read_text() == lock_text


@pytest.mark.usefixtures("_push_new_source_commit")
def test_lock_keeps_the_pin_when_the_branch_moves(
    locked_consumer: Path, lock_text: str, run_in
):
    completed = run_in(locked_consumer, "packs", "lock")

    assert completed.returncode == 0, completed.stderr
    assert (locked_consumer / "rulepack.lock").read_text() == lock_text


@pytest.mark.usefixtures("_push_new_source_commit")
def test_update_moves_the_pin_when_the_branch_has_a_new_commit(
    locked_consumer: Path, source_work: Path, run_in
):
    completed = run_in(locked_consumer, "packs", "update")

    assert completed.returncode == 0, completed.stderr
    assert (
        f'commit = "{read_head_commit(source_work)}"'
        in (locked_consumer / "rulepack.lock").read_text()
    )


def test_update_fails_when_the_named_source_is_not_a_git_source(
    locked_consumer: Path, run_in
):
    completed = run_in(locked_consumer, "packs", "update", "other")

    assert completed.returncode == 2
    assert "no git source named other" in completed.stderr


def test_update_skips_path_sources_when_no_source_is_named(
    locked_consumer: Path, source_work: Path, run_in
):
    config = locked_consumer / ".rulepack.toml"
    config.write_text(
        config.read_text() + f'\n[sources.local]\npath = "{source_work.as_posix()}"\n'
    )

    completed = run_in(locked_consumer, "packs", "update")

    assert completed.returncode == 0, completed.stderr
    assert "[sources.local]" not in (locked_consumer / "rulepack.lock").read_text()


def test_list_reports_packs_and_the_locked_commit_when_asked_for_json(
    locked_consumer: Path, source_work: Path, run_in
):
    completed = run_in(locked_consumer, "packs", "list", "--json")

    team = json.loads(completed.stdout)["team"]
    assert team["commit"] == read_head_commit(source_work)
    assert team["packs"] == {"python-core": ["no-bare-except"]}


def test_list_fails_with_the_lock_message_when_the_source_is_not_locked(
    consumer: Path, run_in
):
    completed = run_in(consumer, "packs", "list")

    assert completed.returncode == 2
    assert "run `rulepack packs lock`" in completed.stderr


def test_list_fetches_the_locked_commit_when_the_cache_is_cold(
    locked_consumer: Path, cache_directory: Path, run_in
):
    shutil.rmtree(cache_directory, onexc=fetch.retry_after_making_writable)

    completed = run_in(locked_consumer, "packs", "list", "--json")

    assert completed.returncode == 0, completed.stderr
    assert "python-core" in json.loads(completed.stdout)["team"]["packs"]


def test_list_reads_a_path_source_when_it_has_no_lock_entry(
    path_consumer: Path, run_in
):
    completed = run_in(path_consumer, "packs", "list", "--json")

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["team"]["commit"] is None
    assert not (path_consumer / "rulepack.lock").exists()


def test_list_rejects_the_manifest_when_a_path_escapes_the_source(
    path_consumer: Path, source_work: Path, run_in
):
    write_source(
        source_work, {"python-core": ["no-bare-except"]}, 'checks_dir = "../outside"\n'
    )

    completed = run_in(path_consumer, "packs", "list")

    assert completed.returncode == 2
    assert "checks_dir escapes the source" in completed.stderr


def test_fetch_clone_keeps_the_other_clone_when_a_parallel_run_finished_first(
    source_url: str, monkeypatch: pytest.MonkeyPatch
):
    clone_path = fetch.locate_cache_directory(source_url) / "clone.git"
    run_git = fetch.run_git

    def clone_while_another_run_clones(*arguments: str, cwd: Path | None = None):
        if arguments[0] == "clone":
            run_git(*arguments[:-1], str(clone_path))
        return run_git(*arguments, cwd=cwd)

    monkeypatch.setattr(fetch, "run_git", clone_while_another_run_clones)

    clone = fetch.fetch_clone(source_url)

    assert clone == clone_path
    assert [path.name for path in clone.parent.iterdir()] == ["clone.git"]
