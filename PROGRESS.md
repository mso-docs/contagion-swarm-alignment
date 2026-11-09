# Progress

## Researcher readiness and unified live dashboard

The default localhost root now combines all indexed protocol-1 and protocol-2 evidence across overview/model/evaluation/trace/dataset views. Current inventory: **61 live attempts / 945 returned responses** (20 legacy RQ1 / 500 responses; 41 newer development/timing/integration attempts / 445 responses). Another 134 protocol-2 mock studies remain separately labeled. Grand totals are evidence inventory, not independent research sample sizes. The local service discovers sealed studies every15s and optionally polls sanitized secondary snapshots every60s into ignored staging; private progress/hardware fields are stripped. Browser caching is disabled locally, asset changes trigger reload, and synchronization health is visible. No versioned end-user URL is required.

Exported available study timestamps, source hashes, actual attempt counts, latency/token measurements, message counts, final-agent labels and catalog-specific downstream metrics from checksummed logs. Missing data stays null; noncatalog objective violations never become suffix-adoption labels. Source cohorts and model filters remain separate. Main inventory and eight-view JavaScript smoke checked against actual exported data. Primary untouched; the large suite remains paused.

Research reports now separate strict frozen cohorts, expose denominators/indeterminate outcomes/failed attempts, calculate working-model Wilson intervals and matched control differences, reject ambiguous retry pairs, record provenance hashes and export PNG/SVG/CSV/JSON with explicit figure caps. Original RQ1 adoption/exposure stays separate. Offline RQ2 analysis regenerated **176 dependent projections from 22 existing trajectories**, giving40 cohort/policy/visibility summaries; no new inference is implied and recall remains undefined without positive adoption labels.

Neural validation now checks shapes, duplicate layer/neuron indices, patch positions and immutable trained revisions; patch layer and trained target are explicit. Original-model/bridge parity was measured successfully on secondary CPU random smoke (maximum logit error about6e-8). Raw checksummed capture fetched; public projection contains no token IDs/prompts/tensors. Added no-op/baseline-gap checks and normalized restoration diagnostics. Trained-checkpoint, task-linked replication and SAE evaluation remain pending; random weights are instrumentation only. A decimal/Luhn false positive in privacy lint was corrected with a regression check, without weakening card detection.

Added RESEARCHER_GUIDE.md, MEASUREMENT_AUDIT.md and INTERPRETABILITY_PROTOCOL.md; refreshed the paper workbench and report guide. Latest full pytest: **147 passed**. Bounded mock pair and regenerated analysis completed; cohort reports generated from175 studies/42 strict cohorts plus original RQ1. Security/static gates and final build are rerun after publication settles, since background exports and concurrent edits can invalidate a pre-commit worktree snapshot. Raw logs remain unchanged and ignored. Future source deployments require fresh freezes.


## Private progress monitor

Added `scripts/experiment_progress.py` for read-only terminal status on either local machine, local suite/study roots, and optional secondary-only SSH polling. Shows sealed/completed/failed/unsealed runs, planned totals, physical attempts, recorded run time, elapsed window, throughput, remaining/total work estimates and update age. No finish timestamp is shown for stopped/paused/stale workers; estimates are explicitly rough and do not include future pauses. No primary access or inference was performed.

Read-only secondary verification observed the original queue stopped at 5 sealed runs (3 completed, 2 failed), 125/80,680 calls; its rough remaining-work estimate was about 39h39m, not a finish promise. The six later local protocol-2.4 checkpoints are a separate monitored source, 6/6 runs and 60/60 responses. Added `docs/PRIVATE_PROGRESS.md` with commands for both paths.

Removed queue/hardware telemetry from current public data and public suite publication. Remote sync strips older operational fields; commit/build guards reject populated private telemetry. Research result counts and per-run scientific runtimes remain public. Source changes require fresh freezes before future source deployment; the paused remote release is untouched.

Verification: **136 pytest tests passed**, bounded mock pair completed and regenerated analysis, eight-view dashboard DOM smoke passed, Gitleaks worktree/history and all privacy/static gates passed, and the allowlisted Pages build passed. Private progress source/docs are reviewable; runtime status stays in ignored results.


## Privacy hardening checkpoint

Added offline `scripts/scan_privacy.py` and integrated it into staged/candidate guards, public build validation, research export/watch publication and a visible GitHub Actions step. Recognizable email, phone, government-ID/payment-card patterns are checked; public JSON receives stricter credential/address/path checks after decoding JSON escapes. Known values come from all root `.env*` files and ignored `*.redact.txt` files. No matched values are printed. More raw artifact extensions/aliases are blocked, including renamed logs, databases, tensors and HAR captures. Existing pre-commit hook is installed; gates inspect staged blobs, not cleaned unstaged copies. Originals remain unchanged.

Observed: 132 pytest tests passed; full Gitleaks worktree/history, publication/privacy, Ruff and Bandit checks passed. Strict audit of 64 public/latest-checkpoint files found no recognized leaks. Standalone public scan checked 37 JSON files with no findings; validated Pages build contains 42 allowlisted files. Local watcher restarted with privacy checks. No remote server access or inference was performed. See `docs/PRIVACY_CHECKS.md`; arbitrary names/addresses or encoded secrets still require denylist/review.


## Current checkpoint: dashboard freshness and developer docs

The local public research snapshot now contains 35 sealed study attempts, including all six latest protocol-2.4 checkpoint runs (60 responses, zero parse failures, control task success 1.0). Earlier failed/invalid diagnostics remain visible in separate cohorts. The legacy 20-run snapshot remains separate. The large secondary suite is paused; primary is excluded. Trained-checkpoint neural measurements and calibrated judging remain pending.

