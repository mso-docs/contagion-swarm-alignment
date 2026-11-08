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
