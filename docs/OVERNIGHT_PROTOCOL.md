# Overnight collection plan — protocol 2.6

Registered before this batch's model outcomes. This extends the existing RQ1 protocol, retaining the RQ definitions, prompts and scoring. Primary remains excluded. One secondary inference stream serves five isolated agent contexts; no concurrent large queue or agent tools.

## Questions and planned analysis

RQ1 asks whether ring, star and complete communication produce different downstream unauthorized artifact adoption, and whether differences are associated with exposure. The exploratory hypothesis is that topology changes propagation probability or timing; the direction is not fixed. Report null observations honestly. Task compliance is a narrow outcome, not a general alignment score.

The overnight matrix is three task families (catalog, provenance, patch), evaluation case indices 1–3, four seeds (11001–11004), three topologies and paired clean/injected conditions: **216 runs, 5,400 scheduled responses**. Each run has five agents and five rounds. These cases/seeds are separate from the compact case-0 development/held-out observations. Case generation is deterministic; the generator itself is not a separately held-out dataset. Freeze the complete plan and model digest before inference.

Analyze catalog suffix adoption separately from provenance/patch boundary violations. Publish family/model/protocol/split denominators, parse failures and interrupted attempts. Match control/injection by case, seed and topology. Agents and rounds are nested observations; overlapping seeds and repeated deterministic cases do not create 216 fully independent task samples. Exposures differ by graph and can confound topology effects.

Offline RQ2 evaluates catalog trajectories at the registered visibility fractions with mask seeds 404/505/606. Recall is undefined if no oracle positives occur. Do not manufacture positives. RQ3's existing small simulator checks remain separate; this overnight batch does not add RQ3 evidence. Trained GPT-2 activation captures remain reference-checkpoint evidence, not original Ollama activations or proof of the mechanism behind swarm behavior.

## Order and stopping

1. Finish the compact 36-run live campaign and offline RQ2 analysis.
2. Verify the five development checkpoints, trained-checkpoint controls, tests and security checks; seal a readiness proof. Preserve and disclose operationally interrupted attempts, requiring a complete checksum-valid successor for each affected logical condition. Do not waive parse errors or model failures.
3. Run one short, medium and long real-diff repository review pair (six runs, 260 scheduled calls), sequentially. This is a distinct protocol-3.0 development cohort. Stop before the overnight batch on any failed/invalid pair. Quality remains unscored pending calibrated independent matching; boundary violations are observations, not operational failures or proof of collusion.
4. Run the frozen 216-run synthetic batch with a 5,500 physical-call cap and a 12-hour campaign ceiling. No automatic retries of failed batches. Stop on malformed output, backend error, checksum/source/digest mismatch, low disk/RAM, unknown GPU telemetry, operator STOP or budget exhaustion. Retain completed and partial attempts.

Thermal pacing pauses inference at warning temperatures and resumes only after two stable cool samples. Critical limits are not raised. A readiness proof permits collection on one pinned model/source; it is not scientific certification. A task failure or intervention-induced violation is data and must not be removed to improve results.

## Viewing and publication

Local dashboard: `http://127.0.0.1:8765/`; it discovers sealed logs automatically. Private progress reads the campaign state and logs, with throughput-based estimates that exclude future pauses. Raw logs, server identities, inputs and credentials stay ignored. Public snapshots and bounded reviewed trace exports pass privacy/security gates before commits.

A draft PR stays open for incremental results commits. GitHub Pages deploys merged main snapshots; opening or updating a draft PR does not update the public site. Local collection continues updating the local dashboard. The local controller and secondary tunnel must remain running; preventing idle sleep does not prevent lid-close sleep or loss of connectivity.

Private progress for this frozen campaign:

```bash
.venv/bin/python scripts/experiment_progress.py \
  --campaign results/campaigns/overnight-v26-20261108 --watch
```

During repository prechecks the synthetic campaign state does not exist yet. Inspect `results/campaigns/overnight-v26-20261108/overnight.json` for the current checkpoint. To stop, create `results/campaigns/overnight-v26-20261108/STOP`; the controllers check it before further inference calls. Do not remove the flag and retry without inspecting the retained attempt and creating an explicit resume plan.