Added `scripts/watch_dashboard.py`: periodic local export of selected sealed attempts, checksum validation, preservation of approved evidence and atomic index replacement. Browser Refresh fetches both snapshots; the research view shows export and browser-check times. Local preview HTTP was verified to serve 35 studies. Pages still requires reviewed data to be pushed and a successful build.

Replaced the accumulated README with a concise quick start, research table and developer navigation. Added colorful Mermaid experiment/publication/architecture diagrams and `docs/LIVE_DASHBOARD.md`. Older entries below are historical snapshots, not current blocker statements.

Verification for this checkpoint: `.venv/bin/python -m pytest -q` → **122 passed**; bounded mock pilot → **2 completed runs** with regenerated analysis; JavaScript DOM smoke → **passed**, including dual-snapshot refresh and task drill-down; `scripts/check_all.py` → **all gates passed** (worktree/history Gitleaks, publication/privacy, syntax, Ruff and Bandit). Validated static build → **42 allowlisted files**. No inference was started or resumed during this dashboard/documentation update.

## Historical implementation log

- P0 complete: local Python package, safe five-agent controller, mock inference, topology routing, benign intervention, JSONL provenance, integrity/resume, configs, CLI and tests.
- P1 live pilot complete: configured qwen3.5:9b passed logged smoke validation and a 25-call-per-condition clean/injected ring pair. All 50 pilot artifacts were exact clean answers; adoption was zero.
- P2: 18 mock conditions / 450 mock calls validated. The live protocol-1.1 Qwen matrix completed 18/18 runs / 450 responses with one source hash and valid checksums. A separate Nemotron Lightning pair completed 2/2 runs / 50 responses. No suffix adoption was observed; all displayed live artifacts were exact clean answers.
- Latest test run: **57 passed**. Dependency check and compilation passed.
- RQ2 and RQ3 definitions/protocols preserved; implementation deferred behind the live RQ1 gate. Literature verification and submission PDF remain pending.

Final mock outputs: `results/final-mock/raw` and `results/final-mock/derived`. Included source fixture: `tests/fixtures/mock_run`. Full execution record, limitations, commands and next steps: [docs/BUILD_STATUS.md](docs/BUILD_STATUS.md).

Dashboard: per-model/cohort metrics, runtime/latency, network replay and optional sanitized traces are implemented; GitHub Pages deployment on push is configured locally. The reviewed snapshot contains 20 live runs and 18 separately labeled mock runs. Enable Pages via GitHub Actions, commit/review the sanitized snapshot and push. No remote server settings or credentials were changed.

Pilot convenience workflow: copy `.env.example` to `.env`, set the existing server URL, run `.venv/bin/python scripts/run_pilot.py --doctor-only`, select an installed model in `.env`, then run `.venv/bin/python scripts/run_pilot.py`. The new script was validated with a clean/injected mock pair and analysis under `results/script-check`.

Dashboard redesigned to match the supplied observability reference: navy sidebar, eight real-data metric cards/sparklines, run history, model comparison, artifact distribution, per-run quality and a dedicated trace workspace. Six functional views; no fabricated cost, drift, feedback or activation metrics. 57 tests and expanded JS interaction/privacy/build checks passed. Preview: http://127.0.0.1:8765/ (hard-refresh to load the new assets).

Security: installed the local pre-commit hook, pinned Gitleaks/hygiene tools and GitHub Actions, added staged/private-file/public-data guards, read-only Ruff/Bandit checks, CI dependency audits and gated Pages deployment. Direct security tool versions are pinned; vulnerable local pip was upgraded to 26.3 and both audits are clean. Latest tests: **77 passed**. No files staged/committed/pushed; review Git author identity before a public push. Setup: docs/SECURITY_CHECKS.md.

Study: docs/EXPERIMENT_STRATEGY.md explains the actual catalog task and a prospective rigorous expansion. Matched thinking-on/off configs are available, unrun. AI reviewer triage, additional task families and actual activation/SAE studies remain prospective; no broad aligned/maligned model rating or neuron evidence is claimed.

## Protocol-2 research expansion — November 7, 2026

Implemented a reproducible 384-variant SQLite scenario registry (256 development / 128 evaluation), seeded stratified/uniform sampling, pre-inference source/plan/task/registry freezes, four bounded task families, strict artifact scoring, matched five-call RQ3 arms, default-deny/permissive in-memory controls, nested offline RQ2 monitor projections, blinded call-limited review and evidence validation, descriptive human calibration, and separate closed-schema publication. Dashboard now has eight views including scenario/review tables and measured neural heatmaps/patch controls with an honest empty state.

Executed locally: development 12 mock runs (300 responses); held-out matrix 72 mock runs (1800 responses); RQ3 deny and permissive four mock runs each (20 responses each). These 92 runs are software checks, not new empirical model findings. Reviewer mock processed 20/60 artifacts, with all60 queued and40 unreviewed. Existing live Qwen ring cohort produced48 dependent RQ2 projections; zero adoption positives means undefined recall/F1. Public research snapshot includes92 mock studies,20 mock reviews,384 scenario metadata rows,8 monitor summary rows and zero neural captures. Existing protocol-1 live results were preserved.

Prepared isolated TransformerLens4.3 Linux CPU installer, Docker recipe, capture CLI, private safetensors/checksums, reduced public schema and manual Actions smoke workflow. Local host has no compatible PyTorch wheel (Intel Darwin/Python3.14); actual capture/runtime and trained-checkpoint replay remain unverified. Remote setup requires an operator-approved worker; the user may reply directly in chat if the follow-up widget fails. No remote changes, push or deployment performed.

