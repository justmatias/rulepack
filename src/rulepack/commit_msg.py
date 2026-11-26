import argparse
import difflib
import logging
import re
from pathlib import Path

from rulepack.config import resolve_config

logger = logging.getLogger(__name__)

RULE = "rules/git-commits.mdc"
MAX_SUBJECT_LENGTH = 72
SCISSORS = re.compile(r"^# -+ >8 -+$")
SUBJECT = re.compile(
    r"^(?P<type>[a-z]+)(\((?P<scope>[a-z0-9-]+)\))?(?P<breaking>!)?: (?P<summary>\S.*)$"
)
# A subject that is close enough to read its parts, to build a corrected example.
LOOSE_SUBJECT = re.compile(
    r"^(?P<type>[A-Za-z]+)\s*(\((?P<scope>[^)]*)\))?(?P<breaking>!)?\s*:\s*(?P<summary>.*)$"
)
# Messages git and tools generate. fixup! and squash! never reach the default
# branch with squash merges, so the hook lets them through.
GENERATED = re.compile(r'^(Merge |Revert "|fixup! |squash! |amend! )')


def clean_message(text: str) -> str:
    """Drop comment lines and everything below the scissors line (git --verbose)."""
    lines: list[str] = []
    for line in text.splitlines():
        if SCISSORS.match(line):
            break
        if not line.startswith("#"):
            lines.append(line.rstrip())
    return "\n".join(lines).strip("\n")


def suggested_type(written: str, types: list[str]) -> str:
    lowered = written.lower()
    if lowered in types:
        return lowered
    close = difflib.get_close_matches(lowered, types, n=1)
    if close:
        return close[0]
    return "chore" if "chore" in types else types[0]


def suggestion(subject: str, types: list[str]) -> str:
    """The subject rewritten to follow every rule, as an example for the user."""
    loose = LOOSE_SUBJECT.match(subject)
    if loose:
        commit_type = suggested_type(loose["type"], types)
        scope = re.sub(r"[^a-z0-9-]+", "-", (loose["scope"] or "").lower()).strip("-")
        breaking = "!" if loose["breaking"] else ""
        summary = loose["summary"]
    else:
        commit_type = "chore" if "chore" in types else types[0]
        scope, breaking, summary = "", "", subject
    summary = summary.strip().rstrip(".").strip() or "describe the change"
    scope_text = f"({scope})" if scope else ""
    prefix = f"{commit_type}{scope_text}{breaking}: "
    room = MAX_SUBJECT_LENGTH - len(prefix)
    if len(summary) > room:
        summary = summary[:room].rsplit(" ", 1)[0]
    return prefix + summary


def subject_problems(subject: str, types: list[str]) -> list[str]:
    problems: list[str] = []
    match = SUBJECT.match(subject)
    if not match:
        problems.append(
            "Conventional Commits subject: write 'type(scope)!: summary' with a "
            "lowercase type, an optional lowercase scope and a space after the colon"
        )
    elif match["type"] not in types:
        problems.append(
            f"Conventional Commits subject: '{match['type']}' is not an allowed type "
            f"({', '.join(types)})"
        )
    if len(subject) > MAX_SUBJECT_LENGTH:
        problems.append(
            f"subject length: {len(subject)} characters, at most {MAX_SUBJECT_LENGTH}"
        )
    if subject.endswith("."):
        problems.append("subject: no trailing period")
    return problems


def message_problems(message: str, types: list[str]) -> list[str]:
    lines = message.splitlines()
    if not lines or not lines[0].strip():
        return ["the commit message is empty"]
    subject = lines[0]
    if GENERATED.match(subject):
        return []
    problems = subject_problems(subject, types)
    if len(lines) > 1 and lines[1].strip():
        problems.append("body: separate it from the subject with a blank line")
    return problems


def main(argv: list[str] | None = None) -> int:
    """`rulepack commit-msg`: commit messages follow Conventional Commits.

    Run as a `commit-msg` hook: git passes the file with the message being written.
    """
    parser = argparse.ArgumentParser(
        prog="rulepack commit-msg",
        description=(
            "Check a commit message file (as a commit-msg hook): a Conventional "
            "Commits subject with an allowed type ([commits].types), at most "
            f"{MAX_SUBJECT_LENGTH} characters, no trailing period, and a blank line "
            "before the body."
        ),
    )
    parser.add_argument("message_file", type=Path, help="The commit message file.")
    arguments = parser.parse_args(argv)
    types = resolve_config().values.commits.types

    message = clean_message(arguments.message_file.read_text(encoding="utf-8"))
    problems = message_problems(message, types)
    if not problems:
        return 0
    subject = message.splitlines()[0] if message else ""
    logger.error("rulepack commit-msg: the message breaks %s:", RULE)
    for problem in problems:
        logger.error("  - %s", problem)
    logger.error("Example: %s", suggestion(subject, types))
    return 1
