# Private experiment progress

Use the terminal monitor on your laptop or on an experiment computer. It reads files or polls the secondary over existing SSH; it makes no inference calls, starts no web server and never exports public dashboard data.

## Secondary status from your laptop

```bash
.venv/bin/python scripts/experiment_progress.py --remote secondary
# Keep refreshing; Ctrl-C stops only the monitor:
.venv/bin/python scripts/experiment_progress.py --remote secondary --watch --interval 30
```

The SSH reader only reads project queue/plan/manifest files. It does not restart jobs or touch Ollama. Existing host-key verification and passwordless authentication are required. Primary is deliberately excluded from remote polling while it is reserved for another operator.

## On either experiment computer

From its project checkout and Python environment:

```bash
.venv/bin/python scripts/experiment_progress.py --suite results/secondary-suite --watch
```

Use the actual suite directory on that computer; the name does not select a server. Relative plan paths resolve from the project working directory. A CPU/neural-only environment can use its installed Python in place of `.venv/bin/python`. Local reads do not need network access. This implementation has not installed or started a monitor on either server.

For standalone batches, repeat selected roots and supply the frozen planned totals when known:

```bash
.venv/bin/python scripts/experiment_progress.py \
  --study results/studies/value-check-catalog-24 \
  --study results/studies/value-check-provenance-24 \
  --study results/studies/value-check-patch-24 \
  --planned-runs 6 --planned-calls 60 --watch
```

You can combine local studies, local suites and `--remote secondary` in one view. Local overlapping roots are deduplicated. Missing plan totals show **unknown**, not guessed completion percentages. `--json` provides machine-readable private status; if saving it, use an ignored location such as `results/private-progress/status.json`.

## Reading the numbers

| Metric | Meaning |
| --- | --- |
| Sealed runs | Completed plus failed/exhausted attempts; failed attempts are not successful experiments |
| Unsealed runs | Locally detected unfinished or abandoned attempts, not proof that a process is alive |
| Attempted calls | Recorded physical HTTP attempts, including retries; mock runs make zero HTTP attempts |
| Recorded run time | Sum of recorded run durations; excludes gaps, paused time and unfinished-run duration; not GPU-hours |
| Elapsed window | Historical first-to-last timing, or the suite's recorded wall budget; can include gaps/pauses |
| Throughput | Returned calls per recorded run minute |
| Remaining / total work estimate | Remaining scheduled calls divided by observed throughput; total adds recorded run time |
| Finish estimate | Only shown for a running state updated within five minutes; assumes uninterrupted execution |

ETA is a rough projection, especially across different models, tasks and swarm sizes. It includes neither future pauses nor all non-inference stages. A paused worker still has a remaining-work estimate but no calendar finish promise. Failed runs count as consumed attempts; any planned reruns require revised totals. Counters can lag an active run until its checkpoint is written. A monitor cannot establish process liveness from old state alone.

## Privacy and publication

Operational queue status, planned budgets, ETA and hardware telemetry belong in private operator tools. The public research exporter omits queue/hardware fields; remote sync strips old worker telemetry; staged-file and Pages build guards reject populated operational fields. Existing public research outcomes, counts of collected evidence and per-run runtimes remain available as scientific results.

Runtime status remains under ignored `results/`. The terminal view prints numeric counters and fixed labels, not endpoints, paths, credentials or trace content. Its source and these instructions may be committed; its runtime output is not a public data source.

Frozen campaign controllers are supported directly:

```bash
.venv/bin/python scripts/experiment_progress.py --campaign results/campaigns/heldout-v26-20261108 --watch
.venv/bin/python scripts/experiment_progress.py --campaign results/campaigns/overnight-v26-20261108 --watch
```

The overnight supervisor records its earlier repository-checkpoint phase in the private `overnight.json` beside the campaign freeze. Synthetic progress starts after those checkpoints pass. Remaining-work estimates use completed scheduled calls, preserving retry overhead as overhead rather than claiming it completed new conditions.
