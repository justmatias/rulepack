SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

.PHONY: setup lint test

setup:
	uv sync

lint:
	uv run pre-commit run --all-files

test:
	uv run pytest -q
