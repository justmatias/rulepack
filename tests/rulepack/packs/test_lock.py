from pathlib import Path

from rulepack.packs.lock import Lock, LockEntry, read_lock, write_lock


def test_lock_reads_back_what_it_wrote_when_names_and_urls_are_not_ascii(
    tmp_path: Path,
):
    lock = Lock(
        sources={
            "équipe 😀": LockEntry(
                git="https://example.invalid/😀.git", ref="main", commit="0" * 40
            )
        }
    )
    path = tmp_path / "rulepack.lock"

    write_lock(path, lock)

    assert read_lock(path) == lock