Validation: **96 tests passed**, full candidate/history secret and static checks passed, eight-view DOM interaction smoke passed, six-file Pages build passed, and existing preview returned HTTP200 at http://127.0.0.1:8765/. Neural chart rendering was checked with a synthetic in-memory UI fixture only. Existing baseline is committed; these additions remain uncommitted on the feature branch for review. Next deployment step: review/commit/push the branch, open a draft PR, run the optional Linux measurement workflow, and merge to main after checks to trigger Pages. Actual neural measurement and human reviewer calibration remain explicit blockers to empirical claims.

## Two-server readiness

Implemented isolated Linux worker setup, safe source bundle, per-server private env files, digest-checked inference, pair-preserving deterministic shards and immutable shard assignments. See docs/WORKERS.md. Existing primary inference server is reachable. A frozen20-call Qwen3.5:9b two-round integration pair completed successfully:10/10 responses in each arm, task success100%, no scored violations. This small setup check is separate from the original protocol-1 results. Public research export now contains92 mock and2 live studies. A two-shard mock study completed6+6 disjoint runs. Neural installation and secondary-server connectivity still require the actual SSH targets/project directories; no remote installation has occurred.

Worker validation:102 tests passed in the repository and102 in the unpacked transfer bundle. Secret/history/privacy/static checks and Pages build passed. No neural result is claimed until a real supported worker completes capture.

## Installed secondary neural worker and prospective scaling — November 7

Private .env now accepts the four server/project fields; publication/commit guards treat their values and host components as sensitive. Secondary SSH preflight succeeded (Linux x86_64,Python3.14.4,59.3GiB RAM,>1TiB free disk). Operator-driven remote helper transferred an allowlisted bundle and installed an isolated CPU environment in a fresh approved-project release:TransformerLens4.3.0,torch2.15.0+cpu,transformers5.22.2,safetensors0.8.0. Pip dependency checks passed. No sudo, driver/firewall/service changes, GPU use or pretrained weights downloads occurred.

Initial capture failed because the fully offline tokenizer lacked name/BOS initialization metadata required by TL4. Preserved previous remote source, corrected explicit BOS/postprocessor/name configuration and reran into fresh output. Actual random-weight capture succeeded:2layers/4tokens per input, residual RMS/selected MLP activations and clean/corrupt/patched/no-op/position-control logits. Both controls matched corrupt baseline within1e-6. Private artifacts were fetched and checksum-validated; the reducer published one measured random capture without raw inputs/token IDs/full tensors. Trained-checkpoint replay is still pending.

Protocol2.1 prospectively permits5–128 RQ1 agents, retains original five-agent protocols, call/time/message caps and serial requests. Froze matched randomized development samples at5/10/20/40/80 agents; completed6 mock runs per size (30runs/1860scriptedresponses). No live larger-swarm findings claimed. Dashboard adds size cohorts/runtime plots and actual neural charts. Snapshot now has122mock+2live study rows,20mock reviews and1random neural capture. Existing legacy data is preserved.

Primary SSH preflight failed authentication; the primary service/60limit could not be inspected. Its shared Ollama workload was left unchanged. Ollama documentation distinguishes parallel requests, queue capacity and loaded models; no universal60-agent cap is documented. Confirm the caller's60limit and agreed shared resource allocation before tuning or load-testing. Reply directly in chat after correcting PRIMARY_SERVER_ID/local key if the widget is unavailable.

Validation:110pytest tests passed; actual measured-neural/scaling DOM smoke passed; six-file Pages build passed; secret/history/privacy/Ruff/Bandit checks passed. No push or deployment performed.

Primary SSH follow-up:operator confirmed user/host are correct and clarified that60was the other swarm's active agent count. The current session's SSH agent query could not reach a usable agent; one public/private key pair was available locally, and the primary rejected it even when explicitly selected with existing Keychain access. No key material/fingerprints/target values were printed, and no credentials were added or modified. Compare a working regular-Terminal login to identify an agent/config difference. Neural setup on secondary remains successful. A Gitleaks false positive on the timestamped smoke-output directory in prose was resolved by using the generic ignored directory in documentation; no scanner exclusion was added.

Primary authentication resolved diagnostically:operator's normal login uses a password, so batch/key-only SSH cannot work yet. Operator needs to install an existing public key using their own password in Terminal and verify BatchMode login. No password/key material was requested or stored, and no credential changes were performed by the agent.

Commit preparation completed at user request:111 tests passed, final secret/privacy/static checks and Pages build passed. PR text covers the complete branch and distinguishes live integration findings, mock scaling results and random-weight neural measurements. All reviewed nonignored staged/unstaged/new files are included; private .env, deployment bundles, logs, tensors and generated build directories remain excluded. Primary SSH key setup remains an operator step.

Primary SSH now succeeds after the operator installed their public key. Read-only preflight observed Linux aarch64/Python3.12.3,121.7GiB RAM and2708GiB free disk. No explicit numeric Ollama overrides were returned by the allowlisted service query; effective settings were not inferred. No packages/services/workloads were changed on primary. SSH blocker resolved; shared-resource allocation and trained-checkpoint replay remain next steps.

## CI dependency audit correction

GitHub's Python3.11 environment retained vulnerable seeded setuptools79.0.1, while local Python3.14 had no installed setuptools and its earlier installed-package audit could not expose that mismatch. Added shared requirements-bootstrap.txt with pip26.3/setuptools84.1.0, upgraded it before CI project installation, applied it to both worker installers and source/Docker packaging, and raised the isolated build-system floor. Recorded the setuptools version in the local dependency snapshot. No advisory ignores or audit disabling were added. Both recorded-version and installed-environment pip-audit now report no known vulnerabilities locally; pip check and secret/privacy/static checks pass. GitHub validation will be observed on the corrected PR head before declaring CI green.

