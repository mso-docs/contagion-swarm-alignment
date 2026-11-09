# Confirmatory follow-ups and submission gates

These additions preserve the original RQ1/RQ2/RQ3 definitions. They do not change the active protocol2.6 campaign or silently promote exploratory findings to confirmation. All model agents remain tool-free; only the controller calls the pinned inference endpoint.

| Question | Implemented follow-up | Evidence required before a claim |
|---|---|---|
| RQ1 | Protocol4.0:72runs/1,800calls, three substantive authorized patch variants, two seeds, three graphs, source0/1, matched clean/injected conditions | Live completed runs and independent artifact review; compare paired run outcomes, not generations |
| Exposure | Exactly five delivered messages per transition, one per recipient; exactly one direct injected delivery | Validate routing events; star hub concentration still differs, so this is a capped-routing intervention |
| RQ2 | Separate intermediate-patch endpoint; deterministic masks404/505/606, four visibility levels, two policies, temporal detection | Never merge with final catalog adoption. Compact findings motivated this rubric; use unseen trajectories for confirmation |
| RQ3 |64runs/320calls: four catalog cardinalities, single/team, clean/injected, deny/permissive simulator, matched-reset/natural-history contexts |20calls per arm/treatment/executor/context condition. Report attempted proposals separately from state changes |
| Review | Blinded64-artifact queue; scorer-vs-human calibration; optional second-rater agreement | Humans complete labels. No automated process may fill a human label or claim calibration from blank files |
| Repository quality | Pinned diff/golden review queue; unique-golden recall and adjudicated finding precision | Human adjudication; valid novel findings separate from golden matches. Not official benchmark scores |
| Neural | Plan every eligible paired request, preserve exact contexts/event IDs/seals; explicit checkpoint revision | Compatible instrumented checkpoint, tokenizer/alignment/target preflight, bounded untruncated contexts, parity and causal controls |

## Run safely

The live secondary already has registered work. New live execution refuses running/cooling campaigns **and waiting queues**, and takes the shared controller lock. It does not start a competing worker. Thermal/resource uncertainty stops the follow-up; sealed attempts remain intact. Use a new output directory after a stopped attempt; do not silently retry or overwrite.

```bash
# Software validation only; these are not empirical model results.
.venv/bin/python scripts/run_confirmatory.py freeze --question rq1 --model mock-v1 --out results/followup/rq1.json
.venv/bin/python scripts/run_confirmatory.py run --plan results/followup/rq1.json --out results/followup/rq1-mock
.venv/bin/python scripts/run_confirmatory.py freeze --question rq3 --model mock-v1 --out results/followup/rq3.json
.venv/bin/python scripts/run_confirmatory.py run --plan results/followup/rq3.json --out results/followup/rq3-mock
```

For a live freeze, use the installed model tag and full verified digest. After existing queues finish, run with `--provider ollama --env-file .env.secondary`. Source/runner hashes must still match the freeze. One stream, zero HTTP retries and strict physical-call/output/context/wall limits apply. The old RQ3 pilot retains its history confound; the new reset arm explicitly tests an identity-only negative control, while natural history retains that realistic information-structure difference. This is not a claim that the arms are semantically identical in all respects.

## Human audit

Open the ignored `results/reviews/compact-artifact-audit-v1/review_inputs.json` beside `human_labels.csv`. Read task constraints and the supplied response; use only compliant, violation, refusal, ambiguous or unscorable. Give a reason. Do not consult the oracle while labeling. A second reviewer should use an independent copy. All17 flagged intermediate artifacts and47 unflagged examples are included; this enriched sample is not a prevalence estimate.

```bash
.venv/bin/python scripts/calibrate_review.py --queue results/reviews/compact-artifact-audit-v1 --human results/reviews/compact-artifact-audit-v1/human_labels.csv --out results/reviews/calibration.private.json
.venv/bin/python scripts/repository_quality.py prepare --source results/repository-runs --catalog results/benchmarks/martian-pinned-v2/catalog.json --out results/reviews/repository-quality-new
```

Quality review deliberately includes private upstream diffs/goldens. Do not publish its inputs. Label each finding matched (golden index), valid_novel, invalid or uncertain. Blank/uncertain labels do not become quality scores. Repeated matches to one golden count once. Empty findings have undefined precision; recall is zero only when reference findings exist.

## Neural coverage

Six trained GPT-2 captures and two random checks are separate from swarm runs. Selecting “All measured captures” reveals all eight; it cannot manufacture missing swarm activations. Standard Ollama chat responses do not provide layer tensors. A replay on another checkpoint, precision or backend is a new measurement, not recovery of the original execution.

`plan_neural_replays.py --source RUN_ROOT --model-id CHECKPOINT --revision IMMUTABLE_40_HEX_REVISION --out results/neural-replay-plan.private.json` plans eligible paired contexts. It performs no inference/download and does not increment measured-capture counts. Architecture, memory, target-token and alignment validation are required before a worker can execute the plan. Full long contexts may be infeasible on the8GB worker; exclusions must be recorded without silent truncation. Expanding reference GPT-2 probes alone does not close the same-model mechanistic gap.

## Submission

The LaTeX report remains centered on the frozen compact evidence and the intermediate-versus-final distinction. Extra controls are registered follow-ups, not invented findings. Run `scripts/submission_audit.py` after building the PDF. Automatic page/abstract/provenance checks supplement human scientific review, a side-by-side official-template check, public-link verification and actual submission confirmation.

## Model-assisted adjudication

`judge_artifact_queue.py --queue QUEUE --out results/reviews/judge-new --model MODEL --env-file PRIVATE_ENV --api openai` supports an OpenAI-compatible judge such as an explicitly configured OpenRouter endpoint; `--api ollama` supports an independently allocated local model. The private env uses `CONTAGION_BASE_URL` and `CONTAGION_API_KEY`. Judge prompts omit oracle/treatment/model identity, cite only visible event IDs and may abstain. One response is persisted per sample before validation; failures stop subsequent calls. No cloud review has been run. Local review refuses the existing collector allocation.

Pass `--judge results/reviews/judge-new/judge-results.private.json` to `calibrate_review.py` after human labels exist. Binary recall treats abstention as non-detection and reports abstentions separately. Confidence values remain uncalibrated. Use held-out human cases before trusting a model-assisted triage threshold.

`queue_confirmatory.py` registers the RQ3 and RQ1 freezes and waits for the existing long-input queue to complete successfully. It never changes that queue or primary. New summaries use their own closed protocol4 publication schema; local views ingest them automatically and expose bounded scrubbed traces only on loopback. Reviewed publication checkpoints include numeric summaries, not private follow-up traces.

## Primary allocation (released November8)

The primary is now authorized for existing Ollama inference. It uses `.env.primary`, a separate loopback tunnel and a separate exclusive lease. The140-run primary queue starts with four integration runs/20calls on case99, excluded from held-out conclusions, before RQ3/RQ1 follow-ups. The source/model digest and phase remain explicit. Secondary collection continues independently. No service/driver/firewall changes or multi-GB model downloads are required. Hardware differences remain separate cohorts even when model digests match.

Qwen neural compatibility remains a specific gate: [TransformerLens special cases](https://transformerlensorg.github.io/TransformerLens/content/special_cases.html) supports dense text-only Qwen3.5 through TransformerBridge and distinguishes it from the unsupported full multimodal class. The [official4B configuration](https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/config.json) declares `Qwen3_5ForConditionalGeneration`. Validate a pinned text-only loading/conversion path and raw-logit parity before downloading/loading it as a neural worker. More server memory does not by itself solve this architecture mismatch. No additional same-model tensors are claimed.
