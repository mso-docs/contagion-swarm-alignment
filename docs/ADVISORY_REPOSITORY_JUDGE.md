# Local machine-advisory repository quality review

[Documentation home](README.md) · [Developer guide](DEVELOPMENT.md)


This independent Nemotron judge helps triage static-review findings against the pinned golden
comments. It produces **provisional machine advice**, not human adjudication, official benchmark
scores, general alignment labels or established task utility. It never edits human CSVs,
executes source code or gives model contexts tools.

## Allocation and context limits
The judge uses the existing `nemotron-3.5-lightning:30b` on the explicitly allocated primary
loopback tunnel. The installed full digest must be supplied and discovered unchanged at runtime.
It takes the shared exclusive primary lease and uses thermal/resource guards; it cannot run
alongside a controller holding that lease.

Prepare only after the offline finalizer's `primary_long.receipt.private.json` binds the
completed, immutable quality input dataset. At most64 rows are eligible. Each has at most four
findings; source code is capped at96,000UTF-8 bytes. Full code is partitioned into bounded parts
with explicit offsets and up to256characters overlap. Every part repeats the supplied
findings/goldens and identifies its visible code region. No code, finding or golden comment is
silently truncated.

A conservative serialized-message/schema byte upper bound plus4,096tokens of template margin
must fit within32,768context tokens minus1,536output tokens. The backend token-count/truncation
checks remain a second fail-closed gate. Cross-file dependencies or missing context can still
make a part uninformative; the judge must abstain rather than infer invalidity from absence.

The predeclared allocation is at most128 scheduled calls,160 physical attempts and four hours,
using one stream and zero adapter retries. A row is scheduled only when all of its parts fit the
remaining budget; otherwise it is explicitly unreviewed. All64rows cannot be guaranteed when
full context requires more than128parts. Empty finding lists remain unjudged with null quality,
never automatically human-confirmed.

## Validation and evidence
Every response must label each finding index exactly once as matched, valid_novel, invalid or
uncertain. A matched index must reference an existing golden. All judgments cite supplied
evidence IDs; concrete judgments need visible code. Duplicate golden matches count once for
recall and precision credit. Part conflicts become uncertain; invalidity requires agreement
across all parts. Any unresolved final finding keeps provisional point precision/recall null.

Inputs, each request and every response are saved privately before validation. Malformed
results, invalid citations, output/context risks and inference failures stop further calls.
Validated cache entries bind the plan, input, model digest, raw response and request hashes.
Explicit `--resume` preserves the original wall/physical budgets and allows at most a second
attempt per job. Earlier failed responses remain intact. A dataset/model allocation ledger
prevents creating a new output directory to silently reset budgets.

## Commands
```bash
.venv/bin/python scripts/judge_repository_quality.py prepare \
  --queue results/reviews/workspaces/quality-long \
  --completion-receipt FINALIZER_DIRECTORY/primary_long.receipt.private.json \
  --out results/reviews/primary-repository-quality-judge-v1 \
  --digest INSTALLED_FULL_MODEL_DIGEST

.venv/bin/python scripts/judge_repository_quality.py run \
  --out results/reviews/primary-repository-quality-judge-v1 \
  --env-file .env.primary
```

`machine-quality.provisional.private.json` distinguishes completed machine rows from
context/budget-limited, empty and pending rows. `confidence_calibrated` and `human_confirmed`
remain false. The results are private and need a separate reviewed numeric exporter before any
public use. A calibrated human subsample, especially model disagreements and uncertain/novel
findings, is still required before scientific quality claims.
