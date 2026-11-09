# Secondary telemetry environment recovery

Protocol3.8 completed three runs /45responses before the next run stopped after
two valid responses. The next inference request had no HTTP attempt. Its sealed
manifest reports a controller-side `ValueError`, with zero parse failures. An
independent operator reproduction identified the strict shared `.env` loader:
an unrelated cloud-provider assignment in that file was rejected during a
read-only SSH capacity probe. No credential value is required to diagnose or fix it.

`secondary_env_recovery.py` isolates that operational configuration boundary.
It reads assignment keys first and parses only `SECONDARY_SERVER_ID` and
`SECONDARY_PROJECT_DIR`. Other values are never parsed, copied or logged. Explicit
inherited overrides for those two SSH settings preserve existing configuration
precedence; inherited cloud-provider keys are excluded. The original environment
files are never edited. A new private `telemetry.env` contains only those two
quoted settings, has mode0600 and is hash-bound into the new registration. Every
capacity probe verifies that snapshot before passing its path to
`remote_worker.execute('secondary', 'capacity', snapshot)`. Inherited SSH drift
blocks the probe instead of silently changing its target.

The frozen scientific runner remains `secondary_review_v38.py`, protocol
`3.8-repository-bounded-output`. Task prompts, response schema, model/digest,
3,072-token output cap, seeds, topologies and full-history policy are unchanged.
Inference still uses the separate `.env.secondary` native-Ollama endpoint; the SSH
telemetry snapshot does not contain inference credentials or cloud-provider keys.
This is an operational continuation, not a new scientific intervention or paid
inference path.

The composite raw ledger now retains15completed runs and three failed attempts.
It charges677physical requests:625from3.1, five from3.5 and47from3.8. The21unfinished
assignments require895scheduled calls;923requests remain under the original1,600cap.
The partially attempted assignment is retried as a fresh sealed attempt, while
completed assignments are skipped. The plan records a supplemental12-hour execution
allowance, a unique parent-budget reservation and the ancestor evidence hashes.
No prior bytes, failed-attempt denominator or physical debit are erased.

```bash
.venv/bin/python scripts/secondary_env_recovery.py prepare \
  --parent results/campaigns/secondary-bounded-recovery-20261108 \
  --root results/campaigns/secondary-isolated-recovery-FRESH \
  --telemetry-env-source .env --supplemental-hours 12

.venv/bin/python scripts/secondary_env_recovery.py run \
  --root results/campaigns/secondary-isolated-recovery-FRESH \
  --provider ollama --env-file .env.secondary
```

The plan is `secondary-isolated-plan.json`; private progress is
`secondary-isolated-state.json`. The isolated SSH snapshot is exactly
`results/campaigns/secondary-isolated-recovery-FRESH/telemetry.env` and can be supplied
to the dashboard's separate secondary SSH configuration option. Raw run logs
remain under `results/repository-runs/secondary-isolated-recovery-FRESH`. Keep
operational-release identifiers and cumulative failed attempts when analyzing
these completed subsets. Simulated agents receive no telemetry settings, tools,
network access or environment data.
