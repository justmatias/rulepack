from importlib import metadata

import pytest

from rulepack.cli import main


def test_prints_package_version_when_called_with_version_flag(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"rulepack {metadata.version('rulepack')}\n"


def test_lists_usage_when_called_with_help_flag(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.startswith("usage: rulepack")
