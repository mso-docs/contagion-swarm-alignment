# Experiment observatory and public data

For current local export, remote sync, separate snapshot counts and refresh troubleshooting, start with [Live dashboard updates](LIVE_DASHBOARD.md). The commands below also document the original protocol-1 export path.

The dashboard in `dashboard/` is a static website for GitHub Pages. It uses local CSS/JavaScript/SVG, no CDN, no analytics, no server/API credentials, and no calls to the inference server. It shows per-model/protocol/sampling cohorts, network and treatment; completed/failed attempts; run-level adoption points; strict downstream clean-answer adherence; task success; runtime; call latency; available generation token counts/throughput; exposure; round-by-round network states; and searchable scrubbed event traces. Missing telemetry is N/A, never invented.

## Run and export

From the repository, after installing the package:

```bash
# Native Ollama with explicit thinking control, versioned as protocol 1.1.
# Reads the existing .env; changes no server configuration.
.venv/bin/python scripts/run_pilot.py \
  --config configs/rq1_pair_thinking_disabled.yaml \
  --out results/qwen-pilot \
  --export-dashboard
```

`--export-dashboard` refreshes a summary-only public snapshot after a successful pair. It omits free text by default. The pipeline stops on failed smoke/experiment calls rather than continuing a batch. The full 18-condition matrix remains a separate post-review step. The exact model comes from CONTAGION_MODEL in `.env` or the shell; the output directory name does not select a model.

For multi-model comparisons, export selected raw directories together. This replaces the public snapshot atomically; it does not append prior public data automatically:

```bash
.venv/bin/python scripts/export_dashboard.py \
  --source results/qwen-pilot/raw \
  --source results/nemotron-pilot/raw
```

Use only experiment `raw` directories, excluding one-call `smoke` diagnostic directories from scientific denominators. Sources are walked recursively. Only sealed, checksummed runs are accepted; incomplete unsealed traces are counted and skipped. Corrupt sealed runs abort the export. Failed/exhausted attempts remain visible but receive no final behavioral rates. Duplicate completed model/cohort/topology/treatment/seed combinations are rejected to prevent double-counting. Byte-identical raw logs are deduplicated. Source/model digest/protocol/sampling differences create separate cohorts; compare matched settings and account for retries/failures rather than treating attempts as independent trials.

To publish scrubbed event text, opt in locally, then review the resulting JSON before committing:

```bash
.venv/bin/python scripts/export_dashboard.py \
  --source results/qwen-pilot/raw \
  --include-traces
# Optional generated reasoning text requires both --include-traces and --include-thinking.
.venv/bin/python scripts/export_dashboard.py --validate-only
```

Export includes responses, artifacts, delivered/generated messages, intervention text and failure event types. It excludes full private request histories and arbitrary metadata. This is a public **oracle** view, never the restricted RQ2 monitor projection. Reasoning text is not mechanistic interpretability evidence.

## Privacy boundary

[Privacy lint and commit protection](PRIVACY_CHECKS.md) adds offline PII scans and blocks accidental staging of raw artifacts.

Raw oracle events/configs/manifests stay unchanged in ignored `results/` for auditability. Only the exporter creates public data. Public models use closed schemas with an explicit field allowlist. All public free-text trace fields and model labels pass through a scrubber. It removes known credential values from the local environment/.env, configured endpoint/hostname, local username/home paths, extra private denylist strings, common token formats, authorization/cookie assignments, URLs, email, IP addresses, common hostnames, shell host prompts, local paths, PEM key blocks and number patterns resembling identifiers. Valid model/protocol/source hashes are deliberately retained for reproducibility.

Use `--redact-file private.redact.txt` for extra exact strings, one per line, such as personal names or organization identifiers. `*.redact.txt`, `.env`, `.env.*` (except `.env.example`) and raw results are ignored. The parser reads .env as data without shell execution or expansion. Do not put secrets into tracked YAML or dashboard code.

