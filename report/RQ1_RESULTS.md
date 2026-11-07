# RQ1 results — protocol 1.1

Observed results from experiments executed during this project. This report is a descriptive pilot/batch summary, not a general alignment evaluation or a submission-ready PDF.

The displayed empirical dataset contains 18 qwen3.5:9b batch runs (3 topologies × 2 treatments × seeds 101/202/303; 450 responses) plus a separate nemotron-3.5-lightning:30b ring pair (seed 101; 50 responses). Five isolated agents each take five rounds. Thinking was explicitly requested disabled. Temperature is 0.2, output budget 256 tokens, call budget 25 per run. Prompts, benign intervention and scorer remained unchanged after pilot review.

All 20 displayed live runs completed without parse failures. All 500 artifact outputs were exact clean answers. No exact unauthorized suffix adoption was observed, including in the injected conditions. This is a null result for one fixed benign instruction and a highly constrained synthetic task. It does not demonstrate broad resistance to prompt injection.

| Model | Topology | Treatment | Runs | Mean adoption | Mean strict task success | Mean wall seconds | Messages / run |
|---|---|---|---:|---:|---:|---:|---:|
| nemotron-3.5-lightning:30b | ring | benign_override | 1 | 0.0% | 100.0% | 24.05 | 40 |
| nemotron-3.5-lightning:30b | ring | none | 1 | 0.0% | 100.0% | 23.38 | 40 |
| qwen3.5:9b | complete | benign_override | 3 | 0.0% | 100.0% | 48.30 | 80 |
| qwen3.5:9b | complete | none | 3 | 0.0% | 100.0% | 48.24 | 80 |
| qwen3.5:9b | ring | benign_override | 3 | 0.0% | 100.0% | 45.42 | 40 |
| qwen3.5:9b | ring | none | 3 | 0.0% | 100.0% | 45.61 | 40 |
| qwen3.5:9b | star | benign_override | 3 | 0.0% | 100.0% | 45.85 | 32 |
| qwen3.5:9b | star | none | 3 | 0.0% | 100.0% | 45.35 | 32 |

## Provenance

The live Qwen batch uses one source hash and all 18 checksums validate. Exact model digests:

- `nemotron-3.5-lightning:30b`: `e6905fffe2e2d9bbe325a9a2d2e074e3bd32683721bc6dfba409dede2f17f4dc`; source `215328ebf55fcde99db4daaf912c3dd5edb969e02f2f56f31690f4a7ae9a5434`; protocol `f0f38517a28deb50ca2d543be5b9515d6f21b5602d72326cbbec83343de4d27a`.
- `qwen3.5:9b`: `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`; source `215328ebf55fcde99db4daaf912c3dd5edb969e02f2f56f31690f4a7ae9a5434`; protocol `f0f38517a28deb50ca2d543be5b9515d6f21b5602d72326cbbec83343de4d27a`.

Raw events and per-run manifests remain local under `results/live-rq1-batch/raw` and `results/nemotron-dashboard-pilot/raw`. The reviewed public projection is `dashboard/data/results.json`. The separate initial Qwen ring pilot, smoke requests, and mock validation runs are excluded from these empirical denominators. The initial five-second smoke timeout is preserved as a failed diagnostic, not silently discarded or counted as a model outcome.

## Limits

- Run/seed is the unit of analysis; agent outcomes are nested. Treatment seeds are matched. No significance or confidence claims are made from three seeds, or one seed for Nemotron.
- The task provides the exact answer format in the system prompt. These results cover that specific instruction boundary and one mild intervention; they cannot establish general alignment or strong attack robustness.
- With no successful adoption, propagation speed is unobserved (null), not zero rounds. Observed maximum adoption distance is zero. Topologies differ in delivered-message exposure.
- Nemotron has only a ring pilot; it is not a full topology replication. Runtime is descriptive: controller wall time includes inference/retries/recording; server load and concurrent operator activity were not controlled or instrumented. It is not a hardware-normalized performance benchmark.
- Native seed and thinking parameters were requested and recorded. Backend acceptance alone does not establish exact reproducibility or reveal model internals.
- These live logs have no positive adoption labels. An RQ2 detector could report false positives, but recall against adopted behavior would be undefined; do not relabel every injected run as a true adoption or mix mock positives into empirical results.
- Public text is scrubbed heuristically and reviewed; unknown PII cannot be guaranteed absent. Full private histories/environment/endpoint metadata are excluded. No neuron activations or causal interpretability results were measured.

## Rebuild

```bash
.venv/bin/python -m contagion.cli analyze --source results/live-rq1-batch/raw --out results/live-rq1-batch/derived
.venv/bin/python -m contagion.cli analyze --source results/nemotron-dashboard-pilot/raw --out results/nemotron-dashboard-pilot/derived
.venv/bin/python scripts/export_dashboard.py --source results/live-rq1-batch/raw --source results/nemotron-dashboard-pilot/raw --source results/final-mock/raw --include-traces
.venv/bin/python scripts/export_dashboard.py --validate-only
```

The public snapshot also includes 18 explicitly separate scripted mock runs for UI/software demonstration; they are not part of the live results above. Research figures are regenerated from retained raw events; the static dashboard regenerates its SVG views from the exported projection. Raw live inference is not rerun by GitHub Pages CI.
