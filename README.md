# rulepack

Run ast-grep and import-linter checks from shared, versioned rule packs in any repo.

**Status: under construction.** The CLI only answers `--version` and `--help` for now. The linter moves here from [mstack](https://github.com/justmatias/mstack), as planned in [mstack's specs](https://github.com/justmatias/mstack/tree/main/docs/specs).

## Install

You need [`uv`](https://docs.astral.sh/uv/). Install the CLI from a release tag:

```bash
uv tool install git+https://github.com/justmatias/rulepack@v0.0.0
```

Or run it without installing:

```bash
uvx --from git+https://github.com/justmatias/rulepack@v0.0.0 rulepack --version
```

semantic-release keeps the tag in these commands current. Until the first release, use `@main`.

## Development

```bash
make setup                  # dev dependencies
uv run pre-commit install   # installs the pre-commit and the commit-msg hooks
make lint                   # every pre-commit hook on every file
make test                   # pytest
```

Planned work lives in [`docs/specs/`](docs/specs/README.md).

## Releasing

Pull requests are squash-merged, so the PR title becomes the commit on `main` and decides the bump: `feat` is a minor bump, `fix` and `perf` a patch, and `!` a major bump once past `1.0` (during `0.x` it bumps the minor version). Other types release nothing.

`release-prepare.yml` commits the bump, `CHANGELOG.md`, `uv.lock` and the tags in this README to the PR branch, so the release is reviewed with the change. After the merge, the `versioning` job in `ci.yml` tags the version, creates the GitHub release and moves the `v<major>` tag.

## Maintaining

GitHub settings, applied with `gh`:

- **Public**, so branch rulesets work on the free plan and consumers can install the CLI and its hooks without a token.
- **Squash merge only.** The squash commit title is the PR title (`COMMIT_OR_PR_TITLE`), and head branches are deleted on merge:

  ```bash
  gh api -X PATCH repos/justmatias/rulepack \
    -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false \
    -f squash_merge_commit_title=COMMIT_OR_PR_TITLE -f squash_merge_commit_message=COMMIT_MESSAGES \
    -F delete_branch_on_merge=true
  ```

- **A `main` ruleset**: no deletion, no force push, and changes only through a pull request merged with squash:

  ```bash
  gh api -X POST repos/justmatias/rulepack/rulesets --input - <<'EOF'
  {"name": "main", "target": "branch", "enforcement": "active",
   "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
   "rules": [{"type": "deletion"}, {"type": "non_fast_forward"},
     {"type": "pull_request", "parameters": {"allowed_merge_methods": ["squash"],
       "required_approving_review_count": 0, "dismiss_stale_reviews_on_push": false,
       "require_code_owner_review": false, "require_last_push_approval": false,
       "required_review_thread_resolution": false}}]}
  EOF
  ```

- **A `GH_TOKEN` secret**: a fine-grained token with contents write access on this repo only. `release-prepare.yml` and `pre-commit-autoupdate.yml` push with it, because a push made with `GITHUB_TOKEN` does not start CI on the pushed commit.

## License

MIT. See [LICENSE](LICENSE).
