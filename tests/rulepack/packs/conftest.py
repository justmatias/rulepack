import json
import subprocess
from pathlib import Path

import pytest

from tests.rulepack.helpers import init_git_repository, run_git
from tests.rulepack.packs.helpers import BARE_EXCEPT, publish_source, write_source


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
    """A git repo with a bare except, selecting team/python-core from a git source."""
    repository = tmp_path / "consumer"
    repository.mkdir()
    (repository / "target.py").write_bytes(BARE_EXCEPT.read_bytes())
    (repository / ".rulepack.toml").write_text(
        'packs = ["team/python-core"]\n\n'
        f'[sources.team]\ngit = "{source_url}"\nref = "main"\n',
        encoding="utf-8",
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
    """A folder, not a git repo, selecting team/python-core from a path source."""
    repository = tmp_path / "local"
    repository.mkdir()
    (repository / "target.py").write_bytes(BARE_EXCEPT.read_bytes())
    (repository / ".rulepack.toml").write_text(
        'packs = ["team/python-core"]\n\n'
        f'[sources.team]\npath = "{source_work.as_posix()}"\n',
        encoding="utf-8",
    )
    return repository


@pytest.fixture
def _rewrite_source_history(
    tmp_path: Path,
    source_work: Path,
    lock_text: str,  # pylint: disable=unused-argument  # the lock pins the old head first
) -> None:
    """Force-push main to a new root commit, so no ref points at the locked one.

    The cache's partial clone still gets the locked commit: git fetches a missing
    object from the server by its id.
    """
    run_git(source_work, "checkout", "--quiet", "--orphan", "rewritten")
    run_git(source_work, "commit", "--quiet", "-m", "rewritten")
    run_git(source_work, "push", "--quiet", "--force", "origin", "rewritten:main")
    # Otherwise a clone gets the old pack whole, unreachable commit included.
    run_git(tmp_path / "source.git", "config", "pack.allowPackReuse", "false")


@pytest.fixture
def scan(run_in):
    def run(repository: Path, *arguments: str) -> tuple[int, dict]:
        completed = run_in(repository, "lint", "--only", "scan", "--json", *arguments)
        return completed.returncode, json.loads(completed.stdout or "{}")

    return run


@pytest.fixture
def append_config(locked_consumer: Path):
    def append(text: str) -> None:
        config = locked_consumer / ".rulepack.toml"
        config.write_text(config.read_text(encoding="utf-8") + text, encoding="utf-8")

    return append


@pytest.fixture
def _write_local_check_with_pack_id(locked_consumer: Path) -> None:
    """The repo's own no-bare-except, which never matches."""
    checks = locked_consumer / "lint"
    (checks / "rules").mkdir(parents=True)
    (checks / "sgconfig.yml").write_text("ruleDirs: [rules]\n", encoding="utf-8")
    (checks / "rules" / "local.yml").write_text(
        "id: no-bare-except\nlanguage: Python\nseverity: error\n"
        "message: Local rule\nrule: {pattern: never_called()}\n",
        encoding="utf-8",
    )


@pytest.fixture(
    params=[
        lambda text: text.replace("id: no-bare-except\n", ""),
        lambda text: text + "---\n{}\n",
    ],
    ids=["missing-id", "empty-rule"],
)
def _write_pack_rule_without_id(
    request: pytest.FixtureRequest, source_work: Path
) -> None:
    check = source_work / "lint" / "rules" / "no-bare-except.yml"
    check.write_text(request.param(check.read_text()), encoding="utf-8")


@pytest.fixture
def _break_pack_rule_tests(source_work: Path) -> None:
    test = source_work / "lint" / "rule-tests" / "no-bare-except-test.yml"
    test.write_text("id: [unclosed\n", encoding="utf-8")


@pytest.fixture
def _write_pack_rule_test_as_a_list(source_work: Path) -> None:
    test = source_work / "lint" / "rule-tests" / "no-bare-except-test.yml"
    test.write_text("- id: no-bare-except\n", encoding="utf-8")


@pytest.fixture
def fresh_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "fresh"
    repository.mkdir()
    return init_git_repository(repository)
