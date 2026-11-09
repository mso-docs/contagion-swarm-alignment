# Independent judge: auxiliary evidence, not alignment ground truth

Every agent artifact is checked by deterministic task-specific scorers. The independent judge sees only the public task and bounded, visible task/message/output evidence under opaque sample/event IDs. Model identity, intervention condition and hidden scoring labels are excluded from its input. Labels are compliant, violation, refusal, ambiguous or unscorable; each substantive claim requires an existing evidence ID. Raw malformed responses are retained for advisory review rather than silently repaired.

The secondary deadline suite schedules at most32 local llama3.2:latest reviews per target model, after its initial block and before loading another target. Installed model digest is verified; no model is pulled. Judge calls are serial and included in the suite call budget. All outputs remain uncalibrated and queued for human review, including seeded clean audits. Scorer/judge disagreement is evidence to investigate, not an automatic override. Inspect a stratified human-labeled subset before reporting judge accuracy or calibrated probabilities. No global aligned/misaligned score is claimed.

OpenRouter is supported by the OpenAI-compatible adapter. Create an ignored `.env.judge` with CONTAGION_PROVIDER=openai, CONTAGION_BASE_URL=https://openrouter.ai/api/v1, an explicitly selected available CONTAGION_MODEL and private CONTAGION_API_KEY. Never paste the key into chat, logs or tracked files. Keep a strict `--max-calls` cap and separately approve any paid workload. Use only reviewed/redacted synthetic trace inputs for an external provider. No OpenRouter account, credential or paid call has been configured by this implementation.

Example local review outside a running suite's inference window:

```
.venv/bin/python -m contagion.research review --source PRIVATE_COMPLETED_RUNS --out results/reviews/local-judge --provider ollama --model llama3.2:latest --env-file .env.secondary --worker-label secondary --max-calls 32
```

For OpenRouter use `--provider openai --env-file .env.judge --model EXACT_SELECTED_MODEL`; thinking defaults to backend behavior so incompatible Ollama-specific flags are not sent to OpenAI-compatible servers. The judge is an additional behavioral measurement. It cannot expose Ollama hidden states or certify neuron meanings.
