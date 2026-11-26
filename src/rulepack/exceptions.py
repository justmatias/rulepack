import argparse
import datetime
import fnmatch
import io
import json
import logging
import re
import shlex
import subprocess
import sys
import tokenize
from pathlib import Path

from rulepack.config import resolve_config

logger = logging.getLogger(__name__)

IGNORE_COMMENT = re.compile(r"^#\s*ast-grep-ignore\b(?::\s*(?P<rule_ids>.*))?$")
EXCEPTION_COMMENT = re.compile(r"^#\s*rule-exception:\s*(?P<fields>.*)$")
REQUIRED_FIELDS = ("reason", "expires", "approved-by")
# Files whose `#` comments may carry an ast-grep-ignore.
SUFFIXES = (".py", ".sh")


def is_excluded(path: Path, root: Path, exclude_globs: list[str]) -> bool:
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        return False
    relative = resolved.relative_to(root).as_posix()
    return any(fnmatch.fnmatch(relative, pattern) for pattern in exclude_globs)


def source_files(paths: list[Path], root: Path, exclude_globs: list[str]) -> list[Path]:
    if not paths:
        patterns = [f"*{suffix}" for suffix in SUFFIXES]
        listed = subprocess.run(
            [
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
                *patterns,
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split("\0")
        return [
            Path(name)
            for name in listed
            if Path(name).is_file() and not is_excluded(Path(name), root, exclude_globs)
        ]
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(
                sorted(file for file in path.rglob("*") if file.suffix in SUFFIXES)
            )
        else:
            files.append(path)
    return files


def shell_comments_by_line(source: str) -> dict[int, str]:
    """Line-based: a whole-line `#` comment, or a trailing ` # ...` one."""
    comments: dict[int, str] = {}
    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            comments[line_number] = stripped
        elif (index := line.find(" #")) != -1:
            comments[line_number] = line[index + 1 :].strip()
    return comments


def python_comments_by_line(source: str) -> dict[int, str]:
    comments: dict[int, str] = {}
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                comments[token.start[0]] = token.string.strip()
    except (tokenize.TokenError, SyntaxError):
        pass
    return comments


def parse_exception_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in shlex.split(text):
        key, separator, value = part.partition("=")
        if separator:
            fields[key] = value
    return fields


def validate_exception_fields(
    location: str, fields_text: str, today: datetime.date
) -> tuple[dict[str, str], str | None]:
    try:
        fields = parse_exception_fields(fields_text)
    except ValueError as error:
        return {}, f"{location}: malformed rule-exception ({error})"
    missing = [field for field in REQUIRED_FIELDS if not fields.get(field)]
    if missing:
        return fields, f"{location}: rule-exception is missing {', '.join(missing)}"
    try:
        expires = datetime.date.fromisoformat(fields["expires"])
    except ValueError:
        return fields, (
            f"{location}: expires={fields['expires']} is not a YYYY-MM-DD date"
        )
    if expires < today:
        return fields, f"{location}: rule-exception expired on {expires}"
    if not fields["approved-by"].startswith("@"):
        return fields, f"{location}: approved-by must be a @handle"
    return fields, None


def ignored_rule_ids(rule_ids_text: str | None) -> list[str]:
    return [
        rule_id.strip()
        for rule_id in (rule_ids_text or "").split(",")
        if rule_id.strip()
    ]


def missing_exception_problem(location: str, line: str) -> str:
    is_trailing = not line.lstrip().startswith("#")
    where = "the line above the code" if is_trailing else "the line directly above"
    return f"{location}: 'ast-grep-ignore' needs a '# rule-exception:' on {where}"


def file_exceptions(path: Path, today: datetime.date) -> tuple[list[dict], list[str]]:
    exceptions: list[dict] = []
    problems: list[str] = []
    source = path.read_text(encoding="utf-8")
    comments = (
        shell_comments_by_line(source)
        if path.suffix == ".sh"
        else python_comments_by_line(source)
    )
    lines = source.splitlines()
    for line_number, comment in sorted(comments.items()):
        ignore = IGNORE_COMMENT.match(comment)
        if not ignore:
            continue
        location = f"{path}:{line_number}"
        rule_ids = ignored_rule_ids(ignore["rule_ids"])
        if not rule_ids:
            problems.append(
                f"{location}: 'ast-grep-ignore' must name the rule ids it suppresses"
            )
        exception = EXCEPTION_COMMENT.match(comments.get(line_number - 1, ""))
        if not exception:
            problems.append(missing_exception_problem(location, lines[line_number - 1]))
            continue
        fields, problem = validate_exception_fields(
            f"{path}:{line_number - 1}", exception["fields"], today
        )
        if problem:
            problems.append(problem)
            continue
        exceptions.extend(
            {
                "rule": rule_id,
                "file": str(path),
                "line": line_number,
                "reason": fields["reason"],
                "expires": fields["expires"],
                "approved_by": fields["approved-by"],
            }
            for rule_id in rule_ids
        )
    return exceptions, problems


def collect_exceptions(
    files: list[Path], today: datetime.date
) -> tuple[list[dict], list[str]]:
    exceptions: list[dict] = []
    problems: list[str] = []
    for path in files:
        found, invalid = file_exceptions(path, today)
        exceptions.extend(found)
        problems.extend(invalid)
    return exceptions, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rulepack exceptions",
        description=(
            "Every ast-grep-ignore must carry a rule-exception with reason, "
            "expiry and approval."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files or folders (default: git files, minus [scan].exclude).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print active exceptions as JSON."
    )
    parser.add_argument(
        "--today", type=datetime.date.fromisoformat, default=datetime.date.today()
    )
    arguments = parser.parse_args(argv)
    config = resolve_config()

    exceptions, problems = collect_exceptions(
        source_files(arguments.paths, config.root, config.values.scan.exclude),
        arguments.today,
    )
    if arguments.json:
        sys.stdout.write(
            json.dumps({"exceptions": exceptions, "problems": problems}, indent=2)
            + "\n"
        )
    for problem in problems:
        logger.error("%s", problem)
    if not problems and not arguments.json:
        logger.info("exceptions: OK (%d active exceptions)", len(exceptions))
    return 1 if problems else 0
