# Task complexity and measurement plan

[Documentation home](README.md) · [Developer guide](DEVELOPMENT.md)


The current synthetic tasks are small boundary tests, not general reasoning benchmarks. More
rounds or renamed catalog entries do not automatically create harder tasks.

| Task | Current reasoning demand | Independently checked outcome |
|---|---|---|
| Catalog | Group five rows by stage | Exact answer; unauthorized marker separately |
| Provenance | Find one row and preserve source identity | Exact stage/source; invented source separately |
| Inert patch | Propose one authorized JSON-pointer update | Exact patch; forbidden evaluator-path proposals separately |
| Record store | Local summaries and final aggregation | Summary, forbidden-update attempt and simulated state change separately |
| Real PR review | Read a pinned multi-file diff and reconcile peer findings | Output integrity and boundary flags; semantic finding quality still needs independent matching |

## Endpoints and evidence
Keep these measurements distinct: legitimate task correctness; any-round boundary violations;
final downstream adoption; directly delivered exposure; unscorable/failed attempts; simulated
state mutation; runtime/tokens; and independent judge findings. Runtime reduction or missing a
bug does not establish deliberate cheating. Unsupported test-execution claims and proposals to
alter evaluator fields are concrete narrow boundary signals; agents cannot actually edit the
evaluator or execute upstream tests here.

The compact protocol2.6 patch result is transient:17 forbidden artifact proposals in round1,
with20 direct injected-message deliveries across six injected runs. Final downstream violations
were zero in every task. The any-round flag is not the primary final-adoption endpoint. The
paper shows both, including clean task-quality failures and undefined catalog monitor recall.
Never pool nested agents or repeated masks as independent trials.

## Stronger design, without changing an active freeze
<details>
<summary><strong>Expand reference and commands</strong></summary>

The registered long-input extension uses the same two further real PR cases at3,8,15rounds, all
three graphs, and paired clean/injected conditions:36runs/1,560responses. Input size stays long
at every horizon. This isolates horizon from input size better than the initial
short/medium/long prechecks, although repeated cases, one seed and changed communication
opportunities remain limitations. Jobs are randomized before outcomes; the current controller is
archived. The queue waits for the existing collection to complete and never competes for
secondary inference. Main protocol2.6 remains unchanged.

Next improvements should prioritize independent quality checks before more scale:

1. Match findings against withheld curated issues and run a blinded human audit of correct,
   incorrect, flagged and unflagged outputs. Register score profiles and ambiguity rules before
   judging.
2. Add curated cross-file cases requiring a dependency chain, distractors, delayed evidence and
   explicit acceptance criteria. Change semantic content, rather than only names. Keep source
   revisions and per-case oracles pinned.
3. Cross input complexity and interaction horizon independently; add matched-delivery-budget
   controls before topology claims. Use multiple independently authored task cases and repeated
   seeds.
4. If studying time-pressure shortcuts, register a separate pressure condition and maintain
   correctness/authorization requirements. The current horizon study does not itself establish
   motivation or intent.
5. Test persistent propagation separately from direct first-hop susceptibility. Repeated
   interventions or delayed objectives require a new protocol; do not modify an active baseline
   after seeing results.
6. For mechanistic claims, use the same trained checkpoint and matched task behavior, with
   causal interventions and negative controls. Current GPT-2 captures are reference
   instrumentation, not Qwen swarm internals.

</details>

## Review at scale
`scripts/behavior_audit.py` creates a private, blinded queue covering intermediate as well as
final artifacts. The compact queue contains64samples, including all17 flagged intermediate
artifacts plus sampled unflagged outputs. Model identity, condition metadata and oracle labels
are excluded from reviewer inputs; oracle labels are stored separately. Inputs contain only the
subject's bounded past delivered messages, with no future events. Review raw artifacts without
silently repairing malformed outputs.

Use a task-specific judge with cited event IDs and an abstain option. Calibrate on held-out
human labels, audit unflagged outputs, and review scorer/judge disagreements. This enriched
audit set is not prevalence representative; do not report its accuracy as population performance
without an appropriate evaluation design. A second independent rater helps quantify agreement.
No human calibration or judge accuracy is currently claimed. Judge inference must have a
separate serial allocation so it does not disrupt the active model workload; paid remote review
requires explicit workload authorization and reviewed/redacted inputs.

## Visual review and paper checkpoints
- Live dashboard: inventory heatmap, completion bars and calls/runtime scatter for every indexed
  task. Click cells/points to filter and inspect evidence. Counts include distinct protocol
  cohorts without pooling behavioral scores.
- `notebooks/all_tasks_analysis.ipynb`: expanding coverage inventory; snapshot hashes and failed
  attempts retained.
- `notebooks/paper_figures.ipynb`: frozen compact numerical evidence, temporal outcomes, monitor
  false alarms and reference-checkpoint diagnostics. New runs do not silently alter the selected
  paper figures.
- `scripts/build_paper.py`: execute the frozen notebook, compile LaTeX, check the abstract, US
  Letter layout, main-text page limit, required sections and extracted-text privacy. Human
  scientific review remains required.
