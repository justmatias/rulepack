import json

import pytest


@pytest.mark.usefixtures("_write_sgconfig_config")
def test_config_command_reports_sources_when_flags_and_file_are_set(
    run_rulepack, git_repository
):
    completed = run_rulepack(
        "config",
        "--importlinter",
        "checks/.importlinter",
        "--json",
        working_directory=git_repository,
    )

    settings = json.loads(completed.stdout)["settings"]
    assert completed.returncode == 0, completed.stderr
    assert settings["sgconfig"] == {"value": "checks/sgconfig.yml", "source": "file"}
    assert settings["importlinter"] == {
        "value": "checks/.importlinter",
        "source": "flag",
    }
    assert settings["scan.exclude"] == {"value": [], "source": "default"}


def test_command_exits_with_message_when_config_is_invalid(
    run_rulepack, write_config, git_repository
):
    write_config('sgconfig = ["not", "a", "path"]\n')

    completed = run_rulepack("config", working_directory=git_repository)

    assert completed.returncode == 2
    assert ".rulepack.toml" in completed.stderr
