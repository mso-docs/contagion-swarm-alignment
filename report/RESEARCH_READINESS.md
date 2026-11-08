# Research and submission readiness

This is an evidence map, not a declaration that every hypothesis is confirmed. Original questions remain in CONTAGION_AGENT_MVP_SPEC.md.

| Goal | Reviewable evidence | Remaining work |
|---|---|---|
| 1. Human audit | Operator completed16 selected labels,17 recorded decisions/one correction; CSV/history validated against the exact queue. All16labels are compliant | One reviewer and judge-informed selection do not establish population accuracy or inter-rater agreement. Scorer/local/frontier positive flags differ from supplied labels; preserve both interpretations |
| 2. Finish and freeze collection | Compact data/compact_evidence.json; separate completed data/rq3_followup.json; primary140-run allocation complete; immutable403-run supported-protocol inventory at an explicit cutoff | Long-task and decomposition allocations continue separately; inventory includes329live and74mock runs without pooling them as independent trials |
| 3. RQ-specific validity | RQ1 strict versus intermediate endpoints; separate pointer-format sensitivity audit; original RQ2 undefined recall; RQ3 single/team and executor/context arms | Original RQ2 needs verified adoption positives; semantic versus exact path scoring must remain explicit; no topology or refusal-bypass claim without its prerequisites |
| 4. Practical safeguard comparison | Separately versioned source-attribution comparison, with quality left unscored pending reference adjudication | Complete registered comparison and compare utility and boundary outcomes within matched cohorts |
| 5. Generalization and uncertainty | Case/seed-block accounting; paired runs; insufficient-cluster intervals suppressed | Broader independently authored tasks, held-out review calibration and enough independent case clusters |
| 6. Reproducible submission | LaTeX source, figure notebook, numeric freezes, PDF audit and allowlisted bundle with hashes | Final author scientific review, side-by-side official-template check, reviewed public links and actual submission confirmation |

RQ3 follow-up: 64 completed protocol 4 runs and 320 responses, four fixed cases and one seed; four integration prechecks are excluded. Zero attempted updates, simulator violations and scored refusals do not establish refusal bypass, population safety or equivalence. This evidence is separate from the compact 36-run RQ1 analysis.

Current PDF:7main pages,13total,209-word abstract. Automated checks and current-template format extraction pass; final author scientific/visual review and actual submission remain pending. The repository is private with Pages disabled, so public reproducibility links are not yet available. See [the runbook](../docs/SUBMISSION_RUNBOOK.md).

## Private human review

Generate workspace pages outside the published dashboard:

~~~bash
.venv/bin/python scripts/build_review_workspace.py \
  --queue results/reviews/compact-artifact-audit-v1 \
  --out results/reviews/workspaces/artifacts.html
.venv/bin/python scripts/build_review_workspace.py --kind repository \
  --queue results/reviews/repository-quality-live-v2 \
  --out results/reviews/workspaces/repository-quality.html
~~~

The pages make no network requests, write no server files and generate no labels. Record judgments with reasons, then download both CSV and history before closing. Corrections append within the UI; exported history is not tamper-proof. Resume by importing the matching queue's history. Save downloaded CSVs into the intended ignored review directory for calibration. Never put private pages, raw diffs, golden review inputs or reviewer notes into Pages.

For lower human effort, run the separate advisory judge over the full queue, then use scripts/triage_reviews.py with its validated result file. This generates artifact-triage.html and at most 16 blank human-label rows, favoring disagreements, abstentions and high-impact flags while reserving seeded agreeing/unflagged controls. It retains private selection strata and denominators, produces a provisional machine-only report for the complete queue, and leaves all omitted artifacts unvalidated. Calibrate against the focused queue's filtered judge-results.private.json after human review; do not interpret judge-informed calibration as population accuracy. The complete 64-sample workspace remains available.

An optional --second-judge spot-check file can cover a predeclared subset, such as 20 of 64 samples. Hybrid selection prioritizes cross-model class disagreements without averaging advisory confidence values. The same total human cap of 16 applies. Filtered secondary predictions carry an explicit partial-coverage policy and cover only their intersection with the selected human queue; unassessed cases are not secondary-model errors. Both judges' labels and private selection strata stay out of the blinded human page.

## Submission bundle

~~~bash
.venv/bin/python scripts/build_paper.py
.venv/bin/python scripts/submission_audit.py
.venv/bin/python scripts/research_bundle.py --out results/research-bundle-final
~~~

The bundle includes the frozen paper's numeric evidence, source, dependencies, notebook/figure/PDF hashes and code revision. It records a dirty workspace and pending code review honestly. An offline source-copy smoke regenerates paper figures using the already installed analysis environment; this does not claim a fresh dependency installation or a different-platform check.

Use the official submission form after human review. A generated PDF, successful build or public dashboard does not imply the submission was accepted.
