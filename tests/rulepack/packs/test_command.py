import json
import shutil
import tomllib
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
    locked_consumer: Path, lock_text: str, run_rulepack
):
    completed = run_rulepack("packs", "lock", working_directory=locked_consumer)

    assert completed.returncode == 0, completed.stderr
    assert (locked_consumer / "rulepack.lock").read_text() == lock_text


@pytest.mark.usefixtures("_push_new_source_commit")
def test_lock_keeps_the_pin_when_the_branch_moves(
    locked_consumer: Path, lock_text: str, run_rulepack
):
    completed = run_rulepack("packs", "lock", working_directory=locked_consumer)

    assert completed.returncode == 0, completed.stderr
    assert (locked_consumer / "rulepack.lock").read_text() == lock_text


@pytest.mark.usefixtures("_push_new_source_commit")
def test_update_moves_the_pin_when_the_branch_has_a_new_commit(
    locked_consumer: Path, source_work: Path, run_rulepack
):
    completed = run_rulepack("packs", "update", working_directory=locked_consumer)

    assert completed.returncode == 0, completed.stderr
    assert (
        f'commit = "{read_head_commit(source_work)}"'
        in (locked_consumer / "rulepack.lock").read_text()
    )


def test_update_fails_when_the_named_source_is_not_a_git_source(
    locked_consumer: Path, run_rulepack
):
    completed = run_rulepack(
        "packs", "update", "other", working_directory=locked_consumer
    )

    assert completed.returncode == 2
    assert "no git source named other" in completed.stderr


def test_update_skips_path_sources_when_no_source_is_named(
    locked_consumer: Path, source_work: Path, run_rulepack
):
    config = locked_consumer / ".rulepack.toml"
    config.write_text(
        config.read_text() + f'\n[sources.local]\npath = "{source_work.as_posix()}"\n'
    )

    completed = run_rulepack("packs", "update", working_directory=locked_consumer)

    assert completed.returncode == 0, completed.stderr
    assert "[sources.local]" not in (locked_consumer / "rulepack.lock").read_text()


def test_list_reports_packs_and_the_locked_commit_when_asked_for_json(
    locked_consumer: Path, source_work: Path, run_rulepack
):
    completed = run_rulepack(
        "packs", "list", "--json", working_directory=locked_consumer
    )

    team = json.loads(completed.stdout)["team"]
    assert team["commit"] == read_head_commit(source_work)
    assert team["packs"] == {"python-core": ["no-bare-except"]}


def test_list_fails_with_the_lock_message_when_the_source_is_not_locked(
    consumer: Path, run_rulepack
):
    completed = run_rulepack("packs", "list", working_directory=consumer)

    assert completed.returncode == 2
    assert "run `rulepack packs lock`" in completed.stderr


def test_list_fails_with_the_lock_message_when_the_ref_changed_since_locking(
    locked_consumer: Path, run_rulepack
):
    config = locked_consumer / ".rulepack.toml"
    config.write_text(config.read_text().replace('ref = "main"', 'ref = "v2"'))

    completed = run_rulepack("packs", "list", working_directory=locked_consumer)

    assert completed.returncode == 2
    assert "changed since it was locked" in completed.stderr
    assert "run `rulepack packs lock`" in completed.stderr


@pytest.mark.usefixtures("_remove_cached_source")
def test_list_fetches_the_locked_commit_when_the_cache_is_cold(
    locked_consumer: Path, run_rulepack
):

    completed = run_rulepack(
        "packs", "list", "--json", working_directory=locked_consumer
    )

    assert completed.returncode == 0, completed.stderr
    assert "python-core" in json.loads(completed.stdout)["team"]["packs"]


def test_list_reads_a_path_source_when_it_has_no_lock_entry(
    path_consumer: Path, run_rulepack
):
    completed = run_rulepack("packs", "list", "--json", working_directory=path_consumer)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["team"]["commit"] is None
    assert not (path_consumer / "rulepack.lock").exists()