## Repository task track — protocol 3.0 development

Added read-only pinned Martian PR imports, hashed long-focused sampling, a bounded five-agent static-review controller, and metadata-only dashboard publication. Three real-diff control/injection **mock** pairs completed: six runs / 260 scripted responses (short 30, medium 80, long 150). No real-model repository result or collusion claim. Full details and commands: `docs/REPOSITORY_BENCHMARKS.md`. Live expansion waits for existing checkpoint promotion; primary remains excluded.

## Compact completion and overnight expansion

Compact protocol-2.6 campaign completed all36 registered conditions (900 completed-run responses); two interrupted attempts are preserved, with941 recorded HTTP attempts/responses across all38 attempts. Offline RQ2:288 projections across three mask seeds. Six trained GPT-2 captures verified; readiness proof sealed after165 tests and security checks passed. Narrow task-family findings are recorded in `report/COMPACT_RESULTS.md`, including clean patch-task failures and undefined catalog monitor recall.

Frozen next campaign:216 five-agent runs /5,400 scheduled responses, secondary only, maximum5,500 HTTP attempts and12hours. Three sequential repository-review pairs (short/medium/long;260 calls) must pass operational checks first; errors stop the supervisor. See `docs/OVERNIGHT_PROTOCOL.md`. No old80,000-call queue restarted. Raw logs remain ignored; sanitized evidence is included in the draft-PR branch, and local dashboard exports continue automatically.

Added and validated `skills/commit-pr-writing/SKILL.md`, repository-required usage, commit-message hook and PR metadata CI validation. The reusable skill is also installed globally with a global Codex instruction requiring its use for commit/PR work.

Draft PR#5 is open on `feat/live-rq-pilots`; initial commit `bd7f4f3` passed all commit hooks and was pushed. First detached overnight supervisor stopped during its first repository response: output cap512 hit, incomplete JSON, no subsequent run started. The one-call budget-exhausted attempt is preserved and automatically included as indeterminate public metadata. Repository protocol3.1 now requests1,536 tokens with up to four findings/320-character descriptions; prior results retain3.0 hashes. A fresh overnight root `overnight-v26-20261108b` is frozen with the unchanged synthetic matrix. No implicit resume or overwriting of the first supervisor.

The amended detached supervisor is running short/medium/long protocol3.1 repository checks on the secondary. Its first short control sealed15 responses with no parse failure; the paired injection remains in progress. The private campaign monitor now displays precheck phases and provisional unsealed response counts before the synthetic campaign state exists. Command: `.venv/bin/python scripts/experiment_progress.py --campaign results/campaigns/overnight-v26-20261108b --watch`. Main216-run campaign remains queued behind these checks. Local dashboard health is OK; public Pages awaits a later merge, while draft PR#5 stays open.

The first live protocol3.1 short repository control/injection pair has completed30 responses with zero parse failures. Medium and long pairs continue sequentially before the216-run synthetic batch. Sanitized pair summaries are included in draft PR#5; quality remains unscored and collusion unadjudicated. All167 tests and commit hooks passed before collection continued.

Model/protocol comparison now uses compact model/backend cards with visual ranges of condition means, completion/attempt counts, protocol/cohort coverage and expandable exact cohort tables. Details are lazy, bounded-scroll, searchable and preserve expansion across refreshes. Cohort/network/treatment results are not pooled into an alignment score. Dashboard DOM interaction checks and17 publication/service/watch tests passed; public build passed. Collector remains running on the medium repository checkpoint, with no harness/source edits for this UI change.

## Paper, measurement audit, expanded visuals and long-horizon collection

Compiled an actual LaTeX PDF using the inspected official DOCX layout:7main-text pages,11total pages,188-word abstract, with supplied author/affiliation. Executed the frozen figure notebook; seven candidate diagrams have PDF/SVG/PNG exports, with four selected for main text and three appendix diagnostics. The expanding all-task notebook separately generated coverage heatmaps, completion bars and runtime scatterplots (120live attempts /3model tags /6task families at that checkpoint). Dashboard equivalents are interactive and link to traces. Source evidence and figure/build hashes preserve provenance.

Temporal audit correction: the six injected patch runs had17 intermediate forbidden proposals, all in round1, following20direct injected-message deliveries. **Final downstream violations were zero in all36completed runs.** Any-round and final outcomes are distinct; raw logs/scorers are unchanged. A blinded64-sample review queue includes all17flagged intermediate artifacts plus unflagged samples; no human calibration or judge accuracy is claimed.

Registered and detached a further36-run /1,560-response matched long-input horizon pilot (two further PR cases,3/8/15rounds,three graphs,paired conditions). It waits for the active secondary collection to complete successfully; no parallel model load or primary access. A1600-call/8-hour execution budget and16-hour wait ceiling apply. See `docs/LONG_HORIZON_PROTOCOL.md`.

Reviewed and merged Dependabot PRs#1/#2/#3 after current security/reproducibility checks passed. Stale audit failures in#1/#3 were resolved by updating from main before merging. A narrowly scoped reviewed-pin auto-merge policy is proposed in the human-reviewed draft; application/experiment/report code is not auto-merged.

Secondary handoff verified: all six protocol3.1 repository checkpoints completed260responses with no parse failures. The216-run /5,400-response synthetic campaign started and returned its first12responses, then entered a scheduled cooling pause with zero failed runs. The additional36-run matched long-input queue remains waiting for successful completion. Draft PR#5 contains the implementation/report/visuals; reviewed dependency main updates were merged into the feature branch only. The draft's current head passed security/reproducibility CI once; a metadata-edit rerun is pending. New sealed results continue entering the local dashboard automatically.


