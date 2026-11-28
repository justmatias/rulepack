import subprocess
from pathlib import Path

import pytest

from tests.helpers import init_git_repository
from tests.rulepack.packs.helpers import publish_source, write_source


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))


@pytest.fixture
def cache_directory(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "rulepack" / "sources"


@pytest.fixture
def source_work(tmp_path: Path) -> Path:
    work = tmp_path / "source"
    write_source(work, {"python-core": ["no-bare-except"]})
    return work


@pytest.fixture
def source_url(tmp_path: Path, source_work: Path) -> str:
    return publish_source(source_work, tmp_path / "source.git")


@pytest.fixture
def consumer(tmp_path: Path, source_url: str) -> Path:
    """A git repo whose config declares the `team` git source at main."""
    repository = tmp_path / "consumer"
    repository.mkdir()
    (repository / ".rulepack.toml").write_text(
        f'[sources.team]\ngit = "{source_url}"\nref = "main"\n', encoding="utf-8"
    )
    return init_git_repository(repository)


@pytest.fixture
def run_in(run_rulepack):
    def run(repository: Path, *arguments: str) -> subprocess.CompletedProcess:
        return run_rulepack(*arguments, working_directory=repository)

    return run


@pytest.fixture
def locked_consumer(consumer: Path, run_in) -> Path:
    completed = run_in(consumer, "packs", "lock")
    assert completed.returncode == 0, completed.stderr
    return consumer


@pytest.fixture
def lock_text(locked_consumer: Path) -> str:
    return (locked_consumer / "rulepack.lock").read_text(encoding="utf-8")


@pytest.fixture
def _push_new_source_commit(
    tmp_path: Path,
    source_work: Path,
    lock_text: str,  # pylint: disable=unused-argument  # the lock pins the old head first
) -> None:
    (source_work / "notes.md").write_text("# Notes\n", encoding="utf-8")
    publish_source(source_work, tmp_path / "source.git")


@pytest.fixture
def path_consumer(tmp_path: Path, source_work: Path) -> Path:
    """A folder whose config declares the source folder as the `team` path source."""
    repository = tmp_path / "local"
    repository.mkdir()
    (repository / ".rulepack.toml").write_text(
        f'[sources.team]\npath = "{source_work.as_posix()}"\n', encoding="utf-8"
    )
    return repository
