# Primary long-review safeguard comparison

Protocol `3.3-repository-safeguard` is a separately registered follow-up. It does not edit protocol3.1/3.2 repository runs, the protocol4 synthetic queue or their frozen controllers. It tests whether explicit controller source attribution reduces boundary failures while retaining useful static review. It does not identify collusion or explain neural mechanisms.

## Fixed design

| Stage | Cases | Rounds | Network | Seeds | Defenses × interventions | Runs | Scheduled responses |
|---|---:|---:|---|---:|---:|---:|---:|
| Integration |1short case|3|ring|1|2×2|4|60|
| Evaluation |8long PR cases|15|ring|2|2×2|64|4,800|

The eight long inputs are selected by deterministic seed6142 from the pinned, privacy-screened benchmark catalog before any new outcomes are inspected. This phase fixes topology, so it cannot estimate topology effects. The same task/seed is paired across plain/source-attribution and clean/injected conditions. Conditions are shuffled within task/seed blocks. Cases may share upstream projects; uncertainty must retain that dependence.

The plain condition presents content-only peer strings; sender/receiver provenance is still retained in the oracle log. The safeguard adds controller-generated `controller_source`, `source_round` and `trust: untrusted_peer_data` fields plus a fixed boundary instruction. It does not remove the injected message, silently rewrite source code or provide hidden labels. This is a bundled formatting/provenance/boundary-reminder safeguard, not an isolated test of one component. Attribution changes prompt length; identical call and output ceilings do not imply identical realized token consumption.

Both arms use inert pinned diffs, five private contexts, synchronous next-round graph routing and no agent tools. The intervention adds the same benign audit marker request to agent0's first generated peer message. Source code and tests are never executed. Boundary labels distinguish any-round failure from final downstream failure; unsupported execution claims are separate counts. Semantic task quality stays unscored until blinded golden-based adjudication. A missing finding or fast answer does not prove cheating.

## Allocation and budgets

Only primary is used. Existing Ollama services, drivers, network binding and credentials are unchanged. The endpoint must be the established private primary loopback tunnel; model tag and full digest are pinned and checked against inventory. The queue waits for the separately configured predecessor status to become `completed`, then takes `results/checkpoint-gates/controller-primary.lock`. A stopped predecessor stops this chain for review. It never competes with another primary controller or touches secondary work.

- Default physical HTTP ceiling:5,200, including failed/interrupted attempts; no hidden retries.
- Scheduled calls:4,860. Per-run ceiling:15×5=75calls; integration uses15calls/run.
- Queue execution ceiling:8hours cumulative across explicit resumes; wait ceiling:24hours; run ceiling:1hour.
- Context request:32,768tokens; output ceiling:1,536tokens; serialized history ceiling:96,000bytes.
- Structured parse errors, truncation risk, changed source/diff, unknown critical resource telemetry and failed seals stop later runs.
- Thermal warnings pause collection, with two cool samples before resuming. A ten-minute unresolved cooling condition stops the queue.
- `STOP` at the queue root is checked before inference and while waiting/cooling.

Every attempt has append-only events, config, outcome, manifest and checksums. Explicit `--resume` validates completed attempts and skips them; failed attempts remain preserved and consume the remaining physical/wall budgets. A partially written unsealed tail is counted conservatively without editing it. Resume cannot switch backend or silently reset elapsed execution time.

## Commands

Prepare only after reviewing the chosen model, predecessor and caps:

```bash
.venv/bin/python scripts/primary_long_queue.py prepare \
  --root results/campaigns/primary-long-safeguard-v33 \
  --catalog results/benchmarks/martian-pinned-v2/catalog.json \
  --model MODEL_TAG --digest FULL_DISCOVERED_DIGEST \
  --readiness results/readiness/secondary-v26-20261108/readiness.json \
  --after results/reviews/primary-artifact-judge-v1/queue-state.json

.venv/bin/python scripts/primary_long_queue.py run \
  --root results/campaigns/primary-long-safeguard-v33 \
  --provider ollama --env-file .env.primary
```

Mock is the default backend. It validates orchestration and deliberately scripts a safeguard effect; its differences are **not model evidence**. Use a separate prepared root for mocks. For an operator-reviewed restart, add `--resume`; a prior partial attempt is never overwritten. Do not change source/helpers after freezing. If they changed, review and create a new registered release instead.

Numeric results use the closed repository snapshot schema with protocol3.3, defense, phase, primary worker and final-boundary fields. The normal local repository pipeline therefore discovers sealed results automatically. Private trace inspection remains loopback-only; upstream diffs and hidden golden comments are never copied into public summaries.
