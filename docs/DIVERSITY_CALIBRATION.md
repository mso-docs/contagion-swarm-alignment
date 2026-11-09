# Model, role and topology calibration

Protocol `6.0-model-topology-calibration` is a new, development-only allocation.
It does not edit the active5.1 controller or change its model, task or budget.
The following installed primary tags/digests were observed through a read-only
inventory request; there were no model pulls, chat calls or service changes:

| Registered group | Installed model | Digest prefix |
|---|---|---|
| Qwen3.5-tagged | `qwen3.5:4b` | `2a654d98e6fb` |
| LFM3-tagged | `lfm3:1.7b` | `b36a103fe2f8` |
| Nemotron3.5-tagged | `nemotron-3.5-bolt:e4b` | `69f2be39b309` |

Full pins are in `configs/diversity_models.example.json`. These are descriptive
model-tag groups, not proof of independent architectures/training lineages. Sizes,
quantization and training data co-vary with names. Installed availability does
not establish task/schema compatibility, which must be measured in the prechecks.

## Compact calibration first

All cases use the same development task, initially the twelve-question humanities
case `bbh-formal_fallacies-0`. Every agent must answer every question. The fixed
question-count/ID schema and no-padding parser come from frozen5.1 helpers.

| Stage | Composition | Graphs | Arms | Runs | Calls |
|---|---|---|---|---:|---:|
| Homogeneous integration | Five agents from each of three model groups | ring, star, complete | clean, marker |18|270|
| Heterogeneous pilot | Two Qwen, two LFM, one Nemotron | ring, star, complete | clean, marker |6|90|
| Optional role cohort | Same mixed composition, distinct review emphases | ring, star, complete | clean, marker |6 per rotation|90 per rotation|

Default: **24runs /360calls**, three rounds per run, five isolated logical agents.
All homogeneous integrations must complete, and each group must produce at least
one clean non-unknown answer citing existing evidence, before mixed calls begin.
This is a structural feasibility gate, not reference correctness or a requirement
for compliant behavior. A malformed response stops subsequent calls and records
the responsible model group. Failure on this task is not universal model incapacity.
The controller never silently repairs an output, changes models or retries it.

Primary comparisons use identical role instructions. `--roles` adds a separately
labeled cohort with proposer, critic, evidence-auditor, checker and synthesizer
emphases. These roles grant no tools, permissions or reduced question coverage.

## Assignment counterbalancing

The default one-rotation pilot establishes initial compatibility; it cannot
separate a model from its particular source/node position. `--rotations 5` keeps
the same assignment across topologies and conditions within each seed and cycles
the mixed models across all five nodes between matched seeds. Every node/source
then hosts Qwen twice, LFM twice and Nemotron once. Roles rotate with a different
offset so they are not permanently attached to model slots.

Five rotations produce48runs/720calls without roles, or78runs/1,170calls with
the separate role cohort. Homogeneous controls remain first-seed compatibility
checks; they are not fully matched five-seed capability estimates. Additional
registered homogeneous seeds would be required for that stronger comparison.

Graph degrees and delivered-message counts differ across ring/star/complete,
particularly when the injection source is the star center. These are not
exposure-matched topology effects. Repeated cases, rounds, agents and seeds are
dependent. No general model ranking, intentional deception, collusion or neural
mechanism is established by this single-task calibration.

## Guarded execution

`scripts/diversity_calibration.py` discovers and verifies relevant model/digest
pins at each cohort boundary. Each request uses its assigned model and records
the per-agent model identity, role, invocation order, raw response and actual
routing. The original task plus two own previous rounds and incoming peer notes
are retained; another agent's private history and hidden targets are excluded.

Requests are serialized under the shared primary lease. Context/output/history,
physical-call, per-run, wall-clock, disk and thermal bounds remain enforced.
Native Ollama requests have no hidden retries. Model load/switch latency is
recorded in run time. Shared Ollama cache/parallelism settings are never tuned;
no extra model replicas, services, credentials or network targets are created.
Failed attempts and conservative unsealed reservations remain on explicit resume.

```bash
.venv/bin/python scripts/diversity_calibration.py prepare \
  --root results/campaigns/diversity-FRESH \
  --catalog results/benchmarks/multidomain-evidence-v2 \
  --model-pins configs/diversity_models.example.json \
  --task-id bbh-formal_fallacies-0 \
  --after results/checkpoint-gates/diversity-interlude-FRESH/handoff.private.json \
  --roles \
  --max-hours 4
```

Plan/state names are `diversity-plan.json` and `diversity-state.json`. Model and
role identities are explicit in each sealed run config, event metadata and
manifest. This protocol needs its own public schema; do not cast mixed identities
into a single-model5.1 row or claim a dashboard deployment from mock validation.

## Early operator interlude

The optional new `scripts/diversity_interlude.py` waits for the active5.1 plan's
registered development matrix to finish, with a two-hour wait ceiling. It writes
an owned operator STOP marker, waits for terminal/sealed evidence and grants a
distinct administrative handoff to the bounded calibration. A racing inference
request can finish first; any interrupted attempt is preserved and debited.

```bash
.venv/bin/python scripts/diversity_interlude.py prepare \
  --root results/checkpoint-gates/diversity-interlude-FRESH \
  --current results/campaigns/multidomain-v51-recovered-20261108 \
  --calibration results/campaigns/diversity-FRESH \
  --chain results/connection-recovery-20261108/v51-chain.private.json \
  --report-observer results/reports/primary-large-post-diversity-20261108 \
  --wait-minutes 120 --interlude-minutes 240
.venv/bin/python scripts/diversity_interlude.py run \
  --root results/checkpoint-gates/diversity-interlude-FRESH
```

The calibration has a four-hour interlude ceiling; a STOP is requested five
minutes before it, allowing bounded requests to seal. At the ceiling, only the
owned local controller process group may be terminated, preserving uncertain
attempts for conservative accounting. No remote inference service is killed.

After the independent calibration finishes—even if a model fails its format
check—the helper archives only its own STOP bytes and explicitly resumes5.1 with
retained-attempt/budget receipts. It also explicitly resumes cascaded stopped
successors only when their new allocations still have zero calls/completions/
failures. Each successor must record an active state before the next starts,
preventing a race against stale stopped prerequisites. An optional freshly
prepared3.7 report observer starts afterward, once, rather than restarting an
already-consumed stopped observer. It never overwrites a different operator's STOP or retries unrelated
current-study failures without review. Unsupported diversity results remain
stopped and visible rather than being relabeled successful.

The helper's append-only hash-linked decision log and source hashes describe
operator actions, not authenticated human authorship or externally anchored
tamper-proofness. Its `completed` state means handoff/restoration finished, not
that any scientific matrix passed. No automatic large-scale expansion follows.
Existing paper freezes and completed scientific evidence remain unchanged.
