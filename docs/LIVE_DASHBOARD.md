# Keep the dashboard current

[Documentation home](README.md) · [Developer guide](DEVELOPMENT.md)

**Current mode: frozen snapshot.** Collection is closed. The submission client
does not poll collectors, and the local collector refuses to start while the
final manifest exists. The commands below describe the earlier live workflow;
they are not instructions to resume submitted allocations.

For normal use, follow [Dashboard usage](DASHBOARD.md) or
[preview the final snapshot](FINAL_DASHBOARD_SNAPSHOT.md).

```mermaid
flowchart LR
    F["Frozen public files"] --> V["Validate hashes and privacy"]
    V --> L["Local preview"]
    V --> G["GitHub CI and Pages"]
    L --> B["Interactive browser views"]
    G --> B
    classDef blue fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef purple fill:#ede9fe,stroke:#7c3aed,color:#2e1065
    classDef green fill:#dcfce7,stroke:#15803d,color:#14532d
    classDef amber fill:#fef3c7,stroke:#d97706,color:#78350f
    class F blue
    class V amber
    class L,G purple
    class B green
```

<details>
<summary><strong>Earlier live synchronization and troubleshooting</strong></summary>

## Recommended: one automatic local service

```bash
.venv/bin/python scripts/serve_dashboard.py --sync-secondary
```

Open **http://127.0.0.1:8765/**. This serves only allowlisted public assets on loopback,
discovers sealed local studies every 15 seconds, and optionally fetches sanitized secondary
snapshots every minute into ignored staging before merging them atomically. No primary access,
inference, Git push or Pages deployment occurs. Do not run another exporter or static server on
the same port/output concurrently.

The main overview and model/evaluation/trace/dataset views share legacy and newer indexed runs.
The old 20-run total is only one historical cohort. Mock evidence remains separate; unrecorded
metrics show N/A. Asset changes trigger local reload and responses prevent caching. A local
status line reports synchronization health; blocked updates retain the previous valid
projection. Unsealed active attempts wait for their checksum seal; use the private progress tool
for in-flight work.

Public GitHub Pages remains a reviewed, push-triggered snapshot. An unavailable secondary or its
slower export cadence can delay remote results; the local status reports synchronization
failure. The service does not promise instantaneous or offline remote updates.

The manual workflows below remain useful for troubleshooting while the automatic service is stopped.


The dashboard reads static, sanitized files. It never contacts Ollama or SSH. A fresh browser
fetch cannot discover private runs until an exporter publishes them.

```mermaid
flowchart LR
    A["Local controller"] --> B["Sealed local attempts"]
    B -->|"watcher: every 15s"| D["Validated public snapshots"]
    R["Secondary suite"] --> S["Remote sanitized snapshot"]
    S -->|"operator suite-sync"| D
    D -->|"browser: every 60s or Refresh"| L["Local dashboard"]
    D --> V["Review + commit + push"]
    V --> C["Security checks + Pages build"]
    C --> P["Public dashboard"]
    classDef private fill:#ede9fe,stroke:#7c3aed,color:#2e1065
    classDef safe fill:#dcfce7,stroke:#15803d,color:#14532d
    classDef display fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef gate fill:#fef3c7,stroke:#d97706,color:#78350f
    class A,B,R private
    class S,D safe
    class L,P display
    class V,C gate
```

## Local study results

Run one watcher for the public output. Do not run it concurrently with remote `suite-sync` or
another exporter writing the same snapshot.

```bash
.venv/bin/python scripts/watch_dashboard.py --study results/studies --interval 15
```

Use repeated `--study PATH` arguments to select narrower sources. Only protocol-2 attempts with
manifests, config snapshots and checksum seals are considered. Integrity failures block that
update and retain the previous public index. Existing approved study rows, monitor results,
neural captures and suite telemetry are preserved; rows with the same run ID are refreshed.
Operational suite status and hardware telemetry are private; use the [terminal progress
monitor](PRIVATE_PROGRESS.md). The public page shows collected research evidence only. Unchanged
data does not advance the export timestamp.

Summary-only export is the default. Add `--include-text` for bounded, scrubbed task and response
details. This does not publish full request histories or raw logs. Review text before
committing; pattern scrubbing cannot guarantee anonymity. An interrupted watcher can be
restarted; Ctrl-C stops only the exporter.

For one update:

```bash
.venv/bin/python scripts/watch_dashboard.py --study results/studies --once
.venv/bin/python scripts/export_research.py --validate-only
```

## Remote suite results

The detached secondary worker publishes its own sanitized snapshots periodically. Fetch them
explicitly when the local watcher is stopped:

```bash
.venv/bin/python scripts/remote_worker.py suite-status --server secondary
.venv/bin/python scripts/remote_worker.py suite-sync --server secondary
```

Synchronization replaces the research snapshot with the remote version. Restarting the local
watcher merges selected local studies back into that snapshot. These commands do not access
primary. The large suite remains paused until checkpoint validation is complete; syncing does
not resume inference.

## Which count am I seeing?

| View | File | Meaning |
| --- | --- | --- |
| Legacy source for unified views | `data/results.json` | Original RQ1 export; merged with newer studies by the frontend |
| Scenarios & review, Neural captures | `data/research.json` | Newer studies, reviews, monitors, measurements and suite telemetry |
| Clicked benchmark row | `data/studies/<id>.json` | Bounded task and trace detail, if exported |

The local dashboard polls all result indexes every 15 seconds; the public static dashboard
checks every 60 seconds. Returning to the tab refreshes immediately. Research rows and trace
choices show newest timestamps first. Source failures remain visible while the last valid
results stay available. Use **Reset filters** to restore all cohorts.

The local server reads its ignored `results/dashboard-live/data` cache. Git checkout and
pre-commit stashing cannot rewind that cache. Sealed, validated runs enter automatically; active
calls appear separately in the private collector strip. Monitor cells count analysis
projections, not experiments, and update when offline analysis completes.

Create a privacy-validated checkpoint for review and commit with:

```bash
.venv/bin/python scripts/export_live_dashboard.py
```

This copies only approved result indexes and referenced sanitized details into `dashboard/data`;
it does not stop inference, publish private progress, push, or deploy. The all-task analysis
notebook reads the live cache when available and falls back to the tracked checkpoint.

## Public Pages

Review and push the sanitized snapshot and referenced detail files. Pages updates after the
main-branch security/build workflow succeeds. It does not stream from private servers, and a
running local watcher does not push or deploy anything.

If results look stale: check the correct view, verify the attempt is sealed, inspect exporter
output, validate the snapshot, then check the latest Pages build. Never copy private raw results
into the website to bypass an export failure.

</details>