**Heuristic redaction cannot guarantee removal of arbitrary names, addresses, encoded secrets or sensitive facts.** Summary-only mode avoids the principal free-text risk. Review opt-in traces before pushing to a public repository: removing data later from the deployed page does not remove it from Git history. Exported text may be altered by redaction; scientific scores are computed from private original events before redaction. Redaction counts are replacements, not numbers of unique secrets.

The build validates the public schema and scans allowed free-text fields again for recognized sensitive patterns. It copies allowlisted frontend assets, validated public snapshots and only referenced study-detail shards into a fresh artifact. Extra raw files or .env files in the source directory are never copied. The frontend inserts trace text via textContent and has a restrictive content security policy; model-generated HTML is displayed as text.

## Preview and GitHub Pages

```bash
.venv/bin/python -m http.server 8765 --bind 127.0.0.1 --directory dashboard
```

Open http://127.0.0.1:8765. The UI uses relative paths so repository subpath hosting works. It fetches the same-origin snapshot with cache bypass when loaded, when Refresh is clicked, and every 60 seconds while the tab is visible. Unchanged exports preserve the open trace view. There is no live access to the controller/model server.

1. In GitHub repository Settings → Pages, choose **GitHub Actions** as the publishing source.
2. Export and inspect `dashboard/data/results.json` locally.
3. Commit the dashboard, exporter, tests, workflow and sanitized snapshot, then push to `main`.
4. `.github/workflows/pages.yml` installs the package, runs tests, validates/builds the allowlisted artifact and deploys it to Pages. Use workflow_dispatch for a manual rebuild.

No GitHub credentials, remote repository settings or deployment were changed in this implementation. The workflow is prepared for your push. Pages updates after workflow completion, not instantaneously or during a private model run. Fresh local results must be exported before the push. For a local artifact check, use a fresh directory:

```bash
.venv/bin/python scripts/build_dashboard.py --out site-dist/preview-1
```

## Measurement limits and external tools

There is deliberately no general “alignment score.” Strict downstream boundary adherence means exact valid clean answers divided by four downstream agents. Adoption means the exact validated unauthorized suffix, not marker mention. Ambiguous answers and parse failures do not establish alignment. Aggregate behavioral headline rates are suppressed when multiple model/protocol/sampling cohorts are selected; use the cohort/condition table. Failed attempts are included in reliability/runtime evidence, excluded from final behavioral rates. Intermediate network states show observed partial artifacts, not guaranteed final outcomes or causal influence.

Inspect AI is the best next optional interoperability layer for evaluations/transcript review. Petri should be a separately versioned exploratory audit. TransformerLens/Neuronpedia need actual activation measurements with a compatible instrumented model; the current Ollama adapter does not provide those. See [EVALUATION_TOOLS.md](EVALUATION_TOOLS.md) for verified primary documentation and the proposed integration boundaries. No external package evaluation or neuron interpretation has been run merely because links appear in the dashboard.

## Observability workspace

The sidebar switches between Overview, Models, Evaluations, Traces, Datasets and Methods, with deep-link hashes and browser history support. The mobile sidebar opens from the menu button. All views share the evidence/model/network/condition filters. Model metrics show cohort-mean ranges rather than a pooled alignment score. Sparklines are actual run values ordered by start time. The response-history chart accumulates each run's returned and unreturned logical call totals; its time labels are run starts, not individual request timestamps. Distribution counts only final artifacts from completed runs. Quality bars refer to the explicitly labeled selected run.

The trace workspace includes round-by-round network state, agent outcomes, latency/token metadata, event IDs, agent/type/search filters and expandable formatted JSON responses. The dataset view provides a sanitized snapshot download and explicitly distinguishes collected telemetry from unavailable cost, drift, feedback and activation measurements. The visual reference influenced layout and color only; none of its example data was copied. After frontend changes, hard-refresh the local preview to load updated CSS/JavaScript.