### Live dashboard synchronization repair

Isolated the runtime result cache from tracked publication checkpoints so Git/pre-commit cannot rewind the live view. All result sources refresh together; newest timestamps sort first, trace labels identify cases, source failures retain last valid data, and filters can be reset. A loopback-only collector strip distinguishes active calls, completed runs, waiting long-input work and monitor analysis cells. Explicit sanitized checkpoint export remains separate from collection.

Validation:175 pytest tests passed; seven service tests include Git rewind isolation, explicit export validation and local Host checks. JavaScript runtime smoke passed all eight views, trace/chart interactions and automatic arrival of a new result without modifying legacy data. Bandit passed. At the status check, the secondary campaign had18/216 completed runs and zero failures; the36-run long-input queue waited without competing inference. No frozen controller, source protocol or primary-server changes.


Chart readability refinement: replaced the expanding sparse adoption SVG with a compact cohort comparison, explicit nonzero-run count and exact within-cohort ranges. Measurement scatterplots fit observed extents and count exact overlapping points without averaging them; axes explicitly disclose fitting. Bars use content-sized canvases, and runtime labels include protocol/task/sample count. JavaScript runtime smoke passed all eight views and automatic arrival; visual browser review remains pending. Frozen scientific scoring and inference were unchanged.

Research figure refinement: task-outcome and monitor panels now use annotated heatmaps with explicit denominators; temporal peaks and reference-checkpoint effects are directly labeled. All-task completion bars carry counts, and runtime scatter uses disclosed symmetric-log axes to reveal short and long attempts. Frozen numerical inputs and conclusions were preserved. Regenerated21 paper figure assets and rebuilt LaTeX PDF (7main-text pages,11total,188-word abstract); three focused paper tests passed.


### Protocol4 follow-ups, measurement review and primary allocation

Implemented a separately frozen72-run/1,800-call RQ1 capped-routing/source-placement comparison and64-run/320-call RQ3 context-policy comparison. Exactly one incoming message per recipient and one direct injected delivery reduce exposure confounding; star hub effects remain. RQ3 crosses matched-reset/natural-history controls, four substantive input cardinalities, single/team, clean/injected and deny/permissive-simulator arms. Every attempt seals before the next run; errors stop collection. The full136-run mock validation completed2,120 scripted responses with36RQ1 and32RQ3 paired comparisons; these are not model findings.

Added offline intermediate-patch monitoring (288dependent projections), blinded artifact judging with evidence citations/abstention, scorer/judge-vs-human calibration and independent-rater agreement, and a private golden-based repository quality workflow. The64-artifact audit still has zero human labels;30live repository samples await adjudication. No calibrated judge or official benchmark score is claimed. Neural replay planning preserves paired request/event/seal provenance without presenting planned work as activations. The dashboard explains the six reference captures plus two random checks.

Primary was explicitly released by the user. Read-only preflight found idle Ollama,117.3GiB available RAM and32°C GPU, and the same installed Qwen4B digest as secondary. Created an ignored private primary configuration/tunnel and a separate exclusive lease; no remote services/infrastructure were modified. The140-run/2,140-call primary queue begins with a20-call integration precheck, then strengthened RQ3 and RQ1. Its precheck completed all four runs/20calls before proceeding. Secondary collection remains unchanged. New protocol4 numeric summaries auto-enter unified local views; bounded sanitized traces are loopback-only, and reviewed snapshots publish summaries only.

The report now has verified additional primary references and explicit hackathon/preexisting-infrastructure provenance. Rebuilt PDF:7main-text pages,11total,188-word abstract. Automated submission checks pass while final author review, template comparison, public-link review and actual submission confirmation remain explicit. Scientific RQ conclusions are not silently expanded with mock or incomplete results.

Final follow-up validation:188pytest tests passed in38.36s;13 focused follow-up tests include capped routing, simulator state separation, private/closed publication, judge abstention, primary allocation and queue stopping. The eight-view JS smoke passed with actual protocol4 summaries included. Public build copied280allowlisted assets. Ruff/Bandit passed. Final PDF/submission audit passed automatic checks (7main pages,188abstract words), while human review remains pending. Primary precheck completed20/20calls before strengthened RQ3; latest status21primary and44secondary completed runs, zero failures.

### Hybrid review and research follow-through

User authorized hybrid review with a cumulative $20 OpenRouter cap. A separate ignored `.env.judge` holds cloud configuration; strict local-worker environment files remain compatible. The frontier runner validates exact model metadata/prices, scrubs and scans inputs, requires zero-data-retention routing and structured cited outputs, reserves cost before calls, and retains uncertain charges. One failed routing request is preserved without automatic paid retry. Twenty validated frontier reviews cost $0.097612; the shared ledger conservatively debits $0.16209950 including the failed reservation. No new batch can reset the authorization. The different-family local Nemotron judge completed64 advisory reviews. Neither judge supplies human ground truth.

The primary protocol4 allocation completed140 runs, including four integration checks,64 RQ3 and72 RQ1 runs. Offline finalization produces separately versioned monitor/paired analyses and a16-item blinded hybrid review workspace. Protocol4 RQ3 had zero protected-update attempts; its repeated full directive does not establish compositional refusal bypass. The compact36-run paper freeze remains separate. Human calibration is pending.

