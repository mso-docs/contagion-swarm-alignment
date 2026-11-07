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
