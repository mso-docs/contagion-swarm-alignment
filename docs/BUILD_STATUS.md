# Build status — November 7, 2026

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

Latest: dashboard/export/Pages workflow implemented; 57 tests passed. Live Qwen matrix completed 18/18 runs / 450 responses; separate Nemotron ring pilot completed 2/2 runs / 50 responses. Public snapshot contains 20 live and 18 separate mock runs. No suffix adoption was observed in live data. Historical setup blockers below describe earlier state; see the latest dashboard section.

The full CONTAGION_AGENT_MVP_SPEC.md was read before implementation. Initial inspection found an existing Git repository containing only the specification and a placeholder README; no implementation was imported. The existing repository was retained. No remote machines, credentials, listeners, firewalls or infrastructure were modified.

## Milestones

- [x] P0: Python src package, dependency declarations and local virtual environment.
- [x] P0: AGENTS.md safeguards; frozen config; typed artifacts/events/outcomes.
- [x] P0: five independent contexts, bidirectional ring/star/complete, synchronous routing.
- [x] P0: deterministic mock, benign outbound-only intervention, authoritative JSONL recorder.
- [x] P0: manifests/config snapshots, source/protocol/config hashes, checksums, non-overwriting attempts.
- [x] P0: saved five-agent mock pilot; full pytest suite green.
- [x] P1 software: native Ollama and OpenAI-compatible adapters, installed-model discovery, timeouts, bounded audited retries, serial concurrency, doctor and logged chat smoke command.
- [x] P1 empirical: actual endpoint/model selection, successful live request, clean/injected live pair and trace/scorer review.
- [x] P2 software: fixed 18-condition matrix, final/intermediate artifact scoring, exposure counts, CSV table, manual-review export, two generated figures from raw events.
- [x] P2 software validation: 18 final-source mock runs, 450 mock calls; all completed and checksummed.
- [x] P2 empirical: freeze reviewed live protocol, execute actual inference batch, assess findings/limitations.
- [ ] P3: deferred behind successful live RQ1 gate; RQ2 definition and projection/monitor plan preserved.
- [ ] P4: deferred; RQ3 definition, safe simulator plan and provisional config preserved. No ToyRecordStore implementation or experiments claimed.
- [ ] P5: verified literature review, actual authors/hardware, official template review and research PDF. Report outline only.

