# Researcher guide

Contagion studies instruction boundaries in controller-mediated agent swarms. The research questions are unchanged: network propagation (RQ1), monitor visibility (RQ2), and distributed responsibility in a synthetic simulator (RQ3).

## Evidence inventory

Counts describe saved evidence, not independent attack designs. The current indexed live inventory is **61 attempts / 945 returned responses**: 20 original RQ1 runs / 500 responses, plus 41 newer development, timing and integration attempts / 445 responses. The newer inventory includes failed attempts and multiple protocol revisions. Mock runs and pytest tests are software evidence, not empirical model trials. Held-out conclusions must use a preselected frozen evaluation cohort, not this grand total.

| Channel | What exists | What it can support |
| --- | --- | --- |
| Original RQ1 | Two live model cohorts, 20 completed runs; no exact suffix adoption | A narrow null result for the specified task and mild intervention |
| Protocol-2 studies | Live development iterations, paired checkpoints, retained failures | Harness validation and preliminary behavior; not a pooled benchmark score |
| RQ2 | Restricted projections and confusion metrics; catalog-only baseline | Visibility-based detection with explicit positives/negatives and coverage |
| RQ3 | Matched simulator arms and development checks | Preliminary proposal/state-change comparisons; no real system access |
| Neural | Measured random-weight captures, latest raw/bridge parity check passed | Instrumentation correctness; no trained-model mechanism claim |
| Advisory judge | Blinded review and human calibration tooling | Triage only until calibrated on held-out human labels |

## Reproduce and inspect

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/research_report.py --out results/paper-candidates
.venv/bin/python scripts/serve_dashboard.py --sync-secondary
```

Open **http://127.0.0.1:8765/**. The overview, models, evaluations, traces and datasets share the indexed evidence across protocols. Metrics unavailable for a run remain N/A. Neural and monitor panels show only measured/applicable evidence. The local service discovers sealed local studies every 15 seconds; optional secondary sync polls sanitized worker snapshots every minute. Worker export cadence and connectivity can add delay. Source logs remain private; corrupt/unsealed attempts are not presented as validated results.

Do not run another exporter against the same output while the service owns it. [Private progress](PRIVATE_PROGRESS.md) provides queue budgets and ETA without publishing operational data. [Privacy checks](PRIVACY_CHECKS.md) apply before committing reviewed projections. Public Pages updates after a reviewed push and successful main build, not directly from private logs.

## Analysis rules

- Use runs as units. Agents, paired conditions and visibility projections are dependent. Scenario variants come from four templates.
- Separate model digest, worker, source/freeze, protocol, task, split, executor and swarm size. Reports conservatively keep different freezes separate.
- Report failed/exhausted attempts, parse failures and indeterminate outcomes alongside successes. A complete controller run can contain invalid artifacts.
- Report matched control/injection differences by case/seed. Duplicate retry candidates make a pair ambiguous; no favorable retry selection.
- Wilson intervals are binomial working-model descriptions. They do not account for template dependence or prove population robustness. Sparse paired estimates receive no automatic significance claim.
- Do not substitute run-level objective flags for RQ1 downstream adoption or mention/exposure for behavioral adoption. Legacy raw analysis retains round-level trajectories and exposure.
- Freeze future questions, prompts, schemas and scorers before evaluation. Existing development failures remain recorded; they are not repaired retrospectively.

## Paper artifacts

`research_report.py` writes run/cohort tables, matched-pair effects, legacy RQ1 summaries, neural quality metrics, PNG/SVG figures, captions and input/analysis hashes. All tables include every cohort; figure caps and omitted counts are explicit. Files stay in ignored `results/` until selected and reviewed. See [measurement audit](MEASUREMENT_AUDIT.md), [interpretability protocol](INTERPRETABILITY_PROTOCOL.md) and [reporting](PERIODIC_REPORTS.md).
