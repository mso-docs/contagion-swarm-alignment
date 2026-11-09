# Protocol5.1 question-coverage continuation

[Documentation home](README.md) · [Developer guide](DEVELOPMENT.md)


The stopped5.0 live study completed nine development runs. A subsequent response
contained four claims where twelve were required. Its nine completed runs, failed
attempt,137physical calls and2,009.734413seconds remain unchanged and auditable.
No omitted answers are padded, guessed, silently converted to unknown or repaired.

`multidomain_live_v51.py` registers a fresh development/evaluation cohort using the
same catalog, model, digest, five-agent ring, task instructions and two-round own
history. It adds an explicitly versioned output-form contract: every task gets a
schema whose claims array has `minItems == maxItems == question_count`, and whose
question-ID field enumerates exactly that task's IDs. Every prompt also lists the
complete ID checklist and count and requires one claim per question, including an
explicit unknown answer when appropriate. Duplicate/omitted/unknown IDs still fail
the parser with `question_coverage_mismatch`; native schema support is not assumed
to guarantee compliance. Numeric output limits remain explicit and the model
output budget remains2,048tokens.

The new cohort repeats five development cases and nineteen held-out cases, each
under clean, marker and reporting-pressure conditions: **72runs /4,500calls**.
It does not rename old5.0 runs or combine them into a completed5.1matrix. Output
form/reminder changes prevent attributing cross-version differences to model
behavior alone. All original dependent-task, ring-only and semantic-quality
limitations remain.

The previously failed development assignment is scheduled first, clean arm first,
followed by its other two arms and then the remaining domains in their original
order. This is a recorded engineering order amendment to reproduce the known
twelve-question format failure before spending calls on other prechecks. It does
not change held-out case selection or use held-out behavioral outcomes to select
tasks. The first-case preflight therefore exercises the actual prior failure task.

## Original allowance is shared, not reset
<details>
<summary><strong>Expand reference and commands</strong></summary>

Preparation reads and verifies the stopped5.0 state, plan and sealed attempts.
The prior137calls debit the original4,950-call ceiling, leaving **4,813 physical
requests** for the new allocation, including retries. The prior execution time
debits the original48-hour ceiling, leaving **170,790.265587 execution seconds**.
An exclusive immutable parent-budget reservation prevents two fresh allocations
from independently spending the same remainder. Changing the old ledger, cap,
reservation or model/catalog/source blocks validation. A mock parent cannot
authorize real inference. Fresh roots do not create a new lifetime allowance.

```bash
.venv/bin/python scripts/multidomain_live_v51.py prepare \
  --root results/campaigns/multidomain-v51-FRESH \
  --catalog results/benchmarks/multidomain-evidence-v2 \
  --model INSTALLED_TAG --digest DISCOVERED_FULL_DIGEST \
  --parent results/campaigns/multidomain-live-active-20261108

# First registered clean development case only; no extra uncounted smoke calls:
.venv/bin/python scripts/multidomain_live_v51.py run \
  --root results/campaigns/multidomain-v51-FRESH \
  --provider ollama --env-file .env.primary --max-new-jobs 1

# After validating that complete sealed preflight, continue the same schedule:
.venv/bin/python scripts/multidomain_live_v51.py run \
  --root results/campaigns/multidomain-v51-FRESH \
  --provider ollama --env-file .env.primary --resume
```

The preflight pauses as `paused_for_review`; it does not mark the study completed
or rerun the first case on resume. All error recovery remains explicit, with
`--resume --retry-failed` and retained failures/cumulative budget receipts.
Primary lease, thermal/disk/context limits, source freezes and zero hidden retries
are unchanged. No remote configuration, credentials or shared services change.

Plan/state filenames remain `multidomain-live-plan.json` and
`multidomain-live-state.json` within the fresh root. Config and manifest bind the
per-task schema hash, output-contract hash, protocol and token ceiling. Public
export must explicitly support5.1; its rows must not be presented as5.0.

The old observed average was about14.67seconds per physical call, including
controller overhead. At that rate the new4,500-call matrix would take roughly
18.3hours. This is an initial rough estimate, not a promise: answering every
question may increase output time. Update the estimate from the new registered
preflight and subsequent complete runs; cooling, contention and failures add time.

</details>
