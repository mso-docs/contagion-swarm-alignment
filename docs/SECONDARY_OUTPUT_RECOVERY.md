# Secondary output-budget recovery

[Documentation home](README.md) · [Developer guide](DEVELOPMENT.md)

**Historical operations reference.** Collection is closed. Commands and status
notes below describe their recorded checkpoint; use the [final catalog](EXPERIMENT_CATALOG.md)
for completed evidence. Do not resume allocations from this page.

<details>
<summary><strong>Full reference</strong></summary>

The protocol3.1 secondary long-horizon allocation stopped after12completed runs.
The last incomplete attempt returned five responses but only four parsed artifacts:
its last response ended with `done_reason=length` at the1,536-token output ceiling.
The prompt contained5,855tokens, so this was output truncation rather than the
32,768-token context ceiling. No operator `STOP` file was present.

Authoritative raw logs contain625physical requests. The old pair-level queue
reported620 because it did not add the incomplete pair's five responses. Recovery
charges all625. It preserves the12completed attempts and the incomplete attempt.
There are24unfinished condition assignments /940scheduled responses, with975
requests available under the original1,600-request physical authorization.

`scripts/secondary_review_v35.py` registers a distinct
`3.5-repository-output-budget` cohort. It retains task instructions, response
schema, task inputs, seeds, graph routing and full own conversation history, but
raises the output allowance to3,072tokens. The actual request, configuration,
manifest and context-margin check all record that new allowance. History remains
bounded at96,000bytes; reaching that bound stops collection instead of truncating
the context. New truncation, parsing, integrity, resource or transport failures stop
later assignments and retain their sealed evidence.

This amendment is a changed experimental condition. Do not silently merge
protocol3.5 outcomes with protocol3.1 or present the recovered assignments as a
balanced3.5 comparison: completed old conditions are intentionally not repeated.
Quality remains unadjudicated, and a failure is not evidence of deliberate cheating.

```bash
.venv/bin/python scripts/secondary_recovery.py inspect \
  --parent results/campaigns/secondary-long-horizon-recovery-v31-20261108

.venv/bin/python scripts/secondary_recovery.py prepare \
  --parent results/campaigns/secondary-long-horizon-recovery-v31-20261108 \
  --root results/campaigns/secondary-output-recovery-FRESH \
  --supplemental-hours 8

.venv/bin/python scripts/secondary_recovery.py run \
  --root results/campaigns/secondary-output-recovery-FRESH \
  --provider ollama --env-file .env.secondary
```

Registration creates a unique parent-budget reservation, source freeze, explicit
supplemental eight-hour wall allowance and a lineage receipt binding the old raw
seals/counters. It never modifies or deletes the old plan, state or evidence.
The live controller requires the existing loopback endpoint, exact discovered
model/digest and original readiness, acquires the secondary controller lease and
checks RAM, thermal sensors and disk before requests. Only the controller performs
inference and read-only capacity probes. Simulated agents remain tool-free.

Failed recovery attempts require explicit `--resume --retry-failed`, with a new
private decision receipt and cumulative request/time debits retained. Unsealed or
corrupt recovery attempts block this path until independently reviewed. Public
dashboard integration must explicitly support the new protocol before publishing
its closed numeric summaries; raw request histories remain private.

</details>