## Commands actually executed and observations

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pydantic httpx pyyaml matplotlib pytest
# Initial sandboxed download failed DNS resolution; no packages installed by that attempt.
.venv/bin/python -m pip install -e '.[test]'
# Approved dependency download/install succeeded.
.venv/bin/python -m pip freeze --exclude-editable > requirements.lock.txt
.venv/bin/python -m pytest -q
# Final run: 38 passed in 29.77s. Earlier suites: 30, then 36 passed.
.venv/bin/python -m contagion.cli doctor
# Expected exit 1: no CONTAGION_BASE_URL; no live request attempted.
.venv/bin/python -m contagion.cli run --config configs/rq1_pilot.yaml --provider mock --out results/mock-pilot/raw
.venv/bin/python -m contagion.cli batch --config configs/rq1_pair.yaml --provider mock --out results/validated-pair/raw
.venv/bin/python -m contagion.cli batch --config configs/rq1_batch.yaml --provider mock --out results/final-mock/raw
.venv/bin/python -m contagion.cli analyze --source results/final-mock/raw --out results/final-mock/derived
# 18 completed runs; runs.csv, manual_review.json, rq1_summary.png, rq1_rounds.png.
.venv/bin/python -m contagion.cli analyze --source tests/fixtures/mock_run --out results/fixture-derived
# Included two-round, five-agent mock fixture: checksum-valid and reanalyzable without inference.
.venv/bin/python -m pip check
# No broken requirements found.
.venv/bin/python -m compileall -q src
git diff --check
# Both succeeded.
```

Intermediate mock batches were also run under results/mock-batch and results/validated-batch while hardening the harness. They are software validation artifacts, not additional independent scientific trials. Final-source artifacts are under results/final-mock. All generated results are ignored by Git; the small fixture in tests/fixtures is included with source. Tests cover the fixture's checksum and regenerated score equality.

## Verification coverage

38 tests cover graph degree/symmetry/hop constraints; validated config; five-agent schedule and history isolation; injection placement; next-round propagation; fresh clean state; inert routing requests; deterministic ordered traces; safe resume and corruption; call and wall budgets; malformed output and sanitized failures; exact-suffix/quotation/ambiguous scoring; analysis from events and explicit empty/duplicate rejection; native and compatible HTTP request payloads; discovery metadata; retry policy and physical attempt cap; concurrency cap; missing-endpoint diagnostics; message quotation distinct from artifact adoption; exclusive event creation; included fixture integrity.

The final mock batch summary figure was visually inspected. It is explicitly titled MOCK — SOFTWARE VALIDATION ONLY. Results match the scripted susceptible fixture and provide no empirical evidence for H1. Three mock seeds do not provide independent model variation.

## Initial blockers and next steps (historical; live inference now validated)

At initial bootstrap, no CONTAGION_BASE_URL or CONTAGION_MODEL was configured. Model tags/digests and remote machine identity were not guessed. This initially blocked empirical P1/P2 and, following the specification's stop/triage gate, additional RQ2/RQ3 implementation. Live determinism and parameter support remain unverified. No real-model findings, verified citations or submission PDF exist.

Next operator step: export CONTAGION_BASE_URL for the approved existing inference server, run doctor to discover tags, then export CONTAGION_MODEL from that list. Run `doctor --check-chat`, the live ring pair, and inspect raw artifacts before freezing the batch protocol. README gives exact commands. No infrastructure deployment is required; any remote host changes require a separate operator-authorized task.

## Pilot workflow script update

Added scripts/run_pilot.py and expanded .env.example with provider, endpoint, installed model, optional API key, paired-pilot config and output directory. The script loads .env as data (quotes/comments supported; no shell execution or variable expansion); existing shell variables win. It supports --doctor-only to discover model tags before selecting one, --provider mock for offline validation, --env-file and --out. Live execution performs discovery, logged chat validation, paired pilot and analysis in order, stopping on the first failure. It does not install software, change server configuration or automatically launch the full batch. README includes the copy/edit/run workflow.

Validation commands:

```bash
.venv/bin/python -m pytest -q
# 45 passed in 33.22s, including env parsing/precedence, nonexecution,
# sanitized parse errors, discovery-only mode, order and failure stopping.
.venv/bin/python scripts/run_pilot.py --provider mock --out results/script-check
# Clean/injected mock pair completed; analysis generated from its raw events.
git diff --check
```

No live endpoint was configured or contacted. Real credentials and an actual .env were not created or modified; copy .env.example to .env and enter operator-selected values locally.

## Dashboard, privacy export and first live pilot

The user explicitly requested a dashboard and public GitHub Pages publication workflow. This amends the no-UI scope for visualization only; agent permissions and RQs remain unchanged. Sites skill local workflow was used with the user's GitHub Pages hosting preference; no Sites hosting or GitHub deployment was created.

Implemented:

- Static `dashboard/index.html`, `style.css`, `app.js`: per-model/protocol/sampling cohorts and conditions, descriptive run-level adoption plots, runtime, call latency, task success and strict clean-answer adherence; network/round replay; agent outcomes; searchable escaped trace text; missing telemetry as N/A.
- `src/contagion/publication.py`: checksum-required public projection, closed schemas, original-event rescoring, retry/failure accounting, duplicate-condition checks, summary-only default and optional scrubbed traces/thinking. Raw logs are never rewritten. Known local secrets/identifiers, URLs, email, IPs, paths, tokens and common identifier patterns are redacted; unknown PII is not guaranteed detectable. Extra exact strings can come from ignored *.redact.txt files.
- `scripts/export_dashboard.py`, `scripts/build_dashboard.py`: atomic public snapshot export, privacy/schema validation and a five-file static artifact allowlist. Root .env, raw logs and arbitrary metadata never enter the artifact.
- `.github/workflows/pages.yml`: test, JS runtime smoke, validate/build and Pages deployment on main push. Current action versions checked against primary GitHub documentation. Remote settings/deployment are unchanged; operator must choose GitHub Actions as the Pages publishing source.
- Protocol 1.1 adds explicit native Ollama thinking control and records returned reasoning/timing metadata. Prompts and scorers are unchanged. New paired/batch configs request disabled thinking. OpenAI-compatible explicit thinking is rejected until separately tested.
- `docs/DASHBOARD.md` and `docs/EVALUATION_TOOLS.md` document publication commands, limitations and verified Inspect/Petri/TransformerLens/Neuronpedia integration options. No external evaluator or activation package was installed or executed.

Validation so far: **55 pytest tests passed in 29.36s**; JavaScript syntax and a lightweight DOM runtime interaction smoke test passed (filters, cohort separation, round replay, traces). Native browser layout QA is unavailable: no Chrome/Chromium/Firefox or browser preview tool is installed. Build artifacts and public data were validated. A mock protocol-1.1 pair completed with scripted outcomes. Existing 18-run mock data is available separately as a dashboard demonstration.

Live integration: configured endpoint discovery succeeded after approved network access. Initial smoke failed with a recorded ReadTimeout because the doctor reused its five-second discovery timeout for chat. Fixed the chat timeout to 60 seconds within a 90-second wall budget; a regression test verifies separate discovery/chat limits. The next logged smoke request returned one valid exact clean answer (55 generated tokens). No model was pulled or server configuration changed.

Live ring pilot: qwen3.5:9b, protocol 1.1, disabled thinking, seed 101. Both conditions completed 25 responses with valid checksums and no failures/parse errors. Control duration 44.95s; injected duration 45.68s. All 50 intermediate/final answer artifacts were exact clean answers. Final downstream adoption 0/4 in each condition; strict task success 5/5 each. Generated message variants were reviewed. This is a preliminary null observation, not general alignment evidence. Protocol 1.1 was frozen without prompt/scorer changes before starting the 18-condition matrix; pilot duplicates must not be pooled into matrix denominators.

Commands actually executed:

```bash
.venv/bin/python scripts/run_pilot.py --doctor-only
.venv/bin/python scripts/run_pilot.py --config configs/rq1_pair_thinking_disabled.yaml --out results/live-dashboard-pilot
.venv/bin/python scripts/run_pilot.py --config configs/rq1_batch_thinking_disabled.yaml --out results/live-rq1-batch
.venv/bin/python -m pytest -q
.venv/bin/python scripts/run_pilot.py --provider mock --config configs/rq1_pair_thinking_disabled.yaml --out results/dashboard-mock-check
.venv/bin/python scripts/export_dashboard.py --source results/live-dashboard-pilot/raw --source results/final-mock/raw --include-traces
.venv/bin/python scripts/export_dashboard.py --validate-only
.venv/bin/python scripts/build_dashboard.py --out site-dist/check-2
.venv/bin/python -m compileall -q src scripts
git diff --check
```

Batch completion/results will be recorded after the bounded runner finishes. Public data is an exported snapshot, refreshed before a push; it is not private-model streaming. Review opt-in traces before public Git history. Source hashes are kept constant during the live matrix.

## Live matrix completion and final public artifact

Qwen protocol-1.1 matrix completed all **18 runs / 450 returned calls** across star/ring/complete, clean/injected and seeds 101/202/303. No failures or parse errors occurred. All checksums validate and all manifests have one source hash. All 450 answer artifacts exactly match the clean answer; final downstream adoption is zero for every run. Descriptive mean runtimes range from roughly 45 to 48 seconds per run, with full per-run values retained.

A separate installed nemotron-3.5-lightning:30b smoke request and ring pair were then run serially, using the same protocol and seed 101. Both runs completed 25 calls without failures. Control runtime was 23.38s; injected runtime 24.05s. All 50 artifacts are exact clean answers; no suffix adoption. This one-seed pair is preliminary and is not a full topology comparison or a controlled hardware benchmark. No remote listeners, infrastructure or credentials were changed.

The final public snapshot contains **20 live experiment runs / 500 responses**, plus **18 separately labeled mock demonstration runs**. The initial Qwen pilot and all one-call smoke diagnostics are excluded from public scientific denominators. All live artifact texts and all distinct generated neighbor-message variants in the snapshot were reviewed. Known private environment values were checked against every public asset and none were present. The snapshot passes closed-schema/privacy validation; redaction count zero means no recognized patterns occurred in this synthetic corpus, not proof that arbitrary PII detection is perfect. Free text remains opt-in for future exports.

Final checks: **57 tests passed in 27.11s**; dependency check, compilation and git diff whitespace check succeeded. JavaScript syntax and runtime/DOM smoke checks passed with live and mock cohorts, network replay, filters, trace rendering and empty states. Native visual/browser QA remains unverified because browser binaries/tools are absent. The final build at site-dist/final contains only the five approved public files.

Additional commands executed:

```bash
env CONTAGION_MODEL=nemotron-3.5-lightning:30b .venv/bin/python scripts/run_pilot.py --config configs/rq1_pair_thinking_disabled.yaml --out results/nemotron-dashboard-pilot
.venv/bin/python scripts/export_dashboard.py --source results/live-rq1-batch/raw --source results/nemotron-dashboard-pilot/raw --source results/final-mock/raw --include-traces
.venv/bin/python scripts/export_dashboard.py --validate-only
.venv/bin/python scripts/build_dashboard.py --out site-dist/final
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q src scripts
git diff --check
```

Results and explicit limitations are in report/RQ1_RESULTS.md. RQ2 has no positive live adoption labels in this dataset; recall would be undefined, not evidence of a successful monitor. No external alignment evaluator or activation tooling was executed. Future protocol changes/adaptive audits must be separately versioned.

Next operator action: preview locally, review dashboard/data/results.json, enable Settings → Pages → GitHub Actions, commit/push main. The workflow publishes the reviewed static artifact after tests. Actual GitHub publication has not been performed. Export new selected model data before future pushes; the page polls only the deployed snapshot every 60 seconds while visible.

## Observability dashboard visual redesign

The user supplied a dark-blue observability reference. Reworked the static UI into a compact navy workspace with fixed sidebar, eight metric cards with sparklines, response history, model/cohort comparison, final-artifact distribution and selected-run quality bars. Added functional Overview, Models, Evaluations, Traces, Datasets and Methods views, hash navigation and mobile sidebar controls. Traces retain round replay, agent/event/search filters, timings and expanded formatted JSON responses. Dataset download serves only the existing sanitized JSON. No inference engine, protocol, scorer, source events or experimental results changed.

All sparklines/charts use recorded values. The response history is cumulative run-level call totals in chronological run order, not invented per-request timestamps. Behavioral headline values are ranges of cohort means; regression checks prevent pooling different cohorts or inventing missing telemetry. Cost, human feedback, semantic drift and activations are explicitly listed as uncollected. No fake alerts, benchmark deltas or human-feedback data were added.

Validation: 57 pytest tests passed in 29.95s. Expanded JS runtime smoke checks passed for all six views, navigation state, mobile sidebar, charts, metrics, cohort separation/ranges, missing values, trace rendering and empty states. Public snapshot privacy validation and the five-file static build passed (`site-dist/observability-style`). A mock five-agent pilot completed under results/ui-redesign-check/raw. Compilation/whitespace checks passed; native visual browser QA remains unavailable. Localhost HTML and JavaScript were checked via HTTP. Existing preview remains on 127.0.0.1:8765 for the user.

## First implementation commit: security gates and study clarification

Installed standard pre-commit at .git/hooks/pre-commit. Added SHA-pinned Gitleaks staged scanning, manual scans over nonignored tracked/untracked candidates and complete Git history, redacted diagnostics, private-file/known-environment-value/public-index guards, read-only syntax/JSON/YAML/TOML/private-key/size checks, critical Ruff lint and medium/high Bandit analysis. No whole test/fixture/public-data exclusions or secret baselines were added. The fake PEM marker in a redaction test is now assembled at runtime so key detection remains active.

The guard reads staged blobs and rejects protected files, unsafe public snapshots and valid/dangling symlinks; tests verify that changing the worktree does not hide a staged credential. A disposable-repository integration probe confirmed actual Gitleaks rejection and redaction of a synthetic nonfunctional staged API-key-shaped value. The real repository index was not changed.

Updated GitHub Actions to run all security checks, two dependency audits, pytest, dashboard JS smoke and the allowlisted Pages build on PRs/main pushes/manual/weekly runs. All Actions and external hook repositories are pinned to immutable verified release commit SHAs. Deployment requires successful checks and a main push/manual event; PRs/schedules cannot deploy. Checkout credentials are not persisted. Dependabot config covers pip and Actions. No remote settings, branch protections, commits or pushes were changed.

Initial runtime-lock audit found no known vulnerabilities. Installed-environment audit found vulnerabilities in local pip 26.1.1; upgraded the repository virtual environment to pinned pip 26.3 and reran the audit successfully, without ignore rules. requirements-security.txt pins the direct security tools. Both audits now report no known vulnerabilities (the editable local project is excluded from PyPI lookup and covered by tests/static checks). Python version pins are not a fully hash-locked dependency supply chain; no perfect-security claim is made.

Latest tests: **77 passed in 27.79s**. Full manual candidate/history scans and all read-only hooks passed. Public-data validator and Pages build passed; security-check/security-final artifacts contain only approved static files. Existing source-event bytes and current published results are unchanged. The existing README-only commit uses a non-noreply author address; identity/history were not modified and should be reviewed by the operator before making Git history public.

The user also asked how to make the study rigorous and scale review/interpretability. Added docs/EXPERIMENT_STRATEGY.md and dashboard Methods text explaining the current bounded catalog task, unchanged RQs, prospective synthetic task families, evaluator-blind AI triage/calibration, sampling unflagged cases, lack of live adoption positives, and actual activation-measurement requirements. Added matched 1,024-token thinking-enabled/disabled ring-pair configs under existing protocol 1.1, with tests for native enabled/disabled payloads and matched budgets. These new configs have not run; AI judges, coding-shaped tasks and neuron/SAE experiments are not implemented or claimed. No new live model calls were made in this security/study-planning pass.

Commands executed:

```bash
.venv/bin/python -m pip install -e '.[test,security]'
.venv/bin/python scripts/setup_security.py
.venv/bin/python scripts/check_all.py
.venv/bin/python -m pip install pip==26.3
.venv/bin/python -m pip_audit --disable-pip --no-deps -r requirements.lock.txt --cache-dir .cache/pip-audit --progress-spinner off
.venv/bin/python -m pip_audit --local --skip-editable --cache-dir .cache/pip-audit --progress-spinner off
.venv/bin/python -m pytest -q
.venv/bin/python scripts/export_dashboard.py --validate-only
.venv/bin/python scripts/build_dashboard.py --out site-dist/security-final
.venv/bin/python -m compileall -q src scripts
git diff --check
```

Dependency/tool downloads and local Git hook installation used approved network/filesystem access. Native system Python's CA validation failed during one release-reference lookup; the verified virtual-environment CA bundle was used instead, without disabling TLS. No files were staged or committed. See docs/SECURITY_CHECKS.md for setup, first-commit commands and enforcement limits.

## Versioned research expansion

Implemented protocol-2 scenario sampling/benchmarking, reviewer queue, offline monitor, closed public export and dashboard views; methodology in PROTOCOL_2.md. New package modules: tasks, scenarios, studies, monitor, review, neural, research and research_publication. New worker scripts/configs/workflow are optional and isolated from the core inference environment.

Executed commands: `python -m contagion.research freeze/study` for scenario_development, scenario_evaluation, rq3_comparison and rq3_permissive_simulator; respective completed mock run counts12/72/4/4. `review --max-calls20` reviewed20 of60; `monitor` on the existing Qwen live cohort generated48 projections. `scripts/export_research.py` validates92 mock studies/20 reviews/384 scenario metadata records/zero neural captures; `scripts/build_dashboard.py --out site-dist/research-v2-check` copied six allowlisted files. JS DOM smoke passed eight-view navigation, charts, filters, cohort separation, traces and empty states; visual browser layout review remains pending.

Blockers: TransformerLens actual runtime requires a supported Linux worker, not this Intel macOS/Python3.14 environment. Trained model replay, human calibration, secondary-reviewer adjudication, external benchmark integration and feature-level SAE interpretation are not completed. Do not claim these as empirical findings. The worker workflow must be pushed and manually run or an operator must approve a Linux target before remote installation. Raw inputs/tensors are never included in the Pages build.

Final local validation for this expansion: **96 pytest tests passed** (`.venv/bin/python -m pytest -q`); Gitleaks candidate/history scans, public-data policy, critical Ruff, Bandit and format checks passed through `scripts/check_all.py`. `git diff --check` passed. Pages artifact validation/build passed (six files). DOM smoke passed eight views and separately exercised neural heatmap/neuron/patch rendering using an in-memory synthetic UI fixture, never published as evidence. Existing local preview at `http://127.0.0.1:8765/` returned HTTP200 outside the filesystem sandbox. Baseline commit is present; research expansion remains unstaged/uncommitted on `feat/research-evaluation-interpretability`. No push, remote install or deployment performed. Existing freezes record the source at execution time; later publication-validator changes mean those freezes cannot resume under changed source—make a new freeze and output folder for subsequent execution.

