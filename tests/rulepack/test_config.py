import json
from pathlib import Path

import pytest

from rulepack.config import ConfigError, resolve_config


def test_config_uses_defaults_when_file_is_missing(git_repository: Path):
    config = resolve_config(start=git_repository)

    assert config.file is None
    assert config.root == git_repository
    assert config.values.rules_dir == git_repository / ".cursor/rules"
    assert config.values.sgconfig == git_repository / "lint-rules/sgconfig.yml"
    assert set(config.sources.values()) == {"default"}


def test_config_reads_rulepack_toml_when_it_exists(git_repository: Path, write_config):
    write_config('rules_dir = "rules"\n[scan]\nexclude = ["generated/**"]\n')

    config = resolve_config(start=git_repository)

    assert config.values.rules_dir == git_repository / "rules"
    assert config.values.scan.exclude == ["generated/**"]
    assert config.sources["rules_dir"] == "file"
    assert config.sources["scan.exclude"] == "file"
    assert config.sources["scan.extensions"] == "default"


def test_pyproject_table_is_ignored_when_no_rulepack_toml(
    git_repository: Path, write_config
):
    write_config('[tool.rulepack]\nrules_dir = "rules"\n', name="pyproject.toml")

    assert resolve_config(start=git_repository).file is None


@pytest.mark.parametrize(
    "content",
    ['rule_dir = "rules"\n', '[scan]\nexcludes = ["generated/**"]\n'],
    ids=["top-level", "nested"],
)
def test_config_fails_when_key_is_unknown(
    git_repository: Path, write_config, content: str
):
    write_config(content)

    with pytest.raises(ConfigError, match="Extra inputs are not permitted"):
        resolve_config(start=git_repository)


def test_flag_overrides_file_when_both_set_a_key(
    git_repository: Path, write_config, monkeypatch
):
    write_config('rules_dir = "rules"\n')
    monkeypatch.chdir(git_repository)

    config = resolve_config({"rules_dir": Path("other-rules"), "sgconfig": None})

    assert config.values.rules_dir == git_repository / "other-rules"
    assert config.sources["rules_dir"] == "flag"
    assert config.sources["sgconfig"] == "default"


def test_config_is_found_when_started_from_a_subfolder(
    git_repository: Path, write_config
):
    write_config('rules_dir = "rules"\n')
    subfolder = git_repository / "package" / "module"
    subfolder.mkdir(parents=True)

    config = resolve_config(start=subfolder)

    assert config.file == git_repository / ".rulepack.toml"
    assert config.values.rules_dir == git_repository / "rules"


def test_config_is_not_found_when_it_is_above_the_git_root(git_repository: Path):
    (git_repository.parent / ".rulepack.toml").write_text('rules_dir = "outside"\n')

    config = resolve_config(start=git_repository)

    assert config.file is None
    assert config.values.rules_dir == git_repository / ".cursor/rules"


def test_config_command_reports_sources_when_flags_and_file_are_set(
    run_rulepack, write_config, git_repository
):
    write_config('rules_dir = "rules"\n')

    completed = run_rulepack(
        "config",
        "--sgconfig",
        "checks/sgconfig.yml",
        "--json",
        working_directory=git_repository,
    )

    settings = json.loads(completed.stdout)["settings"]
    assert completed.returncode == 0, completed.stderr
    assert settings["rules_dir"] == {"value": "rules", "source": "file"}
    assert settings["sgconfig"] == {"value": "checks/sgconfig.yml", "source": "flag"}
    assert settings["importlinter"] == {"value": ".importlinter", "source": "default"}


def test_command_exits_with_message_when_config_is_invalid(
    run_rulepack, write_config, git_repository
):
    write_config('rules_dir = ["not", "a", "path"]\n')

    completed = run_rulepack("config", working_directory=git_repository)

    assert completed.returncode == 2
    assert ".rulepack.toml" in completed.stderr
