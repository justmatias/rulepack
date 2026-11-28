import shutil
from pathlib import Path

import pytest

from rulepack.packs.sources import make_writable_and_retry
from tests.rulepack.packs.helpers import write_local_check

pytestmark = pytest.mark.usefixtures("_isolate_temp_directory")


def test_post_edit_skips_pack_checks_when_the_locked_commit_is_not_cached(
    locked_consumer: Path, run_hook, cache_directory: Path, bare_except_source: str
):
    shutil.rmtree(cache_directory, onexc=make_writable_and_retry)
    cache_directory.mkdir()
    write_local_check(locked_consumer, "no-print", "print($$$)")
    (locked_consumer / "target.py").write_text(bare_except_source + "print('x')\n")

    result = run_hook(
        locked_consumer, "post-edit", tool_input={"file_path": "target.py"}
    )

    assert result.returncode == 2
    assert "no-print" in result.stderr
    assert "no-bare-except" not in result.stderr
    assert "pack checks skipped" in result.stderr
    assert not any(cache_directory.iterdir())


def test_hook_uses_host_packs_when_the_repo_has_no_config(
    tmp_path: Path, source_work: Path, run_hook, bare_except_source: str
):
    host = tmp_path / "config" / "rulepack"
    host.mkdir(parents=True)
    (host / "config.toml").write_text(
        f'packs = ["team/python-core"]\n\n[sources.team]\npath = "{source_work.as_posix()}"\n'
    )
    repository = tmp_path / "plain"
    repository.mkdir()
    (repository / ".git").mkdir()
    (repository / "target.py").write_text(bare_except_source, encoding="utf-8")

    result = run_hook(repository, "post-edit", tool_input={"file_path": "target.py"})

    assert result.returncode == 2
    assert "no-bare-except" in result.stderr