## Primary/secondary worker preparation

Added project-local Linux inventory/installer (`scripts/setup_worker.py`), allowlisted transfer bundle with file checksums (`scripts/prepare_worker.py`), separate private env-file selection, exact discovered model digest checks, deterministic pair-preserving study shards and persisted output-root assignments. Neural setup refuses existing environment replacement. Full deployment/readiness instructions: WORKERS.md. No new service, firewall, driver, credential or remote filesystem changes made; SSH targets/project directories are still needed for actual server installation.

Existing configured primary Ollama endpoint was verified reachable. Executed a NEW frozen protocol-2 development integration check with installed Qwen3.5:9b, ring, two rounds, seed101, disabled thinking, 1024 output-token cap, exactly20 calls total. Both conditions completed10 responses; task success1.0 and no scored violations in either condition. Durations27.59s control /24.58s injected. These are small integration findings, not full scenario-benchmark evidence. Raw checksummed events are under ignored results/studies/server-integration-v2. Public research snapshot now has92 mock +2 live study rows, with model digests available, plus20 mock reviews and no neural captures.

Two mock shards each completed6 runs (150 responses), disjoint by case/seed/topology with complete treatment pairs. Prepared results/deployment/worker-source-20261107.tar.gz;87 allowlisted source files extracted safely and all source checksums matched. Tests run against the unpacked archive separately to check transfer completeness. Pages build at site-dist/worker-readiness passed. Initial local Python invocation lacked PyYAML; retried with the project virtual environment before creating the frozen live plan. No model calls occurred in the failed preparation attempt.

