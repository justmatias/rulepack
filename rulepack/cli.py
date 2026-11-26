import argparse
import importlib
import importlib.metadata
import logging
import sys

logger = logging.getLogger(__name__)

COMMANDS = {
    "config": "rulepack.config.command",
}


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(
        prog="rulepack",
        description=(
            "Run ast-grep and import-linter checks from shared, versioned rule packs."
        ),
        epilog="Run 'rulepack <command> --help' for what each command does.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"rulepack {importlib.metadata.version('rulepack')}",
    )
    parser.add_argument("command", choices=COMMANDS)
    parsed = parser.parse_args(arguments[:1])
    command = importlib.import_module(COMMANDS[parsed.command])
    config = importlib.import_module("rulepack.config")
    try:
        return int(command.main(arguments[1:]))
    except config.ConfigError as error:
        logger.error("rulepack: %s", error)
        return 2
