# Progress

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
