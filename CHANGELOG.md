# CHANGELOG

<!-- version list -->

## v0.10.0 (2026-11-28)

### Bug Fixes

- **lint**: Discover pack rule tests by ID
  ([`1fb8cae`](https://github.com/justmatias/rulepack/commit/1fb8cae8433a7e49739d6b291b777fc13351cbf0))

- **lint**: Name the file when a pack rule has no id
  ([`046366b`](https://github.com/justmatias/rulepack/commit/046366b415e0716ab1b8804ddee21c7efa593a77))

- **lint**: Name the file when a pack rule test is not a mapping
  ([`6ff9bab`](https://github.com/justmatias/rulepack/commit/6ff9bab6048003cb5b54b353f5672f91e0512f68))

- **lint**: Read the packs' rule tests only when the test step runs
  ([`bf94def`](https://github.com/justmatias/rulepack/commit/bf94defd185a56c8520eb96e9d60e1f7b765453c))

- **lint**: Reject an empty pack rule instead of skipping it
  ([`0c76845`](https://github.com/justmatias/rulepack/commit/0c768452f97a93ddbfccdc406142b9c374dafbe4))

### Features

- **lint**: Run the selected packs' checks and rule tests
  ([`b5c8585`](https://github.com/justmatias/rulepack/commit/b5c85855d98f64db8aec091a46d231d221312c90))

### Refactoring

- **packs**: Use the source resolver directly
  ([`aed36b3`](https://github.com/justmatias/rulepack/commit/aed36b33216828dee3a95f6419869cf838f5537f))

### Testing

- **lint**: Check the error names the broken rule test file
  ([`19cf280`](https://github.com/justmatias/rulepack/commit/19cf2802349ab5807a1f4dad0b607ce4b8087858))

- **lint**: Use the shared CLI fixture for pack tests
  ([`d22f380`](https://github.com/justmatias/rulepack/commit/d22f3802af2c66f96f2ba645fcc384caec645e70))


## v0.9.0 (2026-11-28)

### Bug Fixes

- **packs**: List a commit only for a source that is still git
  ([`35f7848`](https://github.com/justmatias/rulepack/commit/35f784805e90528c22fb081d5790772b6fafb06d))

- **packs**: Validate pins and keep named updates scoped
  ([`e1233cd`](https://github.com/justmatias/rulepack/commit/e1233cd124d72309596fa1c6b9813e4772e84692))

- **packs**: Write the lock with a real TOML writer
  ([`2ba6a9f`](https://github.com/justmatias/rulepack/commit/2ba6a9f4502bdbcbe30b25f5e99f6afedb6cd2d7))

- **packs**: Write the lock with LF line endings on every OS
  ([`9c06e88`](https://github.com/justmatias/rulepack/commit/9c06e88e73951602cb126bd7bf61ce51b0361070))

### Features

- **packs**: Lock, update and list pack sources
  ([`0333222`](https://github.com/justmatias/rulepack/commit/03332221054371f110c54ef32b47a700cfc4fb0c))

### Refactoring

- **config**: Split pack sources into git and path models
  ([`bc72750`](https://github.com/justmatias/rulepack/commit/bc7275049497c1ee5aa1b315b1ce77bb70a8d5ae))

- **packs**: Keep each lock and fetch decision in one place
  ([`7b0444a`](https://github.com/justmatias/rulepack/commit/7b0444a5acbe4462201d085a056914a23cf6e7a4))

### Testing

- Import the git helpers from their shared module
  ([`21a2343`](https://github.com/justmatias/rulepack/commit/21a23430311478d19b171542a48a3c8def483119))

- **packs**: Cover a lock whose ref no longer matches the config
  ([`0c585a3`](https://github.com/justmatias/rulepack/commit/0c585a3c2efeb4aaa42cd6cfc315266024309b74))

- **packs**: Cover a locked commit that no ref points at any more
  ([`c8bebfb`](https://github.com/justmatias/rulepack/commit/c8bebfb22dd7a432dc5b6f5b938cf21612686f22))

- **packs**: Drop an unused argument from the force-push test
  ([`abb1ba4`](https://github.com/justmatias/rulepack/commit/abb1ba43313ab68be5eae9718269e2bc028b78cc))


## v0.8.0 (2026-11-28)

### Build System

- Replace the Makefile with poethepoet tasks ([#35](https://github.com/justmatias/rulepack/pull/35),
  [`8add303`](https://github.com/justmatias/rulepack/commit/8add3032b9cc612d17282c3fcdc7397314da17df))

### Chores

- **ci**: Prepare rulepack releases for PyPI ([#27](https://github.com/justmatias/rulepack/pull/27),
  [`a2089cd`](https://github.com/justmatias/rulepack/commit/a2089cd3197a8dbdc3a8c1a60c85f3ee666b4dd0))

### Documentation

- Describe the commands that work today ([#34](https://github.com/justmatias/rulepack/pull/34),
  [`583c2b2`](https://github.com/justmatias/rulepack/commit/583c2b2b786b4ea663756949ec40a53124b97408))

- Document installing rulepack from PyPI ([#28](https://github.com/justmatias/rulepack/pull/28),
  [`de0da11`](https://github.com/justmatias/rulepack/commit/de0da111b095fa52ed8f675e3ecee2ad36f93008))

- Document rulepack's commands and remove the migration spec
  ([#7](https://github.com/justmatias/rulepack/pull/7),
  [`f4aaca9`](https://github.com/justmatias/rulepack/commit/f4aaca93924c95f807c57156bbff1236f1d44b85))

- Explain why rulepack exists ([#34](https://github.com/justmatias/rulepack/pull/34),
  [`583c2b2`](https://github.com/justmatias/rulepack/commit/583c2b2b786b4ea663756949ec40a53124b97408))

### Features

- **init**: Write poe tasks instead of Make targets
  ([`314b14a`](https://github.com/justmatias/rulepack/commit/314b14a1622d14620fcd3264e766f01fd4194255))

### Breaking Changes

- **init**: `rulepack init --makefile` is gone; use `--poe`.


## v0.7.0 (2026-11-28)

### Features

- **hooks**: Run checks while agents edit with rulepack hook
  ([`ee7526c`](https://github.com/justmatias/rulepack/commit/ee7526c5e5c2eafc56fff5c6cd937c61db02ee53))

### Refactoring

- **hooks**: Check the hook config once before selecting files
  ([`4542e36`](https://github.com/justmatias/rulepack/commit/4542e3612b7419c0c02f1d04ffe95cbc3b2bb97d))

- **hooks**: Handle hook errors once in main
  ([`85facef`](https://github.com/justmatias/rulepack/commit/85facef5dd706d380ce7280fd08f521c5c7b88ac))

- **hooks**: Parse payload paths as Path fields
  ([`963fe87`](https://github.com/justmatias/rulepack/commit/963fe87738731c434b514357d6442c4a9cc8e1a5))

- **hooks**: Validate hook input and name functions by action
  ([`10d3a41`](https://github.com/justmatias/rulepack/commit/10d3a41d24bd202da8cc28ac0971dfd488d9bcb6))

### Testing

- **hooks**: Apply the temp directory isolation with usefixtures
  ([`0b86e7a`](https://github.com/justmatias/rulepack/commit/0b86e7a6c1acdb56db26b2bf7454f86419775f60))

- **hooks**: Give each hook test one behavior and fixture-driven cases
  ([`a4a223f`](https://github.com/justmatias/rulepack/commit/a4a223fe087ebfc957955c6ef14c8bd374b9b318))

- **hooks**: Provide the bare-except source as a fixture
  ([`bdcc48c`](https://github.com/justmatias/rulepack/commit/bdcc48c6d647d0bc14ac71b4a5666264e5457887))

- **hooks**: Share config and unscanned-file setup in fixtures
  ([`e67b1ee`](https://github.com/justmatias/rulepack/commit/e67b1eeede99d1995e31d09e7a8e094cf7f3e1e0))


## v0.6.0 (2026-11-27)

### Documentation

- **specs**: Record the config-only init and close its open question
  ([`3d08a02`](https://github.com/justmatias/rulepack/commit/3d08a023a30421101fae6963aef3a000750576a9))

### Features

- **config**: Default the checks folder to lint/
  ([`9c624fb`](https://github.com/justmatias/rulepack/commit/9c624fb2cdde60c7fd3795c6a75d566774cd0bbb))

- **init**: Ask a person at a terminal whether to keep checks locally
  ([`002975b`](https://github.com/justmatias/rulepack/commit/002975bb788a51a47d0d82ebe35b496f6a2234c3))

- **init**: Write only .rulepack.toml unless --checks-dir is given
  ([`0c95a42`](https://github.com/justmatias/rulepack/commit/0c95a42c915cd7b4c9ca31bd47d16885b8c332f6))

- **lint**: Skip the ast-grep steps when the repo has no local checks
  ([`02a6041`](https://github.com/justmatias/rulepack/commit/02a6041f66629e89e0203252f818ea21f4032902))


## v0.5.0 (2026-11-27)

### Bug Fixes

- **init**: Report a malformed pre-commit config instead of crashing
  ([`a0d3f16`](https://github.com/justmatias/rulepack/commit/a0d3f16949f110bb9eb2ea96ce94855477eb67ed))

### Features

- **init**: Scaffold the rules-as-checks layout with rulepack init
  ([`f4fa135`](https://github.com/justmatias/rulepack/commit/f4fa13520a49ab00ffa8a38e1bc022d9ed94c7eb))

### Refactoring

- **init**: Check the existing layout paths directly
  ([`fc056f5`](https://github.com/justmatias/rulepack/commit/fc056f53a961c8c10e4a8c6c6b5200af82ad230e))


## v0.4.0 (2026-11-26)

### Features

- Publish the checks as pre-commit hooks and a GitHub Action
  ([`aba1b19`](https://github.com/justmatias/rulepack/commit/aba1b19aa8c492485f0aa6f4f629f0bb0902f23d))

### Testing

- Remove the pre-commit hooks tests
  ([`f04f41b`](https://github.com/justmatias/rulepack/commit/f04f41be83d20117db67ab772d751d6740286798))


## v0.3.0 (2026-11-26)

### Features

- **lint**: Run the rule tests, scan and imports with rulepack lint
  ([`7e20ef0`](https://github.com/justmatias/rulepack/commit/7e20ef088fba92cea11482d65fa4bb713099f5c3))

### Refactoring

- **lint**: Name functions for their action and type scan findings
  ([`46f94c7`](https://github.com/justmatias/rulepack/commit/46f94c7f6aa3b9fd4ca9744885742025c538f678))


## v0.2.0 (2026-11-26)

### Refactoring

- Remove the exceptions command
  ([`0cdc857`](https://github.com/justmatias/rulepack/commit/0cdc857e580c18aa8b5824891b665df60d53ebf6))

- **cli**: Import importlib.metadata directly
  ([`c5c5f7d`](https://github.com/justmatias/rulepack/commit/c5c5f7ddc61cc5249e3a759eb589a4705cd80117))

- **config**: Drop the keys that only guards and prose rules read
  ([`811c74c`](https://github.com/justmatias/rulepack/commit/811c74c0f3a28622162f53075facf3f2c43b4932))

- **config**: Read the config file where it is found
  ([`8246789`](https://github.com/justmatias/rulepack/commit/82467892016474432dfdd37896fa2b6ae2fe072e))

- **config**: Split the config module into a package
  ([`6e8f1af`](https://github.com/justmatias/rulepack/commit/6e8f1af45392b03ebe6ee4177db4cfa5d37726a4))


## v0.1.0 (2026-11-26)

- Initial Release