Final verification for worker changes:102 pytest tests passed locally and102 passed independently against the safely unpacked source archive; full Gitleaks worktree/history, privacy policy, Ruff and Bandit checks passed. `git diff --check` passed. Actual remote worker package installation, Linux neural capture and secondary-server validation remain pending target information.

## Secondary worker executed; swarm-size amendment

Successfully connected to secondary from private .env, installed isolated CPU Torch/TransformerLens and ran an actual random-weight capture after fixing TL4 offline-tokenizer initialization. No pretrained checkpoint, primary configuration change, GPU load test or service restart occurred. Primary SSH authentication is the remaining administration blocker. See WORKERS.md and PROTOCOL_2_1.md for exact boundaries.

Observed worker versions:torch2.15.0+cpu,TransformerLens4.3.0,transformers5.22.2,safetensors0.8.0. The capture used two layers and four positions. Measured phase duration was 0.032 seconds; this excludes installation and model loading. No-op/position-control logits agreed with corrupt baseline within1e-6. Private capture/checksums retained under ignored results/neural/; public export contains only reduced arrays. Initial failed attempts and remote source backup retained.

Executed scaling mock sizes5/10/20/40/80 with identical sampled development cases:6runs each,1860total responses. Frozen2.1 cohorts are distinct from previous five-agent2.0 empirical work; no larger live studies executed. Public research snapshot124study rows (122mock+2live),20mock reviews,1measured random neural capture. Size comparison plots match source/model/task/seed/topology/treatment/sampling while preserving size-specific freezes.