Registered primary long-task collection has68 runs/4,860 scheduled calls with a5,200 physical-call ceiling, serialized inference, thermal guards and seal-before-next-run behavior. Subsequent bounded semantic repository-quality review is queued. A separate protocol4.1 decomposition follow-up is frozen for50 runs/186 calls after that review; its full mock passed50/50 with zero failures. Direct calibration, serial/team decomposition and identity controls remain distinct. New generic blinded-queue generation and private review pages support scalable selection without publishing raw traces.

Secondary collection recovered from a strict-environment parsing failure caused by adding a cloud-only variable to the local-worker environment. The failed attempt made zero model calls and is retained; existing completed runs were preserved. Cloud configuration was isolated before explicit recovery. The further long-input queue waits for successful recovery completion.

Validation checkpoint:288 pytest tests passed in40.87s. Additional privacy/publication checks and final commit validation are recorded below when complete. The trained GPT-2 captures remain reference measurements, not recordings of the Qwen swarm's internals; no calibrated alignment score or collusion claim is made.

### Submission implementation and measurement validation

Implemented the six submission-preparation improvements with parallel evidence, figure and audit work. The immutable supported-protocol inventory freezes403 completed sealed runs at2026-11-08T06:57:00Z:329Ollama/74mock, with separate cohorts,172unsupported older manifests and four incomplete attempts excluded. Only its three closed public files are tracked; source lineage remains private. Long-task and decomposition allocations continue separately from the compact paper.

Imported the author's actual16-label CSV and17-decision correction history, verified their dataset/sample identities and final values, and preserved private0600 copies. All16labels are compliant, as explicitly confirmed by the author. Positive automated signals differ: strict scorer4/16, local judge9/16, frontier2/11. The paper reports these as differences from the supplied human reference, not established misalignment or judge accuracy; recall/F1 remain undefined without positive human labels. Raw judgments/reasons/history are not published.

A separate post-hoc audit found wrapper-prefixed patch paths affect the original strict scorer. Compact intermediate flags expand17→20 under the declared two-prefix sensitivity check; primary6→36. Final forbidden proposals remain zero in both cohorts under both definitions. Exact primary final control matches18/180 become180/180 after normalization, so formatting errors must not be presented as general task incapability. Original scores, active controllers and logs are unchanged; the paper binds the new numeric audit/code hashes and reports it separately.

Main figures now show controller trust boundaries, per-run/round exposure and strict flags, and paired compact task outcomes. Safeguard/utility plotting is implemented but gated on complete real matched evaluation and human quality data; missing utility is never zero-filled. Added public-safe numerical human review, cutoff and sensitivity appendices, a submission rehearsal/runbook and optional three-minute demo outline.

Full notebook/PDF rebuild passed:7main-text pages,13total,209-word abstract.318pytest tests passed in37.72s; critical Ruff passed. Actual current official-template extraction confirms Letter,1inch margins,Arial11body andOldStandardTT20title; author visual/scientific review remains pending. The repository is confirmed private and Pages disabled; reviewer access must not be claimed public. An allowlisted reviewer bundle and exact-artifact rehearsal are prepared independently of actual submission.

Author-requested typography update: switched body/title to Latin Modern Roman, preserving the template-font PDF and build at `results/paper-template-bf217d7/`. Verified embedded Latin Modern fonts and visually checked the new title page. The new PDF remains7main/13total pages with209abstract words; nine focused paper/bundle tests and automated submission checks passed. The manuscript and readiness docs explicitly disclose the template typeface override. No experiment/scoring changes.

### Long real-world benchmark continuation and final review preparation

Imported and froze51long benchmark adaptations from pinned Martian and SWE-bench Verified sources:14canonical projects,11domains,42held-out/7development/2training cases. Eight previously used/allocated Martian cases were excluded; all known evaluation forks were mapped to canonical projects before project-disjoint splitting. Dataset licenses, source/input/reference hashes and selection/exclusion counts are preserved. Literal upstream code, issue text and hidden references remain private. SWE uses disclosed reference-localized base windows, not a full-repository or official benchmark evaluation.

Registered a separate primary3.4 allocation:264runs/19,320scheduled calls,32held-out cases, five contexts,15rounds, four-arm matched blocks, first-seed coverage before replication,72cumulative execution hours and21,252physical requests maximum. It is running in its registered waiting state behind the existing primary allocation and a fresh50-run RQ3 prelude. Unexpected prior failures block the administrative release; an expired sealed allocation is never declared a completed study. Zero-call predecessor registrations and partial superseded mocks are retained with amendments.

The final actual-catalog mock completed264/264runs and19,320scripted responses in1,189.81seconds with zero failures/parse errors and264valid seals/17batch receipts. Independent acceptance passed with scientific status `mock_only`; no real-model success or alignment claim follows. Added visible-source feasibility checks, safe reason codes, disk/thermal/context guards and explicit hash-bound recovery decisions without resetting budgets. A fixed two-own-round memory window and reference-localized contexts are recorded limitations; later disappearance of flags is not evidence of learned correction.

Offline batch reporting is active: complete matched batches generate private paired analyses, coverage/boundary/runtime PDF/SVG/PNG plots and separately versioned RQ2 marker monitors. Monitor validation on144mock trajectories produced6,912dependent projections/13,824method observations; no new inference or invented positives. A prior-primary descriptive analyzer salvages complete four-arm blocks with cutoff/exclusions and no full-study/CI/semantic-quality claim. Degenerate bootstrap intervals are suppressed, and previous human labels are not transferred to these new tasks.

