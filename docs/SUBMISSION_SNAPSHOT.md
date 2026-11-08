# Submission evidence cutoff

Freeze the paper's reviewable evidence while live collection continues. The snapshot is a new immutable directory, never a moving dashboard export. Choose an explicit past/current UTC cutoff; rerunning with the same output path fails rather than replacing evidence.

```bash
.venv/bin/python scripts/submission_snapshot.py \
  --source results/studies \
  --source results/campaigns/primary-confirmatory-v4-20261108 \
  --source results/repository-runs \
  --source results/campaigns/primary-decomposition-v41-20261108 \
  --cutoff 2026-11-08T06:50:00Z \
  --out results/submission-snapshot-FRESH \
  --pending primary_long=results/campaigns/primary-long-safeguard-v33-20261108/primary-long-state.json \
  --pending decomposition=results/campaigns/primary-decomposition-v41-20261108/decomposition-state.json
```

Use a new output name and the intended cutoff when preparing the actual submission. Python callers can use `prepare(sources, cutoff, out, pending_states=())` and `validate(directory)`.

Only completed manifests with all four source files and a verified checksum are eligible. A run must end at or before the cutoff. Failed/budget-exhausted, unsealed, later and unsupported-protocol manifests receive separate exclusion counts. Supported protocols are2.6,4.0,4.1 and repository3.0/3.1/3.3. Older development protocols are deliberately excluded rather than pooled. Overlapping source paths are deduplicated; duplicated immutable run identities fail. No source is modified, resumed or queried for inference.

`public.json` uses a closed numeric schema. Source/model/worker/freeze/context/defense/executor cohorts remain distinct; mock rows remain explicitly marked. Case identifiers and model identities are hashed. It contains no task text, endpoint, local path, upstream diff or judgment rationale. `lineage.private.json` retains source locations outside the publication boundary. Checksums detect accidental alteration, not externally anchored tamper-proofness.

`RQ_ASSESSMENT.md` presents supported interpretations and pending gates, separately from the original compact paper freeze. `safeguard.json` gives descriptive observed boundary cells with their denominators. It deliberately leaves effect estimates unavailable until registered collection completes, and utility precision/recall remain null until independent human adjudication. The completed registered long analysis supplies paired treatment/safeguard and difference-in-differences effects; no partial matrix is presented as that completed study. A bundled attribution reminder is not a causally isolated mechanism.

Pending allocation states are observations at freeze time, with their own observation UTC and hashes. They can be later than the evidence cutoff and do not contribute unfinished-run outcomes. They are progress metadata, not evidence that a planned matrix has completed.

For public packaging, include only `public.json`, `safeguard.json` and `RQ_ASSESSMENT.md` after `validate(directory)`. Never include `lineage.private.json`. Validation checks the content hash, cutoff, duplicate IDs, row-derived cohort/safeguard tables, exact generated assessment and privacy scanning. The original compact numerical freeze and reference-checkpoint interpretation remain unchanged.