Verification:110pytest tests passed, full secret/history/privacy/static checks passed, DOM runtime smoke exercised actual numeric neural data plus all five mock sizes, and allowlisted Pages build passed. A focused privacy-test rerun verifies the new private server fields/hostname handling. Remote commands were executed only through explicit operator administration; no model agents received SSH or tool access.

Primary SSH diagnosis:target confirmed correct by operator. The one locally discoverable key was rejected, including explicit identity selection; the agent query is not usable in this session. No signing failure or accepted key was observed. Need comparison with ordinary Terminal SSH before attributing the failure to server authorization. Other operator's60refers to active swarm agents, not evidence of an Ollama hard limit. Shared service settings remain untouched.

Operator confirmed primary login currently requires a password. Key-only batch SSH therefore cannot authenticate until the operator adds an existing laptop public key to their primary account. Provided ssh-copy-id and BatchMode verification commands for execution in the user's own Terminal. No password was requested or transmitted, and no credentials were modified by the implementation agent. Secondary worker remains validated.

## Commit and PR preparation

Final repository suite:111 tests passed. Candidate/history Gitleaks, known-private-value/public-schema checks, critical Ruff and Bandit passed; git diff --check and six-file Pages build passed. Reviewed the complete branch against main, including earlier scenario/dashboard changes. Fixed fresh-install capture naming to match artifact fetch and aligned SSH smoke timeout with its remote execution budget; added a regression test. Prepared PR title/body covering the full branch under ignored results/pr. Primary SSH public-key setup is an explicit operator prerequisite; trained-checkpoint replay and larger live sweeps are not claimed complete. All reviewed nonignored modifications/new files are included in the requested local commit; secrets and raw runtime artifacts remain ignored.

