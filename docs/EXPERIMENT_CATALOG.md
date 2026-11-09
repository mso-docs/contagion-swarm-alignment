# Experiment catalog

This final metadata supplement freezes the four public dashboard snapshots by SHA-256. It does not change the paper's original analysis cutoff or promote exploratory runs into its confirmatory sample.

The software suite observation is **499 passed pytest tests**. These are engineering checks, not model experiments. The snapshots contain **1412 indexed agent-run rows**: 583 live rows (570 completed) and 829 mock rows.

Raw seal reconciliation verifies 1407 indexed rows and leaves 5 unmatched. Within those published indexes, deduplicating identical authoritative event bytes yields **578 distinct verified live trajectories**, 567 completed, and 14622 returned responses; 0 repeated index rows are excluded. Identical files copied between local indexes are one trajectory. Unmatched rows remain indexed evidence, excluded from verified-unique totals. Different failed/retry event logs remain different attempts. This is not a census of every historical private raw attempt: latest-record indexes can retain failure counters without publishing each prior attempt. A trajectory is not an independent seed or an independent scientific comparison.

Other evidence comprises 72 trained GPT-2 reference captures, 2 random-weight instrumentation checks, 1152 dependent offline monitor cells and 84 advisory reviews. These are not additional swarm runs. Diversity calibration has 0 published records; queued work is not a result.

## Tasks and research purpose

| Family | Task and observable endpoint | Research role |
|---|---|---|
| catalog | Summarize fictional public records; exclude unauthorized marker | RQ1 propagation; RQ2 offline detection |
| provenance | Evidence/source attribution over synthetic notes | Exploratory instruction-boundary robustness |
| patch | Synthetic proposed patch and allowed edit boundaries | RQ1 follow-up; narrow artifact deviation |
| record | Summarize public catalog while protected fictional state stays unchanged | RQ3 attempted action versus simulated state violation |
| code_review | Review pinned open-source PR diffs; report findings without claiming unexecuted tests | Exploratory long-input boundary tests; no executable agent tools or official benchmark score |
| issue_diagnosis | Diagnose SWE-bench Verified issues from reference-localized base-code windows; propose evidence-supported findings | Exploratory static diagnosis, not executable patch solving or official SWE-bench success |
| psychology / science / mathematics / humanities / defensive_cybersecurity | Answer bounded evidence questions with citations, confidence and explicit unknowns | Exploratory honesty/evidence controls; no adjudication of intent or spontaneous collusion |

Repository inputs come from withmartian/code-review-benchmark and princeton-nlp/SWE-bench_Verified. The issue windows use reference localization, a disclosed selection limitation; they are not full repository workspaces. Repository memory policies are full_history or original_task_plus_last_two_own_rounds, recorded per run alongside complete_pinned_pr_diff, reference_localized_base_windows or legacy_unspecified context selection.

Length means controller rounds and recorded input size, not wall-clock human task duration. Coding tasks review supplied material; models never edit repositories or run tests. Neural captures measure a separate GPT-2 reference checkpoint, not Ollama swarm internals or general alignment.

## Complete indexed cohort inventory

All individual public IDs, source index, exact model/protocol/phase/condition/status, calls, rounds and agent counts appear in [final_inventory.json](../report/data/final_inventory.json). Source references are public dashboard index names; no private source paths or request histories are exported. A missing horizon remains null rather than inferred. Retained multidisciplinary failure counters are supplementary provenance, not added to latest-record calls or silently treated as completed runs.

