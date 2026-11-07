# Evaluation and interpretability tools

This is an integration assessment, not a claim that any external evaluation suite or interpretability experiment has run. Primary documentation was checked during implementation on November 7, 2026. No packages, remote services, accounts or infrastructure were changed for this assessment. Pin and test exact package versions before adopting an integration.

## What belongs in this experiment now

Use Contagion's controller JSONL as the authoritative record and build the public dashboard from a separate sanitized projection. Show model/tag/digest, protocol version, topology, treatment, seed, completion status, run/call duration, parse failures, exposure counts, first downstream adoption, maximum distance, final artifact adoption, strict task success and the denominators behind every rate. Compare model cohorts within matched conditions; preserve control/intervention pairing and failed-run counts.

Do not label an aggregate a general **alignment score**. A clearly defined instruction-boundary compliance percentage is a narrow task-specific behavioral result. Missing/ambiguous artifacts and failed runs must not become automatic evidence of alignment. A monitor or LLM judge is a prediction layer; validated artifact behavior remains the ground truth. Reasoning text is generated text, not a faithful measurement of internal causation.

| Tool | Best fit | Recommendation |
|---|---|---|
| Inspect AI | Reusable evaluation tasks, model adapters, scoring and transcript review | Useful optional integration after the live paired pilot; keep the Contagion router and oracle log authoritative. |
| Petri | Exploratory auditor/target interactions and judge rubrics | Separate exploratory study only; do not silently substitute adaptive audits for the frozen RQ1 matrix. |
| TransformerLens | Activation capture, patching and mechanistic tests | Separate instrumented-model replay study; not derivable from existing Ollama text logs. |
| Neuronpedia | SAE features, activation/attribution displays and model-internals exploration | Optional later visualization of actual measured, compatible artifacts; never synthesize neuron plots from marker frequencies. |

## Inspect AI

Inspect supports local providers including Ollama and OpenAI-compatible interfaces. It is therefore a plausible host for an explicit future Contagion task/solver/scorer adapter. Compatibility must preserve the five separate contexts, next-round graph routing, exact budgets, matched seed conditions and separate oracle/monitor views. A generic Inspect log viewer does not automatically understand Contagion JSONL: implement and test a schema conversion or run a dedicated adapter rather than merely renaming files. [Model documentation](https://inspect.aisi.org.uk/models.html)

Inspect can produce a static transcript viewer with:

```bash
inspect view bundle --log-dir <sanitized-inspect-logs> --output-dir <new-viewer-directory>
```

The bundled viewer can be hosted on GitHub Pages and requires HTTP range requests. This is useful for a later optional transcript subsite; the current dashboard can remain lightweight and consume its own allowlisted JSON. Bundle only already-sanitized Inspect logs: the bundling operation is not a privacy sanitizer. [Log Viewer publishing](https://inspect.aisi.org.uk/log-viewer.html), [CLI reference](https://inspect.aisi.org.uk/reference/inspect_view.html)

## Petri

Petri generates audit scenarios, coordinates auditor/target turns, supports simulated tools/rollbacks and uses judge rubrics to assess transcripts. Those capabilities may help discover benign follow-up hypotheses or review ambiguous behavior, but adaptive auditing introduces a different experimental procedure and additional model calls. Keep it out of the fixed RQ1 treatment unless a new protocol explicitly defines it. Any future adapter must expose only the existing controller-mediated synthetic environment; no real tools or arbitrary external actions. Petri judge scores are rubric-specific observations, not universal alignment measurements. Current upstream material identifies version 3 and notes incompatible internal API changes from version 2, so do not copy older integration snippets untested. [Primary repository README](https://github.com/meridianlabs-ai/inspect_petri), [Project documentation](https://meridianlabs-ai.github.io/inspect_petri/)

## TransformerLens and Neuronpedia

TransformerLens provides model hooks and activation caches, including `run_with_cache`; its analysis tools operate on model execution, cached tensors and, where required, gradients. Our existing Ollama chat-response adapter records text and response metadata, not hidden activations, attention tensors or gradients. Consequently, existing traces cannot support a real logit lens, neuron activation map, SAE feature attribution or causal patching result. This limitation follows from the data available to the controller, not a blanket claim that the model families are unsupported. [Activation demo](https://transformerlensorg.github.io/TransformerLens/generated/demos/Main_Demo.html), [Analysis tools](https://transformerlensorg.github.io/TransformerLens/content/analysis_tools.html)

A defensible follow-up would replay selected clean/injected prompts through an instrumented backend with verified support for the exact checkpoint, tokenizer, chat template, precision and architecture. Record how this differs from the original quantized Ollama execution; a replay is a separate experiment and cannot retroactively reveal the original run's activations. Measure clean/corrupt activation differences and test interventions before making causal claims.

Neuronpedia displays actual internal-model artifacts, including SAE features, activations and attribution graphs. Its self-hosted system has database and inference components; that full system is not a static GitHub Pages app. Precomputed sanitized measurement exports could be visualized statically, while using a public API or uploading text would require an explicitly selected compatible model/data source and a privacy review. No such upload is part of the current implementation. [Introduction](https://docs.neuronpedia.org/), [Self-hosting architecture](https://docs.neuronpedia.org/open-source/self-hosting)

## GitHub Pages publication

A repository workflow can build and deploy a static artifact with `configure-pages`, `upload-pages-artifact` and `deploy-pages`. The deployment job needs `pages: write`, `id-token: write` and the `github-pages` environment. Enable GitHub Actions as the Pages publishing source in the repository settings. [Official workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

A push-triggered deployment publishes a new snapshot after its workflow completes; it is not a live connection to a private inference server. The dashboard should display its export timestamp and refresh its static JSON periodically if desired. Never put an endpoint, API key or raw results directory into the deployment artifact. Sanitization must happen locally before committing data to a public repository: removing sensitive content only during deployment would still leave it in Git history. Automated redaction can reduce risk but cannot guarantee removal of all PII or infer every sensitive fact from arbitrary natural language. Prefer a minimal allowlisted projection and review the exact export before publication.
