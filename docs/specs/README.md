# Specs

Implementation plans for rulepack. Each spec says what it depends on, what it changes, how it is tested and when it is done. When a spec ships, delete it in the same PR (git history keeps it) and remove its row here.

The move of the linter out of mstack is planned in mstack's specs: [pack-sources](https://github.com/justmatias/mstack/blob/main/docs/specs/pack-sources.md), [rulepack-extraction](https://github.com/justmatias/mstack/blob/main/docs/specs/rulepack-extraction.md) and [mstack-uses-rulepack](https://github.com/justmatias/mstack/blob/main/docs/specs/mstack-uses-rulepack.md). Features after the extraction are specced here.

## Writing a spec

Every spec has the same sections: Phase / Depends on, Problem, Goal, Out of scope, Design, Changes, Tests, Docs, Acceptance criteria, Open questions. English only, and practices, never domain details.