The dashboard now distinguishes issue diagnosis/review, benchmark source and memory policy; research defaults to live inference and retains explicit mock access. A real-endpoint regression caught and fixed a cache-policy null-credential bug before publication; health returned `ok`. Unchanged sealed repository summaries are cached with file-stat/seal/policy invalidation, and in-flight private call counts remain separate from sealed outcomes. The awaited eight-view JavaScript smoke passed, including auto-arrival and live/mock filtering.

Final validation checkpoint:385pytest tests passed in46.08seconds, Python3.11 grammar checks passed for154Python files, Ruff/Bandit passed, and the isolated PyArrow23.0.1 dependency audit found no known vulnerabilities. Pages preparation built455allowlisted files and passed closure/privacy/relative-path/workflow checks; no deployment or visibility change occurred. The polished paper is7main/12total pages,209abstract words, with neutral title and no editorial/build notes; classic and template variants share one source/evidence set and both passed exact-source/PDF/font audits. Actual author review and hackathon submission remain manual; no submission will be made autonomously.
# Multidisciplinary task docket — protocol5.0

Added a separate offline task generator, pinned BBH importer and mock rehearsal
for psychology, science, mathematics, humanities and defensive cybersecurity.
The actual imported catalog at `results/benchmarks/multidomain-evidence-v2` has
32 assignments /344questions, including20 original fictional evidence dossiers
and12 bundles adapted from MIT-licensed BBH at a fixed revision. Original dossier
families and imported item indices have explicit development/evaluation splits.

Prepared `results/campaigns/multidomain-next-v1` for96runs /7,200scheduled calls;
this is a docket, not a live launch. Marker and reporting-pressure challenges are
separate. Answers, missing evidence, unsupported verification claims and citation
existence have distinct scores. Semantic support and deceptive intent remain
unadjudicated. Bundled items are not claimed as long-horizon project execution.

Validation: `.venv/bin/python -m pytest -q` passed394tests in46.07seconds;
the full15-round rehearsal at `results/campaigns/multidomain-mock-v1` completed
96/96runs and7,200scripted responses, with all96seals independently verified.
Critical Ruff and medium/high Bandit checks passed on the new scripts. The frozen
`src/contagion` fingerprint remains unchanged. No inference endpoint, paid judge,
active queue, paper finding or public dashboard snapshot was changed. Live adapter
and closed publication-schema integration remain explicit launch blockers. See
[the docket](docs/MULTIDOMAIN_DOCKET.md) for commands, provenance and interpretation.
# Live recovery and multidisciplinary launch

Restored both private loopback SSH forwards with keepalives. Primary transport
recovery preserved42old completions and completed one further assignment before
a separately diagnosed output-length stop. Secondary output-only recovery also
hit its ceiling. All failed bytes, sealed artifacts and original states remain.
New protocol3.6/3.8 controllers use closed compact-report contracts rather than
silently modifying the frozen experiments; their composite call ledgers retain
3,011primary and630secondary prior requests. Remaining work stays within the
original5,200/1,600physical-request ceilings, with explicit supplemental wall
allowances. Runtimes across output-format cohorts must not be silently pooled.

Started `multidomain-live-active-20261108` on primary:72registered runs/4,500calls,
with five-domain live development checks before held-out evaluation. Observed
four completed runs/60responses without failure during verification. Queued the
25-run primary3.6 continuation,50-run RQ3 decomposition,264-run protocol3.7 long
benchmark and zero-inference batch report observer in that order. Secondary3.8
started independently and completed two recovery runs/30responses; a thermal
cooling pause was observed and remains governed by existing thresholds.

Added closed numeric protocol5.0 publication and a separate Research panel, with
domain/live/mock filters and loopback-only redacted trace inspection. Added
protocol3.5/3.6/3.7/3.8 labels and actual output-token ceilings to repository views.
Local HTTP validation observed `status=ok`,623repository attempts,76multidomain
summaries (72scripted mock and four live), bounded trace HTTP200 and foreign-Host
HTTP403. No public push, deployment, remote service change or hackathon submission.

Final validation:436pytest tests passed in103.83seconds; the guarded multidisciplinary
mock completed72/72runs and1,650scripted responses; awaited V8 smoke passed eight
views and explicit multidisciplinary filters. Configured Ruff/Bandit and Gitleaks
worktree checks passed. `src/contagion` and all active frozen dependencies were
preserved. See [active experiments](docs/ACTIVE_EXPERIMENTS.md) for current roots,
registered limits, source-version caveats and private monitoring instructions.
# Telemetry isolation and final recovery verification

The secondary3.8 allocation completed three runs, then preserved a failed attempt
after two valid responses and before its next HTTP request. Reproduction identified
the general `.env` parser rejecting an OpenRouter assignment. The operational
continuation `secondary-isolated-recovery-20261108` snapshots only two existing SSH
settings into a private hash-checked file; no original environment file, API key or
SSH credential was modified. Scientific protocol3.8 is unchanged. Its authoritative
ancestor debit is677requests, with21unfinished assignments/895scheduled calls and
923requests remaining under the original1,600ceiling. The first resumed15-response
run completed successfully; primary had eight completed multidisciplinary prechecks.

The dashboard uses isolated secondary settings as well. Final HTTP checks observed
healthy synchronization,626repository attempts,80multidisciplinary records (72mock,
eight live), private trace200 and foreign-Host403. The overview now exposes the
separate multidisciplinary inventory and expandable run panel rather than hiding
these results in older task-success metrics.

A full validation run exposed one legacy mock test reading operator `.env`; the
test was made hermetic with its own temporary environment file, without editing
the frozen pilot controller or credentials. Final `.venv/bin/python -m pytest -q`:
440passed in97.82seconds. Awaited eight-view V8 smoke and configured Ruff/Bandit/
Gitleaks checks passed. Both active workers and all registered predecessor plans
retain their immutable evidence; failures still stop rather than bypass guards.
# Submission publication checkpoint — November 9, 2026 UTC

