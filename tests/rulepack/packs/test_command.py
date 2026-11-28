import json
import subprocess
import zipfile
from pathlib import Path

import pytest

from rulepack.packs import sources
from tests.rulepack.packs.helpers import (
    publish_source,
    read_head_commit,
    write_consumer_config,
)


def test_packs_lock_writes_the_same_file_when_run_twice(
    locked_consumer: Path, run_in, source_work: Path
):
    first = (locked_consumer / "rulepack.lock").read_text()

    completed = run_in(locked_consumer, "packs", "lock")

    assert completed.returncode == 0, completed.stderr
    assert (locked_consumer / "rulepack.lock").read_text() == first
    assert f'commit = "{read_head_commit(source_work)}"' in first


def test_packs_update_moves_the_pin_when_the_branch_has_a_new_commit(
    tmp_path: Path, locked_consumer: Path, run_in, source_work: Path
):
    (source_work / "notes.md").write_text("# Notes\n")
    publish_source(source_work, tmp_path / "source.git")

    kept = run_in(locked_consumer, "packs", "lock")
    kept_lock = (locked_consumer / "rulepack.lock").read_text()
    updated = run_in(locked_consumer, "packs", "update")

    assert (kept.returncode, updated.returncode) == (0, 0), updated.stderr
    assert f'commit = "{read_head_commit(source_work)}"' not in kept_lock
    assert (
        f'commit = "{read_head_commit(source_work)}"'
        in (locked_consumer / "rulepack.lock").read_text()
    )


def test_packs_list_reports_packs_and_the_locked_commit_when_asked_for_json(
    locked_consumer: Path, run_in, source_work: Path
):
    completed = run_in(locked_consumer, "packs", "list", "--json")

    team = json.loads(completed.stdout)["team"]
    assert team["commit"] == read_head_commit(source_work)
    assert team["packs"] == {"python-core": ["no-bare-except"]}


def test_config_shows_a_path_source_relative_to_the_repo_when_it_is_inside(
    tmp_path: Path, run_in
):
    repository = tmp_path / "local"
    (repository / "packs" / "team").mkdir(parents=True)
    write_consumer_config(repository, '[sources.team]\npath = "packs/team"\n')

    completed = run_in(repository, "config", "--json")

    pack_sources = json.loads(completed.stdout)["settings"]["sources"]
    assert pack_sources == {
        "value": {"team": {"git": None, "ref": None, "path": "packs/team"}},
        "source": "file",
    }


def test_packs_update_skips_path_sources_when_no_source_is_named(
    locked_consumer: Path, source_work: Path, run_in
):
    config = locked_consumer / ".rulepack.toml"
    config.write_text(
        config.read_text() + f'\n[sources.local]\npath = "{source_work.as_posix()}"\n'
    )

    completed = run_in(locked_consumer, "packs", "update")

    assert completed.returncode == 0, completed.stderr


@pytest.mark.slow
def test_wheel_ships_no_pack_content_when_built(tmp_path: Path, repository_root: Path):
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=repository_root,
        capture_output=True,
        check=True,
    )
    wheel = next(tmp_path.glob("*.whl"))

    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()

    assert [name for name in names if name.endswith(".mdc")] == []
    assert [
        name
        for name in names
        if name.endswith((".yml", ".yaml")) and "/templates/" not in name
    ] == []


def test_fetch_clone_keeps_the_other_clone_when_a_parallel_run_finished_first(
    source_url: str, monkeypatch: pytest.MonkeyPatch
):
    clone_path = sources.find_cache_directory(source_url) / "clone.git"
    run_git = sources.run_git

    def clone_while_another_run_clones(*arguments: str, cwd: Path | None = None):
        if arguments[0] == "clone":
            run_git(*arguments[:-1], str(clone_path))
        return run_git(*arguments, cwd=cwd)

    monkeypatch.setattr(sources, "run_git", clone_while_another_run_clones)

    clone = sources.fetch_clone(source_url)

    assert clone == clone_path
    assert [path.name for path in clone.parent.iterdir()] == ["clone.git"]
