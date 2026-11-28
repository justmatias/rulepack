import tomllib
from pathlib import Path


def test_init_writes_the_source_and_the_lock_when_a_source_is_given(
    fresh_repository: Path, source_url: str, run_in
):
    completed = run_in(
        fresh_repository, "init", "--yes", "--source", f"team={source_url}@main"
    )

    config = tomllib.loads((fresh_repository / ".rulepack.toml").read_text())
    assert completed.returncode == 0, completed.stderr
    assert config["sources"] == {"team": {"git": source_url, "ref": "main"}}
    assert config["packs"] == []
    assert "[sources.team]" in (fresh_repository / "rulepack.lock").read_text()


def test_init_keeps_sgconfig_at_the_top_level_when_checks_and_sources_are_given(
    fresh_repository: Path, source_url: str, run_in
):
    completed = run_in(
        fresh_repository, "init", "--yes", "--checks-dir", "lint",
        "--source", f"team={source_url}@main",
    )  # fmt: skip

    config = tomllib.loads((fresh_repository / ".rulepack.toml").read_text())
    assert completed.returncode == 0, completed.stderr
    assert config["sgconfig"] == "lint/sgconfig.yml"
    assert set(config["sources"]["team"]) == {"git", "ref"}


def test_init_rejects_the_source_when_it_has_no_ref(
    fresh_repository: Path, source_url: str, run_in
):
    completed = run_in(
        fresh_repository, "init", "--yes", "--source", f"team={source_url}"
    )

    assert completed.returncode == 2
    assert "must look like <name>=<git url>@<ref>" in completed.stderr
    assert not (fresh_repository / ".rulepack.toml").exists()
