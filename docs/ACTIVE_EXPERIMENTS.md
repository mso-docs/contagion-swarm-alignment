# Experiment status and public checkpoint

[Documentation home](README.md) · [Developer guide](DEVELOPMENT.md)

**Historical operations reference.** Collection is closed. Commands and status
notes below describe their recorded checkpoint; use the [final catalog](EXPERIMENT_CATALOG.md)
for completed evidence. Do not resume allocations from this page.


**Collection closed for final review.** All 30 registered local allocations have
STOP markers; both controller leases were idle at closure. The final static
[snapshot](FINAL_DASHBOARD_SNAPSHOT.md) replaces live dashboards. The recovery
history below explains the preserved results; it is not a new collection queue.

**Primary collection is stopped and reserved for another operator. Do not restart
it or query/load models there.** All primary successors and the planned diversity
interlude are stopped or unstarted. Secondary collection finished its registered
recovery allocation; no replacement experiment has been started. Paper preparation
and public-data review take priority over new collection.

| Allocation | Latest recorded progress | Interpretation |
|---|---:|---|
| Primary5.0 multidisciplinary study |9/72 completed; one failed attempt,137physical requests |Incomplete older output-format cohort; original evidence preserved |
| Primary5.1 question-coverage study |9/72 completed; one interrupted attempt,141physical requests |Stopped; no claim that the development matrix or held-out study completed |
| Primary3.6 continuation |Zero new calls in the current successor chain |Stopped/deferred; earlier source attempts retain their own results and budgets |
| Fresh RQ3 decomposition |Zero live calls in the current successor chain |Deferred; earlier RQ3 results remain separate |
| Primary3.7 long benchmark |0/264 runs |Unstarted/deferred; not evidence of benchmark performance |
| Diversity/role/topology calibration |Prepared; no live observations |No mixed-family or specialized-role finding to report |
| Secondary isolated3.8 recovery |**21/21 completed;895physical requests; zero failed runs** |Complete operational recovery allocation; inherited attempts remain separate |
| Neural reference inventory |**72 trained checkpoint captures plus two random-weight checks** |Reference measurements, not activations from the Ollama swarm runs |

The secondary21 runs follow15 completed assignments across older ancestors. The
36 assignment locations are covered across changed protocols, not one unchanged
balanced experiment. Earlier3.1/3.5 failures,3.8 recovery receipts and all raw bytes
remain preserved. Likewise, a new output-format protocol does not relabel an old
partial primary study complete. There are no hidden retries or deleted budgets.

## Public and private views
<details>
<summary><strong>Expand reference and commands</strong></summary>

The reviewed public checkpoint was copied from the validated local cache on
**November9,2026 at00:14UTC**. It contains38 legacy records,446 study records,646 repository records,
190 confirmatory/decomposition records,92 multidisciplinary records and74 neural
captures. These totals include explicitly labeled mocks and dependent attempts;
they are not independent empirical sample sizes. Per-index generation timestamps
remain visible. Current paper evidence cutoffs do not change automatically.

Seven newly reviewed public trace samples expose49 bounded artifact/message
excerpts from actual completed inference runs: original fictional science cases,
fictional patch cases and two static repository reviews. Exact source-seal and
sanitized-content hashes bind the implementation-agent review. The sixteen human
behavior labels do not certify privacy of these traces. Requests, oracle labels,
source packets, private thinking and operator telemetry are excluded. Other runs
retain numeric summaries and existing approved trace views; full raw logs remain
private. Heuristic redaction does not guarantee anonymity.

The public judge preview serves the **exact Pages artifact**, with the same data,
charts and selected trace index and no private APIs:

```bash
.venv/bin/python scripts/serve_public_preview.py \
  --artifact results/public-preview/review-FRESH
```

Open <http://127.0.0.1:8766/>. The operational localhost dashboard on8765 has a
separate private progress surface; it is not the artifact sent to a judge. The
static preview cannot contact either inference server or restart an experiment.
GitHub publication still requires the reviewed branch merge/Pages configuration;
this local checkpoint performs no deployment or hackathon submission.

To refresh the reviewed numeric checkpoint without model calls:

```bash
.venv/bin/python scripts/export_live_dashboard.py
```

That command validates the local cache and copies only closed approved indexes
and referenced detail files. New public text needs an explicit concrete review
manifest through `public_trace_samples.py`; refreshing counts never publishes raw
logs or arbitrary new text. Build into a fresh preview directory after a checkpoint
change so the judge preview and published files remain byte-for-byte comparable.

</details>
