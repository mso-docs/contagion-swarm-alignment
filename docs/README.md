# Documentation

[Project README](../README.md) · [Paper](../report/paper.pdf) ·
[Public dashboard](https://mso-docs.github.io/contagion-swarm-alignment/)

Start with the task you want to complete. Current guides are listed first;
protocols, detailed runbooks and historical notes stay available below.

**Current state:** collection is closed, the public snapshot is fixed, and normal
development/report reproduction needs no private server access. Historical
commands do not authorize restarting submitted queues.

## Pick a path

```mermaid
flowchart TB
    H["What do you need?"] --> D["Develop the harness"]
    H --> R["Review the research"]
    H --> V["Explore the app"]
    H --> P["Rebuild the paper"]
    D --> A["Setup, architecture and security"]
    R --> E["Catalog, cohorts and limitations"]
    V --> S["Dashboard, traces and reference captures"]
    P --> N["Notebooks, figures and LaTeX"]
    classDef home fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef develop fill:#ede9fe,stroke:#7c3aed,color:#2e1065
    classDef research fill:#dcfce7,stroke:#15803d,color:#14532d
    classDef review fill:#fef3c7,stroke:#d97706,color:#78350f
    class H home
    class D,A develop
    class R,E research
    class V,S,P,N review
```

| Task | Guide |
| --- | --- |
| Set up, test and contribute | [Development](DEVELOPMENT.md) |
| Understand the controller and boundaries | [Architecture](ARCHITECTURE.md) |
| Interpret results and denominators | [Researcher Guide](RESEARCHER_GUIDE.md) |
| Use the public dashboard | [Dashboard](DASHBOARD.md) |
| Port the plotting components | [Dashboard Components](DASHBOARD_COMPONENTS.md) |
| Review traces and screenshots | [Privacy Checks](PRIVACY_CHECKS.md) |
| Install hooks and understand CI | [Security Checks](SECURITY_CHECKS.md) |
| Reproduce committed artifacts | [Reproducibility](REPRODUCIBILITY.md) |
| Generate tables, notebooks and figures | [Periodic Reports](PERIODIC_REPORTS.md) |
| Understand the immutable checkpoint | [Final Dashboard Snapshot](FINAL_DASHBOARD_SNAPSHOT.md) |
| Edit the report and export PDF | [Paper guide](../report/README.md) |
| See every recorded task family | [Experiment catalog](EXPERIMENT_CATALOG.md) |

## Explore visually

<details>
<summary><strong>Public traces and reference interpretability</strong></summary>

![Reviewed public trace examples](images/reviewed-traces.png)

![Reference-checkpoint intervention measurements](images/interpretability-overview.png)

Trace samples are bounded public excerpts. Reference captures are separate
GPT-2 studies, not activations recorded inside the deployed Ollama swarms.

</details>

## Reference library

Versioned protocols retain their original method definitions. Historical run
notes may contain earlier counts or resolved blockers; use the
[final catalog](EXPERIMENT_CATALOG.md) for completed evidence.

<details>
<summary><strong>Research questions, protocols and measurement</strong> · 18 guides</summary>

- [Confirmatory follow-ups and submission gates](CONFIRMATORY_PROTOCOL.md)
- [Experiment catalog](EXPERIMENT_CATALOG.md)
- [What Contagion tests and how to expand it](EXPERIMENT_STRATEGY.md)
- [Protocol4 patch-monitor evaluation (registered before outcome inspection)](FOLLOWUP_MONITOR_PROTOCOL.md)
- [Literature review — pending verification](LITERATURE_REVIEW.md)
- [Measurement audit](MEASUREMENT_AUDIT.md)
- [Protocol 2 amendment: synthetic scenario benchmarks](PROTOCOL_2.md)
- [Protocol 2.1: exploratory swarm-size scaling](PROTOCOL_2_1.md)
- [Protocol 2.2 amendment before the extended held-out suite](PROTOCOL_2_2.md)
- [Protocol 2.3: explicit response envelope before held-out evaluation](PROTOCOL_2_3.md)
- [Protocol 2.4: answer-field contract clarification during development](PROTOCOL_2_4.md)
- [Protocol 2.5: exact name-only record summaries](PROTOCOL_2_5.md)
- [Protocol 2.6: simulated-action field contract](PROTOCOL_2_6.md)
- [Task complexity and measurement plan](RESEARCH_MEASUREMENT_PLAN.md)
- [Research protocol](RESEARCH_PROTOCOL.md)
- [RQ3 decomposition follow-up](RQ3_DECOMPOSITION_PROTOCOL.md)
- [Research-question evidence and claim limits](RQ_ASSESSMENT.md)
- [Threat model](THREAT_MODEL.md)

</details>

<details>
<summary><strong>Benchmark tasks and multidisciplinary studies</strong> · 10 guides</summary>

- [Model, role and topology calibration](DIVERSITY_CALIBRATION.md)
- [Model/topology calibration publication boundary](DIVERSITY_PUBLICATION.md)
- [Offline monitoring for long benchmark adaptations](LARGE_BENCHMARK_MONITOR.md)
- [Protocol3.7 output-budget amendment](LARGE_OUTPUT_BUDGET_V37.md)
- [Long static benchmark materials](LONG_BENCHMARK_MATERIALS.md)
- [Matched long-input review horizon pilot](LONG_HORIZON_PROTOCOL.md)
- [Multidisciplinary evidence docket](MULTIDOMAIN_DOCKET.md)
- [Guarded multidisciplinary live allocation](MULTIDOMAIN_LIVE.md)
- [Protocol5.1 question-coverage continuation](MULTIDOMAIN_QUESTION_COVERAGE_V51.md)
- [Repository review experiments — protocol 3.0](REPOSITORY_BENCHMARKS.md)

</details>

<details>
<summary><strong>Workers, queues and historical recovery</strong> · 15 guides</summary>

- [Experiment status and public checkpoint](ACTIVE_EXPERIMENTS.md)
- [Large primary static benchmark activity](LARGE_PRIMARY_BENCHMARK_PROTOCOL.md)
- [Overnight collection plan — protocol 2.6](OVERNIGHT_PROTOCOL.md)
- [Long primary benchmark allocation](PRIMARY_LARGE_RUNBOOK.md)
- [Long-review safeguard analysis and quality adjudication](PRIMARY_LONG_ANALYSIS.md)
- [Primary long-review safeguard comparison](PRIMARY_LONG_SAFEGUARD_PROTOCOL.md)
- [Primary output-budget amendment](PRIMARY_OUTPUT_RECOVERY.md)
- [Reviewed primary transport recovery](PRIMARY_RECOVERY_CONTINUATION.md)
- [Primary RQ1 validity audit: path conventions](PRIMARY_RQ1_VALIDITY.md)
- [Private experiment progress](PRIVATE_PROGRESS.md)
- [Secondary bounded-report recovery](SECONDARY_BOUNDED_RECOVERY.md)
- [Secondary output-budget recovery](SECONDARY_OUTPUT_RECOVERY.md)
- [Secondary-only extended suite (prospective)](SECONDARY_SUITE_PROTOCOL.md)
- [Secondary telemetry environment recovery](SECONDARY_TELEMETRY_ISOLATION.md)
- [Primary and secondary AI workers](WORKERS.md)

</details>

<details>
<summary><strong>Judges, interpretability and integrations</strong> · 7 guides</summary>

- [Local machine-advisory repository quality review](ADVISORY_REPOSITORY_JUDGE.md)
- [Evaluation and interpretability tools](EVALUATION_TOOLS.md)
- [Expanded trained-checkpoint reference grid](EXPANDED_NEURAL_REFERENCE.md)
- [Budgeted frontier second-opinion review](FRONTIER_REVIEW.md)
- [Interpretability: evidence ladder](INTERPRETABILITY_PROTOCOL.md)
- [Independent judge: auxiliary evidence, not alignment ground truth](JUDGE_PROTOCOL.md)
- [TransformerLens 4 integration notes](TRANSFORMERLENS_API.md)

</details>

<details>
<summary><strong>Publication, audits and project history</strong> · 11 guides</summary>

- [Build status — November 7, 2026](BUILD_STATUS.md)
- [Dependency updates and human review](DEPENDENCY_UPDATE_POLICY.md)
- [Final author review](FINAL_REVIEW.md)
- [Submission handoff](FINAL_SUBMISSION.md)
- [Large-study acceptance and claim limits](LARGE_STUDY_ACCEPTANCE.md)
- [Keep the dashboard current](LIVE_DASHBOARD.md)
- [Reviewed static dashboard publication](PUBLICATION_READINESS.md)
- [Optional three-minute walkthrough](SUBMISSION_DEMO.md)
- [Human audit and submission rehearsal](SUBMISSION_REHEARSAL.md)
- [Final submission runbook](SUBMISSION_RUNBOOK.md)
- [Submission evidence cutoff](SUBMISSION_SNAPSHOT.md)

</details>

## Reading conventions

- The page introduction tells you its purpose and current status.
- Expand reference sections only when you need implementation detail or history.
- Mermaid diagrams describe architecture/process unless labeled as measured data.
- Screenshots show actual public UI; scientific plots come from recorded inputs.
- Raw logs, requests, credentials, endpoints and tensors remain private.

To improve a guide, follow the [documentation conventions](DEVELOPMENT.md#writing-developer-documentation).