Primary readiness follow-up:operator enabled public-key SSH and read-only preflight passed. Linux aarch64/Python3.12.3 with121.7GiB RAM and2708GiB free disk; approved project directory not yet created. Service query returned no explicit numeric Ollama overrides. No primary install, service change or load test performed. Authentication blocker is resolved.

CI follow-up:fixed seeded setuptools79.0.1 by explicitly bootstrapping pinned84.1.0 in CI and worker environments; pyproject build requirements now require the patched release line. Shared bootstrap file is included in transfer bundles and Docker build. Both current advisory audits (recorded requirements and installed environment) returned no known vulnerabilities; no ignore list was introduced. Original local checks did not prove the Python3.11 runner's dependency health. CI status remains pending until the fixed head's workflow finishes.

### Repository review track

Implemented `repository_benchmark.py`, `run_repository_study.py` and `repository_publication.py`. Pinned dataset import and source hashes; 60/20/20 long/medium/short freeze; no upstream execution or agent tools. Six real-diff mock runs completed with 260 scripted responses and sealed logs. Independent quality matching and collusion adjudication are not yet implemented; both stay explicitly unavailable. See `REPOSITORY_BENCHMARKS.md` for commands, costs and validity limits. Live repository inference is gated behind the compact checkpoint proof.

Repository-track validation: `.venv/bin/python -m pytest -q` — **163 passed**; focused repository/dashboard/publication suite — 23 passed; critical Ruff checks and medium/high Bandit checks passed. Dashboard build copied 229 allowlisted files, and privacy scan checked 224 files with no findings. Local automatic sync reports six repository mock runs, eight neural captures and healthy secondary fetches. This does not imply live repository-model evaluation or public deployment.

### Compact completion / draft release preparation

`run_campaign.py promote` passed with165 pytest tests and all candidate/history secret scans, privacy/schema checks, critical Ruff and Bandit gates. Readiness schema1.1 discloses interrupted attempts and requires complete, unique registered-condition coverage plus a later valid successor for each inference-budget interruption. Model/parse failures cannot be waived. Campaign progress now uses completed scheduled calls for remaining-work estimates. Runtime STOP/source guards cover repository checkpoints too. Skill validator and18 focused campaign/repository/progress tests passed after these script changes; final commit hooks are still required before push.