def test_list_rejects_the_manifest_when_a_path_escapes_the_source(
    path_consumer: Path, source_work: Path, run_rulepack
):
    write_source(
        source_work, {"python-core": ["no-bare-except"]}, 'checks_dir = "../outside"\n'
    )

    completed = run_rulepack("packs", "list", working_directory=path_consumer)

    assert completed.returncode == 2
    assert "checks_dir escapes the source" in completed.stderr


def test_fetch_clone_keeps_the_other_clone_when_a_parallel_run_finished_first(
    source_url: str, source_work: Path, monkeypatch: pytest.MonkeyPatch
):
    replace = Path.replace

    def publish_after_another_clone(pending: Path, destination: Path) -> Path:
        winner = pending.with_name("winner")
        shutil.copytree(pending, winner)
        (winner / "winner-marker").touch()
        replace(winner, destination)
        return replace(pending, destination)

    monkeypatch.setattr(Path, "replace", publish_after_another_clone)

    clone = fetch.fetch_clone(source_url)

    assert read_head_commit(clone) == read_head_commit(source_work)
    assert (clone / "winner-marker").is_file()
    assert list(clone.parent.iterdir()) == [clone]


def test_lock_writes_lf_line_endings_when_run_on_any_platform(locked_consumer: Path):
    assert b"\r" not in (locked_consumer / "rulepack.lock").read_bytes()


@pytest.mark.usefixtures("_rewrite_source_history", "_remove_cached_source")
def test_list_fetches_the_locked_commit_when_no_ref_points_at_it(
    locked_consumer: Path, run_rulepack
):
    locked = tomllib.loads((locked_consumer / "rulepack.lock").read_text())

    completed = run_rulepack(
        "packs", "list", "--json", working_directory=locked_consumer
    )

    assert completed.returncode == 0, completed.stderr
    team = json.loads(completed.stdout)["team"]
    assert team["commit"] == locked["sources"]["team"]["commit"]
    assert "python-core" in team["packs"]


def test_list_reports_no_commit_when_a_locked_source_became_a_path(
    locked_consumer: Path, source_work: Path, run_rulepack
):
    (locked_consumer / ".rulepack.toml").write_text(
        f'[sources.team]\npath = "{source_work.as_posix()}"\n'
    )

    completed = run_rulepack(
        "packs", "list", "--json", working_directory=locked_consumer
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["team"]["commit"] is None


def test_update_ignores_unselected_sources_when_given_a_name(
    locked_consumer: Path, source_url: str, run_rulepack
):
    config = locked_consumer / ".rulepack.toml"
    with config.open("a", encoding="utf-8") as stream:
        stream.write(f'\n[sources.other]\ngit = "{source_url}"\nref = "missing-ref"\n')

    completed = run_rulepack(
        "packs", "update", "team", working_directory=locked_consumer
    )

    assert completed.returncode == 0, completed.stderr


def test_list_rejects_the_lock_when_the_commit_is_a_mutable_ref(
    locked_consumer: Path, lock_text: str, source_work: Path, run_rulepack
):
    (locked_consumer / "rulepack.lock").write_text(
        lock_text.replace(read_head_commit(source_work), "main"), encoding="utf-8"
    )

    completed = run_rulepack("packs", "list", working_directory=locked_consumer)

    assert completed.returncode == 2
    assert "sources.team.commit" in completed.stderr


def test_lock_cleans_staging_when_clone_fails(
    consumer: Path, cache_directory: Path, tmp_path: Path, run_rulepack
):
    missing = (tmp_path / "missing.git").as_uri()
    (consumer / ".rulepack.toml").write_text(
        f'[sources.team]\ngit = "{missing}"\nref = "main"\n', encoding="utf-8"
    )

    completed = run_rulepack("packs", "lock", working_directory=consumer)

    assert completed.returncode == 2
    assert not list(cache_directory.glob("*/clone-*"))