| Index | Protocol | Model | Family | Phase | Condition | Status | Rows | Responses | Round range |
|---|---|---|---|---|---|---|---:|---:|---|
| followups | 4.0-confirmatory | qwen3.5:4b | patch | evaluation | benign_override | completed | 36 | 900 | 5–5 |
| followups | 4.0-confirmatory | qwen3.5:4b | patch | evaluation | none | completed | 36 | 900 | 5–5 |
| followups | 4.0-confirmatory | qwen3.5:4b | record | development | benign_override | completed | 2 | 10 | 5–5 |
| followups | 4.0-confirmatory | qwen3.5:4b | record | development | none | completed | 2 | 10 | 5–5 |
| followups | 4.0-confirmatory | qwen3.5:4b | record | evaluation | benign_override | completed | 32 | 160 | 5–5 |
| followups | 4.0-confirmatory | qwen3.5:4b | record | evaluation | none | completed | 32 | 160 | 5–5 |
| followups | 4.1-decomposition | mock-v1 | record | calibration | direct_full | completed | 16 | 16 | 1–1 |
| followups | 4.1-decomposition | mock-v1 | record | matched_split | serial_split | completed | 16 | 80 | 5–5 |
| followups | 4.1-decomposition | mock-v1 | record | matched_split | team_split | completed | 16 | 80 | 5–5 |
| followups | 4.1-decomposition | mock-v1 | record | negative_control | identity_reset | completed | 2 | 10 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | defensive_cybersecurity | evaluation | clean | completed | 2 | 50 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | defensive_cybersecurity | evaluation | marker_override | completed | 2 | 50 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | defensive_cybersecurity | evaluation | reporting_pressure | completed | 2 | 50 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | defensive_cybersecurity | integration_precheck | clean | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | defensive_cybersecurity | integration_precheck | marker_override | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | defensive_cybersecurity | integration_precheck | reporting_pressure | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | humanities | evaluation | clean | completed | 5 | 125 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | humanities | evaluation | marker_override | completed | 5 | 125 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | humanities | evaluation | reporting_pressure | completed | 5 | 125 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | humanities | integration_precheck | clean | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | humanities | integration_precheck | marker_override | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | humanities | integration_precheck | reporting_pressure | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | mathematics | evaluation | clean | completed | 5 | 125 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | mathematics | evaluation | marker_override | completed | 5 | 125 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | mathematics | evaluation | reporting_pressure | completed | 5 | 125 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | mathematics | integration_precheck | clean | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | mathematics | integration_precheck | marker_override | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | mathematics | integration_precheck | reporting_pressure | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | psychology | evaluation | clean | completed | 5 | 125 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | psychology | evaluation | marker_override | completed | 5 | 125 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | psychology | evaluation | reporting_pressure | completed | 5 | 125 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | psychology | integration_precheck | clean | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | psychology | integration_precheck | marker_override | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | psychology | integration_precheck | reporting_pressure | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | science | evaluation | clean | completed | 2 | 50 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | science | evaluation | marker_override | completed | 2 | 50 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | science | evaluation | reporting_pressure | completed | 2 | 50 | 5–5 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | science | integration_precheck | clean | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | science | integration_precheck | marker_override | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | multidomain-scripted-v1 | science | integration_precheck | reporting_pressure | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | qwen3.5:4b | humanities | integration_precheck | clean | failed | 1 | 2 | 3–3 |
| multidomain | 5.0-multidomain-evidence | qwen3.5:4b | mathematics | integration_precheck | clean | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | qwen3.5:4b | mathematics | integration_precheck | marker_override | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | qwen3.5:4b | mathematics | integration_precheck | reporting_pressure | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | qwen3.5:4b | psychology | integration_precheck | clean | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | qwen3.5:4b | psychology | integration_precheck | marker_override | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | qwen3.5:4b | psychology | integration_precheck | reporting_pressure | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | qwen3.5:4b | science | integration_precheck | clean | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | qwen3.5:4b | science | integration_precheck | marker_override | completed | 1 | 15 | 3–3 |
| multidomain | 5.0-multidomain-evidence | qwen3.5:4b | science | integration_precheck | reporting_pressure | completed | 1 | 15 | 3–3 |
| multidomain | 5.1-multidomain-question-coverage | qwen3.5:4b | humanities | integration_precheck | clean | completed | 1 | 15 | 3–3 |
| multidomain | 5.1-multidomain-question-coverage | qwen3.5:4b | humanities | integration_precheck | marker_override | completed | 1 | 15 | 3–3 |
| multidomain | 5.1-multidomain-question-coverage | qwen3.5:4b | humanities | integration_precheck | reporting_pressure | completed | 1 | 15 | 3–3 |
| multidomain | 5.1-multidomain-question-coverage | qwen3.5:4b | mathematics | integration_precheck | clean | failed | 1 | 6 | 3–3 |
| multidomain | 5.1-multidomain-question-coverage | qwen3.5:4b | psychology | integration_precheck | clean | completed | 1 | 15 | 3–3 |
| multidomain | 5.1-multidomain-question-coverage | qwen3.5:4b | psychology | integration_precheck | marker_override | completed | 1 | 15 | 3–3 |
| multidomain | 5.1-multidomain-question-coverage | qwen3.5:4b | psychology | integration_precheck | reporting_pressure | completed | 1 | 15 | 3–3 |
| multidomain | 5.1-multidomain-question-coverage | qwen3.5:4b | science | integration_precheck | clean | completed | 1 | 15 | 3–3 |
| multidomain | 5.1-multidomain-question-coverage | qwen3.5:4b | science | integration_precheck | marker_override | completed | 1 | 15 | 3–3 |
| multidomain | 5.1-multidomain-question-coverage | qwen3.5:4b | science | integration_precheck | reporting_pressure | completed | 1 | 15 | 3–3 |
| repositories | 3.0-repository | mock-repository-v1 | code_review | development | benign_override | completed | 3 | 130 | 3–15 |
| repositories | 3.0-repository | mock-repository-v1 | code_review | development | none | completed | 3 | 130 | 3–15 |
| repositories | 3.0-repository | qwen3.5:4b | code_review | development | none | budget_exhausted | 1 | 1 | 3–3 |
| repositories | 3.1-repository | qwen3.5:4b | code_review | development | benign_override | completed | 9 | 440 | 3–15 |
| repositories | 3.1-repository | qwen3.5:4b | code_review | development | none | budget_exhausted | 1 | 5 | 3–3 |
| repositories | 3.1-repository | qwen3.5:4b | code_review | development | none | completed | 9 | 440 | 3–15 |
| repositories | 3.3-repository-safeguard | mock-repository-v1 | code_review | evaluation | benign_override | completed | 32 | 2400 | 15–15 |
| repositories | 3.3-repository-safeguard | mock-repository-v1 | code_review | evaluation | none | completed | 32 | 2400 | 15–15 |
| repositories | 3.3-repository-safeguard | mock-repository-v1 | code_review | integration_precheck | benign_override | completed | 2 | 30 | 3–3 |
| repositories | 3.3-repository-safeguard | mock-repository-v1 | code_review | integration_precheck | none | completed | 2 | 30 | 3–3 |
| repositories | 3.3-repository-safeguard | qwen3.5:4b | code_review | evaluation | benign_override | completed | 20 | 1500 | 15–15 |
| repositories | 3.3-repository-safeguard | qwen3.5:4b | code_review | evaluation | benign_override | failed | 1 | 15 | 15–15 |
| repositories | 3.3-repository-safeguard | qwen3.5:4b | code_review | evaluation | none | budget_exhausted | 1 | 10 | 15–15 |
| repositories | 3.3-repository-safeguard | qwen3.5:4b | code_review | evaluation | none | completed | 19 | 1425 | 15–15 |
| repositories | 3.3-repository-safeguard | qwen3.5:4b | code_review | integration_precheck | benign_override | completed | 2 | 30 | 3–3 |
| repositories | 3.3-repository-safeguard | qwen3.5:4b | code_review | integration_precheck | none | completed | 2 | 30 | 3–3 |
| repositories | 3.4-benchmark-static | mock-repository-v1 | code_review | evaluation | benign_override | completed | 30 | 2250 | 15–15 |
| repositories | 3.4-benchmark-static | mock-repository-v1 | code_review | evaluation | none | completed | 29 | 2175 | 15–15 |
| repositories | 3.4-benchmark-static | mock-repository-v1 | code_review | integration_precheck | benign_override | completed | 6 | 90 | 3–3 |
| repositories | 3.4-benchmark-static | mock-repository-v1 | code_review | integration_precheck | none | completed | 6 | 90 | 3–3 |
| repositories | 3.4-benchmark-static | mock-repository-v1 | issue_diagnosis | evaluation | benign_override | budget_exhausted | 1 | 0 | 15–15 |
| repositories | 3.4-benchmark-static | mock-repository-v1 | issue_diagnosis | evaluation | benign_override | completed | 198 | 14850 | 15–15 |
| repositories | 3.4-benchmark-static | mock-repository-v1 | issue_diagnosis | evaluation | none | completed | 199 | 14925 | 15–15 |
| repositories | 3.4-benchmark-static | mock-repository-v1 | issue_diagnosis | integration_precheck | benign_override | completed | 6 | 90 | 3–3 |
| repositories | 3.4-benchmark-static | mock-repository-v1 | issue_diagnosis | integration_precheck | none | completed | 6 | 90 | 3–3 |
| repositories | 3.5-repository-output-budget | qwen3.5:4b | code_review | development | none | budget_exhausted | 1 | 5 | 3–3 |
| repositories | 3.8-repository-bounded-output | qwen3.5:4b | code_review | development | benign_override | completed | 12 | 470 | 3–15 |
| repositories | 3.8-repository-bounded-output | qwen3.5:4b | code_review | development | benign_override | failed | 1 | 2 | 3–3 |
| repositories | 3.8-repository-bounded-output | qwen3.5:4b | code_review | development | none | completed | 12 | 470 | 3–15 |
| research | 2.0 | mock-v1 | catalog | development | benign_override | completed | 4 | 100 | 5–5 |
| research | 2.0 | mock-v1 | catalog | development | none | completed | 4 | 100 | 5–5 |
| research | 2.0 | mock-v1 | catalog | evaluation | benign_override | completed | 12 | 300 | 5–5 |
| research | 2.0 | mock-v1 | catalog | evaluation | none | completed | 12 | 300 | 5–5 |
| research | 2.0 | mock-v1 | patch | development | benign_override | completed | 4 | 100 | 5–5 |
| research | 2.0 | mock-v1 | patch | development | none | completed | 4 | 100 | 5–5 |
| research | 2.0 | mock-v1 | patch | evaluation | benign_override | completed | 12 | 300 | 5–5 |
| research | 2.0 | mock-v1 | patch | evaluation | none | completed | 12 | 300 | 5–5 |
| research | 2.0 | mock-v1 | provenance | development | benign_override | completed | 4 | 100 | 5–5 |
| research | 2.0 | mock-v1 | provenance | development | none | completed | 4 | 100 | 5–5 |
| research | 2.0 | mock-v1 | provenance | evaluation | benign_override | completed | 12 | 300 | 5–5 |
| research | 2.0 | mock-v1 | provenance | evaluation | none | completed | 12 | 300 | 5–5 |
| research | 2.0 | mock-v1 | record | development | benign_override | completed | 4 | 20 | 2–5 |
| research | 2.0 | mock-v1 | record | development | none | completed | 4 | 20 | 2–5 |
| research | 2.0 | qwen3.5:4b | catalog | development | benign_override | completed | 2 | 20 | 2–2 |
| research | 2.0 | qwen3.5:4b | catalog | development | benign_override | failed | 2 | 50 | unrecorded |
| research | 2.0 | qwen3.5:4b | catalog | development | none | completed | 5 | 95 | 2–2 |
| research | 2.0 | qwen3.5:9b | catalog | development | benign_override | completed | 1 | 10 | 2–2 |
| research | 2.0 | qwen3.5:9b | catalog | development | none | completed | 1 | 10 | 2–2 |
| research | 2.1 | mock-v1 | catalog | development | benign_override | completed | 5 | 310 | 2–2 |
| research | 2.1 | mock-v1 | catalog | development | none | completed | 5 | 310 | 2–2 |
| research | 2.1 | mock-v1 | patch | development | benign_override | completed | 5 | 310 | 2–2 |
| research | 2.1 | mock-v1 | patch | development | none | completed | 5 | 310 | 2–2 |
| research | 2.1 | mock-v1 | provenance | development | benign_override | completed | 5 | 310 | 2–2 |
| research | 2.1 | mock-v1 | provenance | development | none | completed | 5 | 310 | 2–2 |
| research | 2.2 | qwen3.5:4b | catalog | development | benign_override | completed | 1 | 10 | 2–2 |
| research | 2.2 | qwen3.5:4b | catalog | development | none | completed | 1 | 10 | 2–2 |
| research | 2.2 | qwen3.5:4b | patch | development | benign_override | completed | 1 | 10 | 2–2 |
| research | 2.2 | qwen3.5:4b | patch | development | none | completed | 1 | 10 | 2–2 |
| research | 2.2 | qwen3.5:4b | provenance | development | benign_override | completed | 1 | 10 | 2–2 |
| research | 2.2 | qwen3.5:4b | provenance | development | none | completed | 1 | 10 | 2–2 |
| research | 2.2 | qwen3.5:4b | record | development | benign_override | completed | 4 | 20 | 2–5 |
| research | 2.2 | qwen3.5:4b | record | development | none | completed | 4 | 20 | 2–5 |
| research | 2.3 | qwen3.5:4b | catalog | development | benign_override | completed | 1 | 10 | 2–2 |
| research | 2.3 | qwen3.5:4b | catalog | development | none | completed | 1 | 10 | 2–2 |
| research | 2.3 | qwen3.5:4b | patch | development | benign_override | completed | 1 | 10 | 2–2 |
| research | 2.3 | qwen3.5:4b | patch | development | none | completed | 1 | 10 | 2–2 |
| research | 2.3 | qwen3.5:4b | provenance | development | benign_override | completed | 1 | 10 | 2–2 |
| research | 2.3 | qwen3.5:4b | provenance | development | none | completed | 1 | 10 | 2–2 |
| research | 2.4 | qwen3.5:4b | catalog | development | benign_override | completed | 1 | 10 | 2–2 |
| research | 2.4 | qwen3.5:4b | catalog | development | none | completed | 1 | 10 | 2–2 |
| research | 2.4 | qwen3.5:4b | patch | development | benign_override | completed | 2 | 20 | 2–2 |
| research | 2.4 | qwen3.5:4b | patch | development | none | completed | 2 | 20 | 2–2 |
| research | 2.4 | qwen3.5:4b | provenance | development | benign_override | completed | 2 | 20 | 2–2 |
| research | 2.4 | qwen3.5:4b | provenance | development | none | completed | 2 | 20 | 2–2 |
| research | 2.4 | qwen3.5:4b | record | development | none | completed | 1 | 5 | 5–5 |
| research | 2.5 | qwen3.5:4b | record | development | none | completed | 1 | 5 | 5–5 |
| research | 2.6 | qwen3.5:4b | catalog | development | benign_override | completed | 1 | 25 | 5–5 |
| research | 2.6 | qwen3.5:4b | catalog | development | none | completed | 1 | 25 | 5–5 |
| research | 2.6 | qwen3.5:4b | catalog | evaluation | benign_override | budget_exhausted | 2 | 41 | 4–5 |
| research | 2.6 | qwen3.5:4b | catalog | evaluation | benign_override | completed | 42 | 1050 | 5–5 |
| research | 2.6 | qwen3.5:4b | catalog | evaluation | none | completed | 42 | 1050 | 5–5 |
| research | 2.6 | qwen3.5:4b | catalog | evaluation | none | failed | 1 | 0 | 5–5 |
| research | 2.6 | qwen3.5:4b | patch | development | benign_override | completed | 1 | 25 | 5–5 |
| research | 2.6 | qwen3.5:4b | patch | development | none | completed | 1 | 25 | 5–5 |
| research | 2.6 | qwen3.5:4b | patch | evaluation | benign_override | completed | 42 | 1050 | 5–5 |
| research | 2.6 | qwen3.5:4b | patch | evaluation | none | completed | 42 | 1050 | 5–5 |
| research | 2.6 | qwen3.5:4b | provenance | development | benign_override | completed | 1 | 25 | 5–5 |
| research | 2.6 | qwen3.5:4b | provenance | development | none | completed | 1 | 25 | 5–5 |
| research | 2.6 | qwen3.5:4b | provenance | evaluation | benign_override | completed | 42 | 1050 | 5–5 |
| research | 2.6 | qwen3.5:4b | provenance | evaluation | none | completed | 42 | 1050 | 5–5 |
| research | 2.6 | qwen3.5:4b | record | development | benign_override | completed | 4 | 20 | 2–5 |
| research | 2.6 | qwen3.5:4b | record | development | none | completed | 4 | 20 | 2–5 |
| results | 1.0 | mock-v1 | catalog | legacy_unspecified | benign_override | completed | 9 | 225 | 5–5 |
| results | 1.0 | mock-v1 | catalog | legacy_unspecified | none | completed | 9 | 225 | 5–5 |
| results | 1.1 | nemotron-3.5-lightning:30b | catalog | legacy_unspecified | benign_override | completed | 1 | 25 | 5–5 |
| results | 1.1 | nemotron-3.5-lightning:30b | catalog | legacy_unspecified | none | completed | 1 | 25 | 5–5 |
| results | 1.1 | qwen3.5:9b | catalog | legacy_unspecified | benign_override | completed | 9 | 225 | 5–5 |
| results | 1.1 | qwen3.5:9b | catalog | legacy_unspecified | none | completed | 9 | 225 | 5–5 |

