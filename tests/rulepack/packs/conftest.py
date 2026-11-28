import json
import subprocess
from pathlib import Path

import pytest

from tests.rulepack.helpers import init_git_repository
from tests.rulepack.packs.helpers import (
    publish_source,
    write_consumer_config,
    write_source,
)


@pytest.fixture(autouse=True)
def _isolate_machine_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("CI", raising=False)


@pytest.fixture
def source_work(tmp_path: Path) -> Path:
    work = tmp_path / "source"
    write_source(work, {"python-core": ["no-bare-except"]})
    return work


@pytest.fixture
def source_url(tmp_path: Path, source_work: Path) -> str:
    return publish_source(source_work, tmp_path / "source.git")


@pytest.fixture
def consumer(tmp_path: Path, source_url: str, bare_except_source: str) -> Path:
    """A repo with a bare except, selecting team/python-core from a git source."""
    repository = tmp_path / "consumer"
    repository.mkdir()
    (repository / "target.py").write_text(bare_except_source, encoding="utf-8")
    write_consumer_config(
        repository,
        'packs = ["team/python-core"]\n\n'
        f'[sources.team]\ngit = "{source_url}"\nref = "main"\n',
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
def cache_directory(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "rulepack" / "sources"


@pytest.fixture
def scan(run_in):
    def run(repository: Path, *arguments: str) -> tuple[int, dict]:
        completed = run_in(repository, "lint", "--only", "scan", "--json", *arguments)
        return completed.returncode, json.loads(completed.stdout or "{}")

    return run
