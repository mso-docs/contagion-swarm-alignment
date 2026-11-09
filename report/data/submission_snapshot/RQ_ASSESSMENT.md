# Frozen research-question assessment

Cutoff: `2026-11-08T06:57:00+00:00`. Snapshot hash: `b5574d230b9508e7f852eba260c3d6fd83097e06570de1461a905f6c6874171e`. Only verified sealed completed runs ending by this cutoff contribute outcomes. Live work can continue separately.

| Question | Evidence in this snapshot | Supported interpretation | Remaining gate |
|---|---|---|---|
| RQ1 topology propagation | 72 protocol4 patch runs; 0/72 runs with positive final downstream rate; 6 with any-round violation | Any-round and final endpoints are separate; this does not by itself establish topology causality or intent | Human artifact validation; paired exposure/source analysis; few independent cases |
| RQ2 partial visibility | Original catalog monitor and separate protocol4 patch monitor use dependent projections, not new runs | Recall is undefined wherever the adopted-behavior truth denominator is zero; intermediate-patch detection is a different endpoint | Keep monitor masks/endpoint cohorts separate and report positive denominators |
| RQ3 distributed responsibility | 64 completed protocol4 record runs; 0 attempted updates; 0 state violations | Context allocation is tested; no refusal bypass established | Protocol4.1 decomposition and verified individual-refusal prerequisite; human review |
| Safeguard and utility | See safeguard.json; only completed sealed evaluation cells shown | Boundary compliance is separate from legitimate review quality; missing quality stays null | Complete registered matrix, semantic review and human adjudication |

## Included live cohorts

| Protocol | Task | Phase | Completed runs |
|---|---|---|---|
| 2.6 | catalog | development | 2 |
| 2.6 | catalog | evaluation | 84 |
| 2.6 | patch | development | 2 |
| 2.6 | patch | evaluation | 12 |
| 2.6 | provenance | development | 2 |
| 2.6 | provenance | evaluation | 68 |
| 2.6 | record | development | 8 |
| 3.1-repository | code_review | development | 6 |
| 3.3-repository-safeguard | code_review | evaluation | 1 |
| 3.3-repository-safeguard | code_review | integration_precheck | 4 |
| 4.0-confirmatory | patch | evaluation | 72 |
| 4.0-confirmatory | record | evaluation | 64 |
| 4.0-confirmatory | record | integration_precheck | 4 |

## Pending allocations at freeze

| Allocation | Observed status | Completed / planned |
|---|---|---|
| primary_long | running | 5 / 68 |
| secondary | cooling | 130 / unknown |
| secondary_long | waiting | unknown / 36 |
| decomposition | waiting | 0 / 50 |

Human validation remains pending. Reference GPT-2 neural measurements are not recordings of swarm-model internals. No general alignment rating or collusion conclusion is inferred.
