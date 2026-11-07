# Build status — November 7, 2026

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
