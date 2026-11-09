# Dependency updates and human review

[Documentation home](README.md) · [Developer guide](DEVELOPMENT.md)


The user authorizes merging safe Dependabot-only maintenance after review and green checks.
Application, experiment, report and dashboard implementation remain subject to human review in
the open draft PR.

Reviewed action upgrades: checkout7.0.1, Pages artifact upload5.0.0 and Pages deployment5.0.1,
all pinned to verified official commits. Dependabot PRs#1,#2,#3 were reviewed and merged; stale
setuptools audit failures in#1/#3 were resolved by incorporating current main and rerunning
checks before merging. No failed check was bypassed.

The proposed automatic workflow merges only genuine `dependabot[bot]` PRs from this repository
targeting main, with successful current-head security checks and a diff restricted to already
reviewed immutable action pins in the two allowlisted workflows. Changes to application code,
permissions, runner commands, unknown packages or unreviewed versions are rejected. It never
checks out or executes PR code in the privileged merge job. The merge API binds the expected
head SHA to prevent merging a changed revision.

New versions, including future major upgrades, need review before adding their exact pins to the
allowlist. The automation itself is implementation code and stays in the human-reviewed draft
until merged; it is not enabled by this branch alone.

Dependabot-generated descriptions are exempt from the human/agent PR-writing template check;
security, tests and publication gates still run. Human-authored implementation PRs retain the
writing requirement. This avoids blocking safe bot maintenance merely because its generated body
uses a different format.
