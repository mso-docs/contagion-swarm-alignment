# Primary output-budget amendment

The original protocol3.3 allocation preserved42completed runs and one failed
transport attempt. Its first explicit transport continuation completed one further
75-response run, then stopped after10responses in the next run: the final response
ended at the1,536-token output ceiling, leaving nine parsed artifacts. Connection
health was restored; this later failure is a different output-budget condition.

`primary_output_recovery.py` validates both ancestors and their sealed evidence.
The composite ledger contains43completed original assignments, two retained failed
attempts and3,011physical requests. The25unfinished assignments require1,875calls;
at most2,189further physical requests are available under the original5,200cap.
Every new request and failure is charged to that remaining authorization.

The new runner is protocol `3.6-repository-output-budget`. It logs and requests
3,072output tokens, reserves the corresponding32,768−3,072context margin and closes
unbounded extra answer fields. Findings and execution claims retain their original
contracts; the optional audit marker is explicitly allowed by the schema with an
80-character bound so unauthorized adoption remains observable. The task/system
objectives, source-attribution condition, seeds, graph routing and full own history
are unchanged. A new system-format instruction explicitly states numerical field
limits, a4,000-character report limit and no copied source or peer transcripts.
This additional format instruction is an experimental amendment. The96,000-byte
history limit still stops rather than evicts.

These output/schema amendments create a distinct cohort. Only unfinished
assignments are included, so the resulting3.6sample is not a balanced new factorial
study. Do not pool it silently with completed3.3conditions or remove either prior
failed attempt. Any completion/analysis across allocations must use the recorded
new-to-original assignment mapping and disclose the amendment and dependence.

```bash
.venv/bin/python scripts/primary_output_recovery.py inspect \
  --continuation results/campaigns/primary-long-continuation-20261108

.venv/bin/python scripts/primary_output_recovery.py prepare \
  --continuation results/campaigns/primary-long-continuation-20261108 \
  --root results/campaigns/primary-output-recovery-FRESH \
  --supplemental-hours 8 \
  --after results/campaigns/REGISTERED-PREREQUISITE/STATE.json

.venv/bin/python scripts/primary_output_recovery.py run \
  --root results/campaigns/primary-output-recovery-FRESH \
  --provider ollama --env-file .env.primary
```

Registration takes only the stopped ancestor's queue lock and a unique reservation
for its remaining authorization. It does not acquire the primary inference lease,
so an unrelated registered allocation may continue uninterrupted. The optional
immutable prerequisite is checked before acquiring the primary lease, with a
96-hour wait ceiling. Its stopped/failed state blocks launch; completion permits
the next lease acquisition. A separately registered supplemental eight-hour
execution allowance begins after lease acquisition, retains previous execution
debits and never rewrites prior wall limits or states.

Live execution checks the pinned model/digest/readiness, primary loopback endpoint,
RAM, thermal telemetry, disk, cumulative calls and wall time. It verifies ancestor
state hashes before calls, so an attempt to resume an old ancestor blocks new
collection. New failures stop later calls and seal the current attempt. Explicit
resume/retry decisions append private receipts; unsealed or corrupt attempts block
resumption. No model networking, tools, upstream execution or service changes are
introduced. Public export requires a closed protocol3.6 schema and separate cohort
labels; raw histories remain private.
