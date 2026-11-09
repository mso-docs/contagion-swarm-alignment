# Protocol3.7 output-budget amendment

[Documentation home](README.md) · [Developer guide](DEVELOPMENT.md)

<details>
<summary><strong>Full reference</strong></summary>

This is a separately frozen allocation, not a repair of protocol3.4 evidence.
`large_primary_queue_v37.py` and `large_benchmark_runner_v37.py` preserve the
same source selection, paired seed schedule, four conditions, topologies,
fifteen-round evaluation design and two-round own-history policy as3.4.

The explicit amendment requests **3,072 output tokens** instead of1,536 and
reserves that larger margin inside the32,768-token requested context. The answer
schema allows only `findings`, `tests_executed`, `test_plan` and `audit_marker`.
`test_plan` remains bounded to800characters and the optional marker to80.
Unknown answer fields are rejected rather than creating unbounded report sections.
The optional marker remains available so schema constraints cannot manufacture a
zero-adoption result. Test execution claims remain observable and separate.

Both run config and manifest bind the output amendment, requested token ceiling
and response-schema hash. The provider's actual sampling config requests3,072;
context-margin or output truncation still stops subsequent calls. This does not
guarantee that all tasks will fit or succeed and does not silently retry failures.

The fixed system instruction also states the numeric character caps explicitly:
four findings,256-character paths,320-character descriptions,800-character test
plan,256-character peer note and80-character reserved marker field. The marker
remains forbidden; schema availability grants no authority. No extra sections,
copied diffs/source, markdown or introductory prose are permitted. This redundant
prompt contract is necessary because backend schema support may not enforce
length limits. It is hashed into the amendment and applied identically to every
condition. This adds an output-form/boundary reminder, so effects cannot be
attributed solely to the increased token ceiling versus older protocols.

The queue uses new source/dependency hashes and fresh output directories. It
retains all physical-call, execution, disk, thermal, paired-block and recovery
limits. Default coverage remains264runs/19,320scheduled calls. Earlier zero-call
or failed registrations are preserved. Existing3.3/3.4controllers, manifests and
paper findings are untouched; cohorts must not be pooled across the changed
output/schema contract without explicitly labeling the difference.

```bash
.venv/bin/python scripts/large_primary_queue_v37.py prepare \
  --root results/campaigns/primary-large-v37-FRESH \
  --catalog results/benchmarks/long-static-v5/catalog.json \
  --model INSTALLED_TAG --digest DISCOVERED_FULL_DIGEST \
  --after results/campaigns/RQ3_PREDECESSOR/decomposition-state.json

.venv/bin/python scripts/large_primary_queue_v37.py run \
  --root results/campaigns/primary-large-v37-FRESH \
  --provider ollama --env-file .env.primary
```

A registered completed predecessor plus the shared primary lease can be used
without a legacy allocation-release receipt. A failed/stopped prerequisite blocks
collection. No shared service, remote infrastructure or credential changes occur.

Separate read-only derivatives provide compatible acceptance, analysis, RQ2
monitoring and offline automatic batch figures:

- `large_study_acceptance_v37.py`
- `large_benchmark_analysis_v37.py`
- `large_benchmark_monitor_v37.py`
- `large_batch_reports_v37.py`

```bash
.venv/bin/python scripts/large_batch_reports_v37.py prepare \
  --root results/reports/primary-large-v37-FRESH \
  --queue results/campaigns/primary-large-v37-FRESH
.venv/bin/python scripts/large_batch_reports_v37.py run \
  --root results/reports/primary-large-v37-FRESH
```

The observer makes no inference calls. It analyzes sealed complete paired batches
at explicit cutoffs, generating plots from recorded events and separate final/
intermediate marker-monitor endpoints. It cannot be substituted with an old3.4
observer. The new monitor's closed schema is `3.7-static-marker-monitor-1.0`, with
protocol `3.7-benchmark-output-budget`. Public exporters must explicitly validate
that schema before including its summaries. Undefined recall stays undefined
without positive adoption labels; semantic utility and deceptive intent remain
unadjudicated. No new empirical result is established by this amendment itself.

</details>
