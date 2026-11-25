import argparse
from importlib import metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rulepack",
        description=(
            "Run ast-grep and import-linter checks from shared, versioned rule packs."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"rulepack {metadata.version('rulepack')}",
    )
    parser.parse_args(argv)
    parser.print_help()
    return 0
