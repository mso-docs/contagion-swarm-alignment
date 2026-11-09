# Reusable dashboard boundary

[Documentation home](README.md) · [Developer guide](DEVELOPMENT.md)

## Reuse the renderer, replace the adapter

```mermaid
flowchart LR
    D["Your project's data"] --> E["Your schema and privacy exporter"]
    E --> A["Your domain adapter"]
    A --> W["Reusable numeric widgets"]
    W --> U["Your application's UI"]
    classDef input fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef boundary fill:#fef3c7,stroke:#d97706,color:#78350f
    classDef adapter fill:#ede9fe,stroke:#7c3aed,color:#2e1065
    classDef output fill:#dcfce7,stroke:#15803d,color:#14532d
    class D input
    class E boundary
    class A adapter
    class W,U output
```

| Component | Portable? | Responsibility |
| --- | --- | --- |
| `dashboard/widgets.js` | Yes, with matching styles | SVG bars, histograms and confusion matrices |
| `dashboard/app.js` | Project-specific adapter | Contagion cohorts, filters and trace navigation |
| Public schema/exporters | Replace for another domain | Approved fields, redaction and validation |

<details>
<summary><strong>API, integration boundaries and measurement limits</strong></summary>

`dashboard/widgets.js` is a framework-free numeric plotting component with `bars(target, items,
options)`, `histogram(target, series, options)` and `confusion(target, counts)`. It accepts
labels and measured numeric data, renders SVG using DOM APIs, and never interprets model HTML.
Copy it with the axis-label/gridline styles or supply equivalent host styling.

`app.js` is the Contagion adapter: it maps the closed research snapshot into widgets and adds
task/model/size/outcome filters, run details and trace navigation. `research_publication.py` is
this project's privacy/schema boundary. Other projects should provide their own versioned
adapter/exporter rather than weakening that boundary. The whole application is not yet a general
packaged dashboard SDK; the reusable rendering layer is separated now so later packaging can
preserve the working experiment UI.

The Interpretability view distinguishes binary behavioral monitor confusion matrices, measured
residual/MLP activations and controlled patch logits. Missing classifier ROC/AUC, SHAP
explanations, SAE concepts and calibrated judge probabilities are unavailable, not fabricated.
Token-position tiles are measured activations with token text/IDs withheld. Run rows link to
bounded scrubbed trace files with explicit omission/truncation notices; complete authoritative
logs remain private.

</details>
