# Reusable dashboard boundary

`dashboard/widgets.js` is a framework-free numeric plotting component with `bars(target, items, options)`, `histogram(target, series, options)` and `confusion(target, counts)`. It accepts labels and measured numeric data, renders SVG using DOM APIs, and never interprets model HTML. Copy it with the axis-label/gridline styles or supply equivalent host styling.

`app.js` is the Contagion adapter: it maps the closed research snapshot into widgets and adds task/model/size/outcome filters, run details and trace navigation. `research_publication.py` is this project's privacy/schema boundary. Other projects should provide their own versioned adapter/exporter rather than weakening that boundary. The whole application is not yet a general packaged dashboard SDK; the reusable rendering layer is separated now so later packaging can preserve the working experiment UI.

The Interpretability view distinguishes binary behavioral monitor confusion matrices, measured residual/MLP activations and controlled patch logits. Missing classifier ROC/AUC, SHAP explanations, SAE concepts and calibrated judge probabilities are unavailable, not fabricated. Token-position tiles are measured activations with token text/IDs withheld. Run rows link to bounded scrubbed trace files with explicit omission/truncation notices; complete authoritative logs remain private.
