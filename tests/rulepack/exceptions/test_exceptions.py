from pathlib import Path

import pytest

from tests.rulepack.helpers import init_git_repository

VALID_HEADER = (
    '# rule-exception: reason="third-party legacy API" expires=2999-12-31 '
    "approved-by=@reviewer\n"
)


def test_exceptions_pass_when_exception_is_justified(run_rulepack, exception_file):
    completed = run_rulepack("exceptions", str(exception_file(VALID_HEADER)))

    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    ("header", "expected_problem"),
    [
        ("", "needs a '# rule-exception:'"),
        (
            '# rule-exception: reason="legacy" expires=2000-01-01 approved-by=@reviewer\n',
            "expired on 2000-01-01",
        ),
        (
            '# rule-exception: reason="legacy" expires=2999-12-31\n',
            "missing approved-by",
        ),
        (
            "# rule-exception: expires=2999-12-31 approved-by=@reviewer\n",
            "missing reason",
        ),
        (
            '# rule-exception: reason="legacy" expires=someday approved-by=@reviewer\n',
            "not a YYYY-MM-DD date",
        ),
    ],
    ids=["no-justification", "expired", "no-approval", "no-reason", "bad-date"],
)
def test_exceptions_fail_when_exception_is_unjustified(
    run_rulepack, exception_file, header: str, expected_problem: str
):
    completed = run_rulepack("exceptions", str(exception_file(header)))

    assert completed.returncode == 1
    assert expected_problem in completed.stderr


def test_exceptions_pass_when_shell_exception_is_justified(
    run_rulepack, shell_exception_file
):
    completed = run_rulepack("exceptions", str(shell_exception_file(VALID_HEADER)))

    assert completed.returncode == 0, completed.stderr


def test_exceptions_fail_when_shell_exception_is_unjustified(
    run_rulepack, shell_exception_file
):
    completed = run_rulepack("exceptions", str(shell_exception_file("")))

    assert completed.returncode == 1
    assert "needs a '# rule-exception:'" in completed.stderr


def test_exceptions_check_shell_files_when_folder_is_given(
    run_rulepack, shell_exception_file
):
    folder = shell_exception_file("").parent

    completed = run_rulepack("exceptions", str(folder))

    assert completed.returncode == 1
    assert "task.sh" in completed.stderr


def test_exceptions_check_listed_file_when_its_name_has_a_space(
    run_rulepack, tmp_path: Path
):
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "my file.py").write_text(
        "x = 1  # ast-grep-ignore: no-print\n", encoding="utf-8"
    )
    init_git_repository(repository)

    completed = run_rulepack("exceptions", working_directory=repository)

    assert completed.returncode == 1
    assert "my file.py" in completed.stderr
