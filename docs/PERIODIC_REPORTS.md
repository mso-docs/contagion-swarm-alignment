# Reproducible research reports

```bash
.venv/bin/python scripts/research_report.py --out results/paper-candidates
```

This reads validated snapshots without inference and writes `report.md`, `runs.csv`, `cohort_summary.csv`, `paired_effects.csv`, `legacy_summary.csv`, `neural_quality.csv`, `evidence.json`, a figure catalog, and PNG/SVG figures. `evidence.json` records input/analysis hashes, limitations and omitted figure counts. `--max-cohort-figures` limits plots, not tables. The suite also calls the reporter at publication checkpoints; its remote release must be updated before it uses newly added analysis code.

Reports separate frozen model/backend/digest/worker/protocol/task/split/executor cohorts. Run/seed is the unit, with conditions paired and template variants dependent. Unknown/failed attempts and parse errors remain in denominators and coverage columns. Duplicate retry candidates are not arbitrarily selected for paired effects. Wilson intervals are binomial working-model descriptions, not cluster-adjusted population confidence. Sparse paired comparisons are descriptive only.

Neural figures use measured activations and patch controls. Normalized restoration is undefined for tiny baseline gaps or failed no-op controls. No generated reasoning is treated as activations, no named SAE meanings are assumed, and random weights remain instrumentation evidence. See [interpretability protocol](INTERPRETABILITY_PROTOCOL.md).

Use `notebooks/report_workbench.ipynb` for interactive selection; optional `.[analysis]` supplies pandas/seaborn/Jupyter. Matplotlib and stdlib tables work without these extras. Keep generated outputs in ignored results until selected and reviewed for the paper. The original raw RQ1 analyzer retains round-level trajectories/exposure; run-level objective flags are not substituted for those outcomes.

Hardware samples and queue state remain private under the remote suite results. They are absent from public snapshots and rejected by Pages guards. Resource pause policies do not certify hardware safety; missing sensors remain unknown. [Private progress](PRIVATE_PROGRESS.md) displays budgets/time/ETA independently of publication.