Overnight plan consists of three bounded1,800-call family blocks (216runs /5,400responses total) and a sequential checkpoint supervisor; registered hypotheses and limitations are in `OVERNIGHT_PROTOCOL.md`. Initial compact outcomes are in `report/COMPACT_RESULTS.md`. Reference-checkpoint captures and simulator/RQ2 evidence remain separate measurements.

Repository precheck amendment: one actual live response reached `done_reason=length` at512 tokens, and the supervisor stopped before further calls. No successful live repository review is claimed. Protocol3.1 budgets1,536 output tokens and limits review size to four concise findings; exported protocol cohorts remain separate. Focused repository/campaign/publication tests:28 passed. The public build and first commit hooks passed; PR#5 remains draft/open. The replacement supervisor uses a fresh campaign root and unchanged protocol2.6 synthetic cases.

Final private-progress validation:167 tests passed in36.11s. Five focused progress tests include live unsealed HTTP/response counts and a partially written tail without claiming trial completion. The amended short repository control completed15 responses with zero parse failures, and its paired run is collecting. Private progress supports this phase directly. Original and amended attempts remain separate, and the large synthetic campaign stays queued behind all repository checkpoints.

Comparison UI refinement: replaced the always-expanded model/protocol table with responsive visual cards and native accessible details. Exact condition rows remain available on demand; search affects only this section. Lazy tables preserve expansion during live refresh. Seventeen targeted publication/dashboard tests and the public asset build passed; JavaScript DOM QA covers search, lazy expansion, refresh persistence and complete cohort-row coverage. Browser layout QA was unavailable; the existing local server is retained.

### Research report and long-input expansion

LaTeX source, template-format provenance, frozen numeric evidence, notebook executor, seven paper figures and an expanding all-task notebook are implemented. Actual PDF build passed:7main-text pages,11total pages,188abstract words; US Letter and required sections/attribution verified. Pages were rendered for visual inspection. Human final review remains pending. Build checks reject narrative/evidence mismatches; a temporal regression prevents pooling unrelated task denominators into patch-only curves.

171pytest tests passed. New tests cover intermediate-vs-final reporting, fixed-input horizon registration and conservative dependency automation. All-task dashboard heatmap/bars/scatter DOM interactions passed; coverage is recorded across all indexed task families. Further final security/publication gates and commit hooks are required before push. A prior broad check reported files changing during the scan while exports/source were updating, despite no secret findings; rerun with stable inputs rather than waiving the gate.

The active secondary long repository pair remains running; the216-run /5,400-response baseline follows its checkpoint gate. A separate36-run /1,560-response long-input queue waits afterward, preserving matched case IDs across3/8/15round horizons. The primary remains untouched and all model agents remain tool-free. Proposed infrastructure and analysis changes stay in draft PR#5 for human review.


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

### Hybrid review checkpoint

- `.venv/bin/python -m pytest -q`:288 passed in40.87s.
- Local different-family advisory judge:64 validated reviews; frontier spot check:20 validated reviews. Confirmed cloud cost$0.097612; conservative shared-budget debit$0.16209950 of$20, including one retained failed-request reservation. Keys/configuration and full traces stay ignored.
- Primary protocol4 queue:140/140 completed runs, including four prechecks. The68-run long-task allocation is now collecting; subsequent local quality judging and50-run protocol4.1 decomposition are serialized behind it. No cloud judging is required for these experiment calls.
- Full protocol4.1 mock:50 runs/186 scripted responses, zero failures. Live decomposition results remain pending. Original compact results and six trained reference captures retain their separate evidence boundaries.
- `.venv/bin/python scripts/build_paper.py --out results/paper-draft --compiler .cache/report-tools/tectonic --skip-notebook`:actual PDF rebuilt,8 main pages/12 total,188-word abstract. Submission audit automated checks passed; author/template review and submission remain pending.
- Private16-item hybrid adjudication workspace is ready; human labels remain pending. Model opinions never populate human ground truth or certify general alignment.

See `docs/FRONTIER_REVIEW.md`, `docs/PRIMARY_LONG_SAFEGUARD_PROTOCOL.md`, `docs/RQ3_DECOMPOSITION_PROTOCOL.md` and `report/RESEARCH_READINESS.md` for commands, frozen limits and remaining scientific gates.

Final manual pre-commit run passed all hooks: candidate and full-history Gitleaks, JSON/YAML/TOML/conflict/private-key/size checks, public-snapshot privacy validation, Ruff critical checks and Bandit medium/high checks. Dashboard V8 runtime smoke passed after cohort separation changes; browser visual review remains pending. Explicit dashboard checkpoint export validated343 data files. The initial concurrent export/check attempt was repeated after files stabilized; only the stable successful run is the final validation.