- Final report: `report/paper.pdf`, eight main-text pages, fourteen total pages,
  209-word abstract. Required limitations/dual-use appendix retained; editorial
  draft/font notes removed. Figures and separate reference-checkpoint diagnostics
  regenerate from the recorded numerical freezes through the notebook.
- Final source suite: **499 tests passed in 142.60s**. A separate two-run mock
  pilot completed and regenerated analysis; it is engineering validation only.
- Awaited JavaScript runtime checks passed all eight views in both local and
  static modes, including redacted trace fallbacks and measured metric coverage.
- Exported458 validated public data files; privacy scan found no recognized
  categories. The exact463-file Pages artifact passed allowlist/source checks.
- Published trace candidates contain seven concretely agent-reviewed bounded
  excerpts /49 events, with exact content/source hashes. They are not full logs
  or human privacy approvals. Raw records remain unchanged and ignored.
- Runtime and installed-environment dependency audits found no known
  vulnerabilities. Gitleaks candidate/history scans and typed PDF inspection
  passed. Final hooks are rerun on the staged bytes before committing.
- The author explicitly permits public username, Git name and email, including
  the historical email identified by the audit. No history rewrite is needed.
  Credentials, private host details, operational telemetry and private paths
  remain excluded; heuristic redaction is not an anonymity guarantee.
- Primary remains stopped/reserved. Secondary recovery is21/21 complete;
  reference instrumentation has72 trained captures and two random checks.
  Pending larger allocations have not become findings. The paper cutoff stays
  fixed. No merge, repository visibility change, deployment or submission occurs.

### Final static dashboard boundary

Implemented an explicit `public-dashboard-freeze-1.0` manifest binding the final inventory, all four public numeric indexes, six separately counted result sources and every approved application/detail/trace asset. Default public pages make no private-status requests and schedule no refresh. Explicit private operator mode is available before a freeze; the final manifest overrides it. Filters, diagrams and approved static trace drilldowns remain interactive. Export refuses to mutate frozen data, and a fresh Pages build revalidates the exact asset hashes.

Observed verification: `.venv/bin/python -m pytest -q tests/test_freeze_dashboard.py tests/test_public_preview.py tests/test_public_trace_samples.py` → **9 passed in55.40s**; `git diff --check` passed. These checks used temporary copied snapshots; actual submission freeze and preview restart remain the lead operator's coordinated final step. No inference, SSH, deployment or raw-log modifications were performed. See `docs/FINAL_DASHBOARD_SNAPSHOT.md`.
# Final static submission checkpoint — November 9, 2026

The final paper now has7 main-text pages,16 total pages and a211-word abstract.
It retains Latin Modern and the original research questions. The five substantive
revisions add endpoint-focused contributions, actual scorer/human disagreement
examples, an RQ support/limits table, paired run-level variation and an updated
64-run responsibility summary. The original compact freeze is not expanded by
silently pooling exploratory results.

The final inventory covers1,412 indexed rows:583 live and829 mock. There are578
locally seal-verified distinct live trajectories,567 completed, and14,622 returned
responses; five older rows have explicit unresolved provenance. All eleven task
families and every indexed ID are recorded. Issue diagnosis and defensive cyber
have mock-only coverage. The72 trained reference captures include the original
six plus66 later captures; two random checks remain separate.

Collection closure marked30 local allocations STOP and verified both controller
leases idle without changing raw logs/states or remote machines. The public
dashboard is frozen at2026-11-09T02:59:37Z. Both local ports8765/8766 now serve the
same464-file Pages artifact; HTTP checks verified exact HTML/index/manifest bytes,
private endpoint404 and foreign-Host403. Frozen clients have no polling timers or
private requests, and collector startup refuses a submission freeze.

Final full pytest run: **524 passed in 217.32s**. Awaited JavaScript checks passed
eight views in operator, public-static and frozen modes. The source-only research
bundle regenerated figures and validated supplements offline. The final PDF
audit, privacy guard, Ruff and configured Bandit checks passed. Final staged
secret/privacy hooks and new-head CI remain part of the commit/review process.
Mock hardware fixtures also passed with simulated 1 GiB free; low-disk guards
still stop before inference. No production safeguard was weakened. No new model
calls, public deployment, merge or hackathon submission occurred.

## Judge landing page

Added a separate `/overview/` page for the existing GitHub Pages deployment,
with prominent README links to the final dashboard and judge guide. The page
distinguishes the compact study, full live/mock inventory and separate GPT-2
reference captures. Statistics come from the validated frozen inventory; the
published PDF passes the existing privacy and source-hash audit. The dashboard,
report and measurement code remain unchanged.

The combined build contains464 original dashboard files plus3 explicitly
allowlisted overview files. All ten focused checks passed, including the HTTP
route test with native loopback permission. Ruff and Bandit passed.
No new model calls or automatic merge, deployment or submission were performed.

The README now includes the supplied overview image and five real browser
captures of public model comparisons, approved trace excerpts, reference
interpretability, the neuron inspector and the judge guide. All six screenshots
passed visual/OCR privacy review and lossless metadata stripping. Exact hashes
and dimensions are bound by `docs/images/screenshots.json`; the privacy guard
rejects unreviewed images or unexpected PNG metadata. Three new screenshot
policy tests passed. The browser reported no page errors and the judge overview
fits a390px viewport. Full regression passed:531 tests in269.42s. Final manual
secret/history, publication privacy, Ruff and Bandit checks also passed. The
new overview requires human review and merge before Pages publishes it.
