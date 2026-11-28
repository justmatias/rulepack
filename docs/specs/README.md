# Specs

Implementation plans for rulepack. Each spec says what it depends on, what it changes, how it is tested and when it is done. When a spec ships, delete it in the same PR (git history keeps it) and remove its row here.

## Next

| Spec | Summary | Depends on |
| --- | --- | --- |
| [pack-sources](pack-sources.md) | Run checks from one or more git or path sources, pinned by a lockfile | mstack's [cleanup](https://github.com/justmatias/mstack/blob/main/docs/specs/mstack-uses-rulepack.md) |

## Writing a spec

Every spec has the same sections: Phase / Depends on, Problem, Goal, Out of scope, Design, Changes, Tests, Docs, Acceptance criteria, Open questions. English only, and practices, never domain details.
