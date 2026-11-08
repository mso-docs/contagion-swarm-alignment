# Measurement audit

This is a readiness assessment, not a declaration that every research hypothesis has been evaluated.

| Area | Improvement implemented | Remaining requirement |
| --- | --- | --- |
| Provenance | Frozen cohorts, retained attempts, snapshot/analysis hashes | Archive chosen raw sources and exact dependencies with the paper |
| Denominators | Completed, failed, indeterminate, parse-failure and scorable counts | Review excluded cases and report coverage |
| RQ1 | Separate downstream adoption/exposure and objective run flags | More predeclared held-out cases/seeds; matched exposure if making topology claims |
| Uncertainty | Working-model Wilson intervals; explicit sparse samples | Cluster-aware design/power assessment before population inference |
| Paired effects | Matched case/seed comparisons; duplicate retries rejected | Adequate independent case clusters before paired uncertainty/significance |
| RQ2 | Separate policies/cohorts; confusion counts and undefined recall | Verified positive adoption cases, more monitor seeds, coverage beyond catalog |
| RQ3 | Attempts vs simulator state changes remain distinct | Held-out single/team comparisons with matched budgets and recorded information access |
| Runtime | All-attempt runtime distributions, observed latency/token telemetry | Controlled hardware allocation for performance comparisons; no inferred GPU-hours |
| Interpretability | Six trained GPT-2 reference captures with parity/no-op/position controls | Same-model task behavior linkage and replicated causal controls before swarm mechanism claims |
| Reviewer | Blinding, cited event evidence, human queue | Held-out human adjudication, agreement/precision/recall and calibration |
| Public data | Unified evidence index; numeric telemetry derived from logs; privacy gates | Review optional text; private queue/hardware data never enter Pages |

Do not use a grand total of generations as the experimental sample size. Report development, timing, mock and held-out evaluation separately. A zero-event result with three runs remains highly uncertain. Neural magnitudes, generated reasoning text and advisory model confidence are not alignment probabilities.

The compact temporal audit distinguishes17 round1 patch deviations from zero final downstream violations. See `RESEARCH_MEASUREMENT_PLAN.md` and the frozen paper notebook. Intermediate-artifact review is required; final-only review would miss this observation.

## Implemented follow-ups (separate evidence)

Protocol4 adds capped-exposure/source-placement RQ1 controls and RQ3 context-policy controls with20calls per simulator condition. `deviation_monitor.py` evaluates intermediate patch proposals without altering final-adoption RQ2. Human/scorer/judge calibration and private golden-based repository adjudication are executable; blank labels remain pending. A linked neural replay planner performs no inference and cannot recover missing Ollama tensors. These close implementation gaps; live results and human validation are still prerequisites for stronger conclusions. See [the registered design](CONFIRMATORY_PROTOCOL.md).
