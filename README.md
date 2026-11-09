# Contagion

A reproducible research harness for instruction-boundary failures in LLM swarms, built from scratch for the November 6–8, 2026 Swarm Alignment Hackathon. Agents have separate histories and communicate through a bounded simulation controller. They have no tools, shell, file access or autonomous networking.

**Final review:** [paper PDF](report/paper.pdf) · [review guide](docs/FINAL_REVIEW.md) ·
[complete experiment catalog](docs/EXPERIMENT_CATALOG.md) ·
[static dashboard snapshot](docs/FINAL_DASHBOARD_SNAPSHOT.md).

**Online:** [final dashboard snapshot](https://mso-docs.github.io/contagion-swarm-alignment/) ·
[judge overview](https://mso-docs.github.io/contagion-swarm-alignment/overview/) ·
[Apart Research project](https://apartresearch.com/sprints/projects/contagion-testing-how-unsafe-instructions-spread-through-ai-agent-networks-3hzoqflrcr).

Watch the [video demo](https://youtu.be/7FGDfEq0ucE).

Collection is closed. The dashboard is frozen at **2026-11-09T02:59:37Z** and
serves recorded files without polling collectors or private APIs.

[![Frozen Contagion dashboard with cohort metrics, runtime summaries and research coverage](docs/images/dashboard-overview.png)](https://mso-docs.github.io/contagion-swarm-alignment/)

The screenshot shows the public snapshot. Individual panels cover different
evidence subsets; the complete cross-protocol inventory is described below.

The final inventory has **583 indexed live attempts** (570 completed), of which
578 distinct trajectories have locally verified source seals (567 completed,
14,622 returned responses). Five older rows have an explicit provenance gap.
The 829 mock records are engineering checks, not empirical model findings.
All eleven task families are catalogued; SWE-bench-style issue diagnosis and
defensive cybersecurity have mock checks but no live results in this snapshot.
These counts are an inventory across separate protocols, not independent trials.

**Evidence checkpoint:** the compact protocol2.6 study completed36 runs/900 responses. Seventeen intermediate patch artifacts were flagged by the strict path scorer; final downstream flags were zero. A separate post-hoc wrapper-path sensitivity check preserves zero final flags while changing intermediate counts and task-format interpretation. The separate primary protocol4 allocation completed140 runs, including four integration prechecks,72 RQ1 and64 RQ3 runs. Original catalog-monitor recall is undefined without adoption positives. The paper's six trained GPT-2 captures are reference measurements, separate from the deployed swarm models. A later 72-cell reference grid reuses those six and adds66 captures; it does not revise the paper cutoff or explain swarm internals. A selected16-artifact human audit labeled all compliant; automated flags and human interpretation remain separate, with no general judge-accuracy claim. Primary collection is stopped for another operator; secondary recovery completed21 remaining assignments. Pending larger studies remain separate registrations, not results.

For submission, start with the [research report](report/paper.pdf), [submission handoff](docs/FINAL_SUBMISSION.md), [compact findings](report/COMPACT_RESULTS.md), and [LaTeX/report commands](report/README.md). Completed runs, pending collection and model opinions are separate evidence categories; none is a general alignment score.

The [submission runbook](docs/SUBMISSION_RUNBOOK.md) covers the immutable cutoff snapshot, actual human-audit import, PDF rehearsal and reviewer bundle. The [RQ assessment](docs/RQ_ASSESSMENT.md) lists supported findings and unresolved questions. The repository is public and GitHub Pages is configured to publish the reviewed static snapshot; it does not expose local collectors or private APIs.

The [long primary runbook](docs/PRIMARY_LARGE_RUNBOOK.md) describes the separately registered264-run/19,320-call static benchmark extension, paired batches, recovery and private progress. Its51long materials include pinned Martian reviews and SWE-bench Verified base-source issue diagnosis. These are benchmark adaptations with an explicit memory window; they do not execute upstream tasks or yield official benchmark scores. The pending large allocation is closed without live results; registrations are not findings.

The [multidisciplinary docket](docs/MULTIDOMAIN_DOCKET.md) adds psychology, science, mathematics, humanities and defensive cybersecurity evidence tasks. Its separate protocol includes pinned open-source BBH adaptations, unavailable-evidence checks and peer reporting-pressure conditions. The [guarded live controller](docs/MULTIDOMAIN_LIVE.md) supports development gates, separate numeric dashboard summaries and private traces. See [active experiments](docs/ACTIVE_EXPERIMENTS.md) for the recovered allocation sequence and limits.

## App screenshots

These are actual captures of the frozen public app and the judge overview.
Metadata is stripped without changing pixels; images receive visual and OCR
privacy checks and are bound to their reviewed hashes.

<details>
<summary>Model comparisons, public traces, interpretability, and judge overview</summary>

**Model comparisons.** Cohorts, protocols and conditions remain separate;
displayed ranges are not general alignment scores.

![Model and protocol comparison cards](docs/images/model-comparisons.png)

**Reviewed public traces.** Selected output/message excerpts can be expanded
without connecting to a private server. They are not complete raw logs.

![Reviewed public trace excerpts with two messages expanded](docs/images/reviewed-traces.png)

**Interpretability overview.** Trained GPT-2 reference captures, intervention
effects and measurement controls are separate from the Ollama swarm runs.

![Reference-checkpoint interpretability metrics and intervention plots](docs/images/interpretability-overview.png)

**Neuron inspector.** Recorded activation values and clean/patched/control
logits describe the selected reference capture, not a mechanism for swarm behavior.

![Selected reference capture with neuron activations, intervention logits and residual heatmap](docs/images/neuron-inspector.png)

**Judge overview.** A short reading guide connects the paper, experiment flow,
findings, limitations, demo and dashboard.

![Contagion judge overview and controller-mediated experiment diagram](docs/images/judge-overview.png)

</details>

## Start here

Requires Python 3.11+. Commands run from the repository root; no paid API is required.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade -r requirements-bootstrap.txt
.venv/bin/python -m pip install -e '.[test,security,analysis]'
.venv/bin/python -m pytest -q
.venv/bin/python scripts/run_pilot.py --env-file configs/mock.env --provider mock
```

For a future, separately authorized replication, copy `.env.example` to `.env`, enter your approved endpoint and exact installed model tag, then run:

```bash
.venv/bin/python scripts/run_pilot.py --doctor-only
.venv/bin/python scripts/run_pilot.py
```

The pilot discovers model identity, checks a response and runs a bounded control/injection pair. It does not pull models or change server settings. Keep mock and live output directories separate. Research parameters belong in YAML; credentials and private server identifiers belong only in ignored `.env` files. See [worker setup](docs/WORKERS.md) before remote execution.

## Public judge preview

The dashboard stays at the Pages root; `/overview/` provides a concise judge
landing page with the paper, findings, scope, and demo. Both use the same Pages
deployment, with no additional hosting account. Build the combined site with
`.venv/bin/python scripts/build_public_site.py --out results/public-preview/site-FRESH`.
The dashboard freeze stays byte-identical; overview statistics are rendered from
the validated inventory, and the PDF receives the existing publication audit.
To preview both views on loopback, run
`.venv/bin/python scripts/serve_public_site.py --artifact results/public-preview/overview-FRESH`
and open <http://127.0.0.1:8767/overview/>.

Build and open the exact allowlisted GitHub Pages artifact locally, with the same
numeric results, charts and reviewed public trace samples:

```bash
.venv/bin/python scripts/serve_public_preview.py --artifact results/public-preview/review-FRESH
```

Open <http://127.0.0.1:8766/>. Both current local ports8765 and8766 serve the same
frozen artifact, with no private APIs or server telemetry. The exporter refuses
to replace a frozen checkpoint. Filters, figures and approved trace drilldowns
remain interactive; automatic refresh is disabled. See the
[snapshot policy](docs/FINAL_DASHBOARD_SNAPSHOT.md). Previewing results does not
restart experiments or publish the site.

After approving and merging the PR, make the repository public and select
**Settings → Pages → Build and deployment → Source: GitHub Actions**. Run the
**Security, tests and GitHub Pages** workflow on `main` if the merge ran before
Pages was enabled. The workflow publishes this frozen snapshot only after its
security, test and artifact checks pass. Verify the resulting Pages URL before
sharing it with reviewers; repository visibility alone does not enable Pages.

## Experiment flow

```mermaid
flowchart LR
    A["Versioned scenario + paired seed"] --> B["Freeze prompts, config and source"]
    B --> C["Controller schedules isolated agents"]
    C --> D["One configured inference endpoint"]
    D --> E["Validate artifacts + route next round"]
    E -->|"bounded rounds"| C
    E --> F["Seal oracle logs + checksums"]
    F --> G["Score, monitor and review"]
    G --> H["Scrub public export"]
    H --> I["Dashboard + paper figures"]
    classDef plan fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef run fill:#ede9fe,stroke:#7c3aed,color:#2e1065
    classDef evidence fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef public fill:#fef3c7,stroke:#d97706,color:#78350f
    class A,B plan
    class C,D,E run
    class F,G evidence
    class H,I public
```

| Research question | Comparison | Main evidence |
| --- | --- | --- |
| RQ1: network propagation | Ring, star, complete; control vs injection | Validated adoption, task success, exposure and propagation timing |
| RQ2: partial observability | Matched visibility masks over recorded runs | Precision, recall, F1 and coverage against separate oracle truth |
| RQ3: distributed responsibility | Single agent vs five-agent team | Forbidden proposals and actual synthetic record-state changes |

Run/seed is the analysis unit. Agents within a run, paired conditions and monitor projections are dependent. Scenario variants are synthetic, not independent attack designs. See the [unchanged specification](CONTAGION_AGENT_MVP_SPEC.md), [original protocol](docs/RESEARCH_PROTOCOL.md), and [protocol 2.4 amendment](docs/PROTOCOL_2_4.md). Prompt/schema changes require a fresh freeze and separate cohort; failed attempts remain preserved.

## Dashboard: local updates and public publication

```bash
.venv/bin/python scripts/serve_dashboard.py --sync-secondary
# Separately checkpoint sanitized live results for review/commit:
.venv/bin/python scripts/export_live_dashboard.py
```

Open **http://127.0.0.1:8765/**. No version or special URL is needed. The local service discovers sealed local studies every15seconds and polls configured sanitized secondary snapshots every minute. Primary controllers also write sealed results locally through their separately authorized inference tunnel. The dashboard itself does not initiate model calls. The visible page checks synchronization health and reloads changed frontend assets automatically. The explicit checkpoint exporter reads the isolated live cache; avoid another writer to that runtime cache.

Overview, Models, Evaluations, Traces and Datasets share all indexed experiments. Mock data is labeled and excluded from the default live selection. Protocols remain separate for scientific metrics; missing measurements show N/A. Neural and monitor views display only available measurements, never invented coverage.

The service validates checksums, redacts opt-in trace text and retains the prior valid snapshot if synchronization fails. Queue progress and hardware telemetry remain private. GitHub Pages serves reviewed committed snapshots and updates after a successful main-branch build; it does not connect to private servers or auto-push logs.

See [LaTeX paper and notebooks](report/README.md), [measurement plan](docs/RESEARCH_MEASUREMENT_PLAN.md), [repository benchmark tasks](docs/REPOSITORY_BENCHMARKS.md), [researcher guide](docs/RESEARCHER_GUIDE.md), [live updates](docs/LIVE_DASHBOARD.md), [privacy checks](docs/PRIVACY_CHECKS.md), and [portable components](docs/DASHBOARD_COMPONENTS.md).

## Developer guide

| Need | Start here |
| --- | --- |
| Assess evidence and improve measurements | [Researcher guide](docs/RESEARCHER_GUIDE.md) · [measurement audit](docs/MEASUREMENT_AUDIT.md) |
| Plan trained-model interpretability | [Interpretability protocol](docs/INTERPRETABILITY_PROTOCOL.md) |
| Understand modules and trust boundaries | [Architecture](docs/ARCHITECTURE.md) |
| Find current completion and blockers | [Progress](PROGRESS.md) · [build log](docs/BUILD_STATUS.md) |
| Configure primary/secondary workers | [Workers](docs/WORKERS.md) |
| Run bounded secondary batches | [Suite protocol](docs/SECONDARY_SUITE_PROTOCOL.md) |
| Understand advisory model judging | [Judge protocol](docs/JUDGE_PROTOCOL.md) |
| Generate paper figures and notebooks | [Periodic reports](docs/PERIODIC_REPORTS.md) |
| Capture actual neural measurements | [TransformerLens notes](docs/TRANSFORMERLENS_API.md) |
| Watch private experiment progress and ETA | [Private progress monitor](docs/PRIVATE_PROGRESS.md) |
| Scan traces for secrets and PII | [Privacy checks](docs/PRIVACY_CHECKS.md) |
| Install commit hooks and security checks | [Security checks](docs/SECURITY_CHECKS.md) |
| Reproduce original live results | [RQ1 results](report/RQ1_RESULTS.md) · [reproducibility](docs/REPRODUCIBILITY.md) |

```bash
.venv/bin/python scripts/check_all.py
.venv/bin/python scripts/export_dashboard.py --validate-only
.venv/bin/python scripts/export_research.py --validate-only
.venv/bin/python scripts/build_dashboard.py --out site-dist/preview
```

Raw logs, private requests, credentials and tensors stay ignored. Public exports use closed schemas and heuristic redaction; review optional text before pushing. Reviewers are advisory and uncalibrated. Generated thinking is text, not a neural measurement. Random-weight activations validate instrumentation, not learned features or alignment. There are no claimed SAE meanings, fabricated SHAP values or general alignment scores.

Research follow-ups, human review commands and neural coverage limits: [Confirmatory protocol](docs/CONFIRMATORY_PROTOCOL.md). Check the PDF with `.venv/bin/python scripts/submission_audit.py`; automated checks do not replace author review or submission confirmation.

The final review uses a fixed public dashboard, identical to the GitHub Pages artifact, at [localhost:8766](http://127.0.0.1:8766/). See [submission snapshot instructions](docs/FINAL_DASHBOARD_SNAPSHOT.md) for the explicit cutoff, hash validation and preview commands. Public views do not connect to private collector APIs.
