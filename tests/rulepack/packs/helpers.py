import subprocess
from pathlib import Path

from tests.rulepack.helpers import init_git_repository, run_git

SAMPLE_REPOSITORY = Path(__file__).resolve().parents[2] / "fixtures"
CHECKS = SAMPLE_REPOSITORY / "lint" / "rules"
TESTS = SAMPLE_REPOSITORY / "lint" / "rule-tests"


def write_source(root: Path, packs: dict[str, list[str]], manifest: str = "") -> None:
    """A source folder: a packs.toml and the sample checks and tests it lists."""
    (root / "lint" / "rules").mkdir(parents=True, exist_ok=True)
    (root / "lint" / "rule-tests").mkdir(parents=True, exist_ok=True)
    tables = "".join(
        f"\n[packs.{name}]\nchecks = {checks!r}\n".replace("'", '"')
        for name, checks in packs.items()
    )
    (root / "packs.toml").write_text(manifest + tables, encoding="utf-8")
    for check in {check for checks in packs.values() for check in checks}:
        (root / "lint" / "rules" / f"{check}.yml").write_bytes(
            (CHECKS / f"{check}.yml").read_bytes()
        )
        test = TESTS / f"{check}-test.yml"
        if test.is_file():
            (root / "lint" / "rule-tests" / test.name).write_bytes(test.read_bytes())


def publish_source(work: Path, bare: Path) -> str:
    """Commit the work folder and push it to a bare repo; return the bare repo's URL."""
    if not (work / ".git").exists():
        init_git_repository(work)
        subprocess.run(
            ["git", "clone", "--quiet", "--bare", str(work), str(bare)], check=True
        )
        run_git(bare, "config", "uploadpack.allowFilter", "true")
        run_git(work, "remote", "add", "origin", str(bare))
    else:
        run_git(work, "add", "--all")
        run_git(work, "commit", "--quiet", "-m", "change")
        run_git(work, "push", "--quiet", "origin", "main")
    return bare.as_uri()


def write_consumer_config(repository: Path, content: str) -> None:
    (repository / ".rulepack.toml").write_text(content, encoding="utf-8")


def read_head_commit(repository: Path) -> str:
    return run_git(repository, "rev-parse", "HEAD").strip()


def write_local_check(repository: Path, check_id: str, pattern: str) -> None:
    """A repo-owned ast-grep check at the default sgconfig path (lint/)."""
    checks = repository / "lint"
    (checks / "rules").mkdir(parents=True, exist_ok=True)
    (checks / "sgconfig.yml").write_text("ruleDirs: [rules]\n")
    (checks / "rules" / f"{check_id}.yml").write_text(
        f"id: {check_id}\nlanguage: Python\nseverity: error\n"
        f"message: Local check\nrule: {{pattern: {pattern}}}\n"
    )
