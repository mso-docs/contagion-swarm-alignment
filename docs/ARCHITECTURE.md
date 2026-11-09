# Architecture

The controller owns scheduling, routing and simulated state. Model output is untrusted data. Agents have independent histories; inference calls share a configured backend and run serially.

```mermaid
flowchart TD
    P["Config + scenario + immutable freeze"] --> C["Bounded round controller"]
    C --> H["Isolated agent histories"]
    H --> I["Inference adapter"]
    I --> J["Strict artifact validation"]
    J --> S["Task scorer / simulated action parser"]
    J --> R["Topology router: next-round delivery"]
    R --> H
    C --> O["Append-only oracle events"]
    S --> O
    O --> K["Sealed checksums"]
    K --> M["Allowlisted monitor projections"]
    K --> X["Public export + redaction"]
    X --> D["Static dashboard / reports"]
    classDef config fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef execution fill:#ede9fe,stroke:#7c3aed,color:#2e1065
    classDef evidence fill:#dcfce7,stroke:#15803d,color:#14532d
    classDef boundary fill:#fef3c7,stroke:#d97706,color:#78350f
    class P config
    class C,H,I,R execution
    class O,K,D evidence
    class J,S,M,X boundary
```

## Where to change things

| Area | Modules |
| --- | --- |
| Original protocol-1 runs | `config.py`, `agents.py`, `controller.py`, `scoring.py` |
| Protocol-2 scenarios and studies | `scenarios.py`, `tasks.py`, `studies.py`, `research.py` |
| Inference and budgets | `inference.py`, `models.py` |
| Routing and provenance | `topology.py`, `interventions.py`, `events.py`, `storage.py` |
| Restricted monitoring and advisory review | `monitor.py`, `review.py` |
| Suite queue and hardware pauses | `suite.py`, `resources.py` |
| Public schemas and reports | `publication.py`, `research_publication.py`, `reporting.py` |
| Dashboard | `dashboard/app.js` (domain adapter), `dashboard/widgets.js` (numeric charts) |

## Invariants

- Stable agent order; undirected graph edges; inboxes contain previous-round messages only. Each run starts with fresh histories and simulator state.
- Agents cannot select endpoints, execute tools or modify controller settings. Operator SSH helpers are separate administration scripts.
- Physical inference attempts, retries, rounds, output tokens and wall time are bounded. Requested backend settings do not prove deterministic model generation.
- Raw events contain oracle information. RQ2 sees an explicit restricted projection; hidden annotations and future events never enter monitor inputs.
- Sealed runs are checked before analysis. Failed attempts remain preserved; a killed, unsealed attempt is not a completed trial. One writer per output tree.
- Source/prompt/schema changes require a fresh freeze. Keep protocols and model digests separate in analysis. Checksums detect accidental alteration, not externally anchored tamper resistance.
- Public summaries and optional scrubbed details cross a separate privacy boundary. Private histories, endpoints, credentials and full tensors stay outside the static site.

See [experiment flow](../README.md#experiment-flow), [live publication](LIVE_DASHBOARD.md), and [component portability](DASHBOARD_COMPONENTS.md).
