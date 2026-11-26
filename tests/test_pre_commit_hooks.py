import shlex

import pytest
import yaml

from rulepack.cli import COMMANDS
from tests.helpers import REPOSITORY_ROOT, try_repo

HOOKS = yaml.safe_load((REPOSITORY_ROOT / ".pre-commit-hooks.yaml").read_text())


@pytest.mark.parametrize("hook", HOOKS, ids=lambda hook: hook["id"])
def test_entry_runs_a_rulepack_command_when_hook_is_published(hook: dict):
    program, command, *_ = shlex.split(hook["entry"])

    assert (program, command in COMMANDS) == ("rulepack", True)


@pytest.mark.parametrize("hook", HOOKS, ids=lambda hook: hook["id"])
def test_hook_installs_rulepack_as_python_when_published(hook: dict):
    assert hook["language"] == "python"


def test_hook_ids_are_unique_when_hooks_are_published():
    ids = [hook["id"] for hook in HOOKS]

    assert len(ids) == len(set(ids))


@pytest.mark.slow
def test_try_repo_fails_when_file_breaks_a_rule_and_passes_once_fixed(
    repository_with_a_rule,
):
    bad = "try:\n    run()\nexcept:\n    raise\n"
    fixed = "try:\n    run()\nexcept ValueError:\n    raise\n"

    assert try_repo(repository_with_a_rule, bad, "rulepack-lint").returncode == 1
    assert try_repo(repository_with_a_rule, fixed, "rulepack-lint").returncode == 0


@pytest.mark.slow
def test_try_repo_passes_every_hook_when_repository_is_clean(repository_with_a_rule):
    completed = try_repo(repository_with_a_rule, "VALUE = 1\n")

    assert completed.returncode == 0, completed.stdout