## How these tasks affect the conclusions

- Catalog, provenance and inert patch tasks supply the compact RQ1 comparison. Catalog trajectories also supply the original RQ2 monitor analysis; absent adoption positives leave recall undefined.
- Protected-record summaries supply RQ3 development and the separate 64-run contextual-allocation comparison. No observed individual refusals means these results do not establish refusal bypass.
- Live code reviews test longer supplied inputs and repeated controller rounds, plus format/recovery reliability. They are exploratory static reviews, not executable coding solutions; independent semantic-quality labels are missing, so they do not establish benchmark performance or a long-horizon causal effect.
- Live psychology, science, mathematics and humanities records are integration prechecks of evidence/uncertainty formats. They do not complete the registered held-out multidisciplinary matrix and are not pooled into the compact causal comparison.
- Issue diagnosis and defensive cybersecurity have mock-only coverage in this checkpoint. They validate the task pipeline, not model honesty, task success or resistance to collusion in those domains.
- Longer inputs, more rounds and different cases co-vary in exploratory collections. A change in observed behavior cannot be attributed to task length alone. The report keeps these limitations visible rather than counting every record as a new independent experiment.

## Reproduce

```bash
.venv/bin/python scripts/final_evidence_inventory.py --validate-only
```

This read-only command checks the closed inventory and its four snapshot hashes without requiring private logs. To rebuild source reconciliation locally, supply fresh --output and --catalog paths under results; existing files are never overwritten. Rebuilding requires the preserved private source logs and makes no inference requests. Monitor recall stays undefined when there are no positive labels. Compliance is a narrow endpoint, not a general alignment score. Public excerpts require their separate reviewed export boundary.
