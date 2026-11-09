---
name: commit-pr-writing
description: Write or update Git commit messages, pull request titles and pull request descriptions when the user requests a commit, PR, or revision to that metadata. Ground descriptions in the actual diff and completed validation.
---

# Commit and PR writing

Apply whenever committing, opening/updating a PR, or drafting their messages. Read repository instructions and any PR template first. User instructions take precedence. This skill controls writing; it does not authorize staging unrelated work, pushing, merging or deploying.

Inspect the final staged diff for commits and the complete base-to-head diff for PRs. Include untracked files only within the user's authorized scope. Describe the final behavior and purpose; remove abandoned approaches and conversational history.

## Commit messages

Use a concrete imperative subject, at most 72 characters, without a trailing period. Prefer the repository's existing type/scope convention when present. Avoid generic subjects such as “updates,” “fix stuff,” or “WIP.”

For a substantial change, add a short body explaining the problem, resulting behavior, and material tradeoff. Include verified validation when useful. Do not claim tests passed when they are pending or failed. Preserve logically related user work; do not amend, split or rewrite history without authorization or an established repository workflow.

## Pull requests

Use an imperative title, at most 72 characters, that describes the complete change. Keep the title and description current as the branch grows. Honor the repository template. Without one, use:

- Summary: problem and resulting behavior, with only the main changes needed for review.
- Validation: exact checks actually run and observed results; distinguish local results from pending CI.
- Limitations: material gaps, operational requirements, rollout/deployment status or untested behavior. Say “None identified” only when supported.

Scale the description to the change. A simple change needs only a few sentences. A larger PR benefits from the three sections above and short parallel bullets. Use plain language; avoid promotional claims, unrelated detail, invented issue references and misleading checklists.

Research repositories: distinguish mock tests from empirical inference, interrupted attempts from complete runs, and measured outcomes from hypotheses. Never call task compliance general alignment, agreement collusion, or a reference checkpoint the deployed model's internals. Exclude secrets, private hostnames and raw sensitive traces from messages and screenshots.

## Before submission

Recheck wording against the staged/base-to-head diff and current evidence. Run required repository checks; record remaining failures candidly. Use structured tool arguments or a body file for multiline text. If asked for a draft PR, create/keep it draft and open; do not merge or publish it. Report the commit identifier, PR link and any material pending checks.
