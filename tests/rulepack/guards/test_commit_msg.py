import pytest

from rulepack.commit_msg import clean_message, suggestion


@pytest.mark.parametrize(
    "message",
    [
        "feat: add the shell rules\n",
        "fix(lint): skip the scan when nothing changed\n",
        "refactor(install)!: drop the old manifest schema\n",
        "docs: explain the hooks\n\nThe README only listed the ids, not when each runs.\n",
        "feat: " + "a" * 66 + "\n",
    ],
    ids=["plain", "scope", "breaking", "body", "72-characters"],
)
def test_commit_msg_passes_when_message_is_valid(commit_message, message: str):
    completed = commit_message(message)

    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("feature: add the rules\n", "'feature' is not an allowed type"),
        ("Feat: add the rules\n", "Conventional Commits subject"),
        ("feat:add the rules\n", "Conventional Commits subject"),
        ("feat: " + "a" * 67 + "\n", "73 characters, at most 72"),
        ("feat: add the rules.\n", "no trailing period"),
        ("feat: add the rules\nBecause they were missing.\n", "blank line"),
    ],
    ids=[
        "unknown-type",
        "uppercase-type",
        "missing-space",
        "73-characters",
        "trailing-period",
        "no-blank-line",
    ],
)
def test_commit_msg_fails_with_rule_and_example_when_message_is_invalid(
    commit_message, message: str, expected: str
):
    completed = commit_message(message)

    assert completed.returncode == 1
    assert expected in completed.stderr
    assert "rules/git-commits.mdc" in completed.stderr
    assert "Example: feat: a" in completed.stderr


@pytest.mark.parametrize(
    "message",
    [
        "Merge branch 'main' into feature\n",
        'Revert "feat: add the rules"\n\nThis reverts commit abc.\n',
        "fixup! feat: add the rules\n",
        "squash! feat: add the rules\n",
    ],
    ids=["merge", "revert", "fixup", "squash"],
)
def test_commit_msg_passes_when_message_is_generated(commit_message, message: str):
    assert commit_message(message).returncode == 0


def test_commit_msg_ignores_lines_when_they_are_comments_or_below_scissors(
    commit_message,
):
    message = (
        "feat: add the rules\n"
        "# Please enter the commit message for your changes.\n"
        "# ------------------------ >8 ------------------------\n"
        "diff --git a/x b/x\n"
        "+Some line that would break the rules.\n"
    )

    assert commit_message(message).returncode == 0


def test_commit_msg_fails_when_message_is_empty(commit_message):
    completed = commit_message("# only a comment\n")

    assert completed.returncode == 1
    assert "empty" in completed.stderr


def test_commit_msg_accepts_type_when_config_lists_it(commit_message, write_config):
    write_config('[commits]\ntypes = ["change", "fix"]\n')

    assert commit_message("change: rename the module\n").returncode == 0
    assert commit_message("feat: add the rules\n").returncode == 1


def test_clean_message_keeps_body_when_trailing_lines_are_blank():
    assert clean_message("feat: x\n\nWhy.\n\n# comment\n\n") == "feat: x\n\nWhy."


def test_suggestion_fixes_type_scope_and_period_when_subject_breaks_them():
    assert suggestion("Feat(My Scope): add it.", ["feat", "fix"]) == (
        "feat(my-scope): add it"
    )


def test_suggestion_fits_the_limit_when_subject_is_long():
    example = suggestion("feat: " + "word " * 30, ["feat"])

    assert len(example) <= 72
    assert example.startswith("feat: word")