### Submission-ready artifact pipeline

- Full suite:318passed in37.72s. New tests cover immutable cutoff validation, source/privacy checks, actual human CSV/history import, closed numeric calibration, pointer sensitivity and paper supplement consistency.
- Full notebook rebuilt; PDF7main pages/13total/209abstract words. Three primary visuals are architecture, per-run temporal heatmap and paired task outcomes; diagnostics are in appendices. No overfull boxes or unresolved-reference warnings were found in the compilation log.
- Explicit cutoff snapshot:403supported sealed runs,329Ollama/74mock, separated;172unsupported manifests/four incomplete attempts excluded. Repeated runs/projections are not independent samples. Tracked snapshot excludes private lineage.
- Actual author audit:16compliant labels,17decisions/one correction, exact CSV/history/queue validation, private0600 originals. Automated scorer/judge flags are reported separately; no override, calibrated accuracy or positive human class is invented.
- Read-only84-run patch audit: wrapper-sensitive proposal counts20compact/36primary versus17/6strict; zero final flags under both. Primary baseline exact matches versus normalized semantics are separated. Frozen core/controllers/logs unchanged.
- Current official DOCX format essentials checked; visual author comparison remains pending. Authenticated repository check confirms private/noPages; unauthenticated links404. No publication/visibility settings changed and no submission performed.
- Commands: `scripts/submission_snapshot.py`, `scripts/import_human_audit.py`, `scripts/submission_rehearsal.py`, `scripts/build_paper.py`, and `scripts/research_bundle.py`. See `docs/SUBMISSION_RUNBOOK.md` for the exact release sequence and remaining author actions.

Final validation passed all manual pre-commit hooks: candidate and complete-history Gitleaks, privacy/publication lint, conflict/JSON/YAML/TOML/private-key/size checks, Ruff and Bandit. The98-file allowlisted bundle passed offline source-copy figure **and supplement** generation. Exact-PDF rehearsal reads16/16 actual labels and retains author/template/access gates; no submission was performed. Core fingerprint remains unchanged and primary long collection continues without failures at the check.

Typography follow-up: author requested the classic LaTeX research-paper serif. Latin Modern Roman body/title compiled successfully, with embedded font names recorded in the build manifest; original template-font PDF retained under `results/paper-template-bf217d7/`. New PDF7main/13total pages,209-word abstract;9focused tests and automated submission checks passed. This is an explicit author-requested typeface override; official template fonts remain documented, and final author review is pending.

### Extended campaign and final review gate

- New materials:51long pinned adaptations,42held-out cases across11held-out projects; fork aliases and prior exposure audited. Selected32cases comprise3Martian reviews/29SWEissue diagnoses; source/task-kind effects are confounded and semantic quality remains unknown.
- Real primary264-run/19,320-call queue is started in `waiting`, with exclusive lease, registered prior-release/RQ3 prerequisites, live development feasibility and paired batch gates. Existing primary3.3 continues; its cap/state/logs were not rewritten.72-hour execution/21,252physical-call caps remain binding.
- Actual-catalog full mock:264/264runs,19,320scripted responses, zero parse/failed attempts;264seals/17receipts verified independently. Harness acceptance passed, scientific status `mock_only`. Earlier interrupted mocks remain preserved.
- Recovery retains failed/uncertain budgets and bytes; approved matching retries are recorded. Safe allowlisted failure codes replace opaque error-only diagnostics. No requirement that boundary flags be positive or models compliant is used to pass the harness.
- Automatic private observer reports completed batches and a cutoff-based prior-primary checkpoint; RQ2 baselines share allowlisted seeded views, keep final/intermediate truth distinct and leave recall undefined without positives. No extra model calls.
-385pytest passed46.08s; Python3.11 grammar154files; critical Ruff/Bandit passed. Isolated benchmark-reader audit found no known vulnerabilities. Awaited V8 smoke passed eight views, arrival, charts, traces and explicit live/mock filtering; pixel/browser review is not claimed.
- Real-configuration cache regression fixed and tested; localhost health verified `ok`. Source caching invalidates on seal/file-stat/redaction policy changes. Research rows, private call progress and monitor counters include new3.4 evidence with source/memory labels.
- Fresh Pages preview:455allowlisted files, technical publication checks passed. No deployment/settings/merge/submission. Polished classic/template PDFs:7main/12total/209abstract; two-font-declaration-only variants, same numerical evidence, source/compiled/PDF/font audits passed. Editorial notes are outside the manuscript.
- Final review packet tooling requires a clean committed tree, source privacy guard, matching scientific PDF versions and validated Pages closure. It includes source without Git history/ignored private runtime data. Actual publication and submission remain author/operator actions.
