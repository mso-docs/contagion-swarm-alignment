# Long static benchmark materials

The new material catalog contains **51 long cases**, spanning **14 canonical project groups** and two public benchmark sources. Forty-two cases belong to the project-disjoint held-out split across11project groups, seven to development and two to training. The held-out inventory includes39 SWE-bench adaptations and three fresh Martian cases. These are static Contagion adaptations, not official benchmark runs or leaderboard scores.

The tracked [source descriptor](../configs/long_benchmark_sources.json) contains revisions, license/artifact hashes, public source attribution and closed task metadata. Literal inputs, hidden references, source licenses and downloaded dataset artifacts stay under ignored `results/benchmarks/`. No upstream program, test, repository checkout or shell command is executed by agents or this importer.

| Source | Pinned artifact | Input to agents | Hidden reference and limits |
|---|---|---|---|
| [Martian Code Review Benchmark](https://github.com/withmartian/code-review-benchmark) | Dataset revision `e616e849755441da38f18bf3adba2c9583b03803`; full PR diffs pinned by base/head/diff hashes | Complete bounded PR diff, canonical project identity | Curated golden review comments. Source/project licensing is retained privately; code redistribution remains withheld. Golden quality still needs independent semantic adjudication |
| [SWE-bench Verified](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified) | Dataset revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`; Parquet SHA and base commits pinned | Original issue statement plus bounded base-source windows | Reference patch, test patch, test IDs and upstream difficulty label remain hidden. File and line windows are selected using reference-patch locations: this supplies localization hints and changes task difficulty |

The official [SWE-bench repository](https://github.com/SWE-bench/SWE-bench) describes generating patches and checking them with execution-based evaluation. This project does neither for these adaptations: agents diagnose static evidence and return bounded findings/test plans in the simulated controller. No resolved-issue rate, test pass rate or official SWE-bench score is inferred. MIT source license documents are retained with hashes; underlying repository code keeps its own licensing and is not automatically published.

## Scope and selection

Each selected input contains16,001–52,000 serialized characters and at most70,000 UTF-8 bytes. Character length, source-file count and15/30-round horizons are operational workload measures, not verified reasoning difficulty or equivalent task information. Domain metadata covers web frameworks, scientific computing, symbolic math, machine learning, documentation, static analysis, visualization, HTTP clients, observability and community software.

Selection is deterministic before inference. SWE-bench reserves one project group for training and another for development; its remaining eligible projects form the held-out split. The fresh Martian pool has only two canonical groups, so it reserves one for development and the other for held-out evaluation, with no invented training group. All seven physical Martian source repositories were audited against their five upstream benchmark project families, including Sentry and Keycloak evaluation-fork aliases. Unknown evaluation forks fail closed. The fixed seed is20261108. Project grouping uses canonical upstream identity: the Discourse evaluation fork is grouped as `discourse/discourse`, while its physical source repository remains recorded. Different tasks/seeds from one project are dependent, and the same source project must not be counted as several independent projects through fork names.

Eight Martian source cases already used by live studies or allocated to the existing long-task queue are excluded from the new catalog. Historical project exposure is still recorded: a newly split held-out project is not necessarily a never-before-studied project, and public benchmark tasks may already occur in model training data. No test outcome influenced source selection.

Privacy failures quarantine the whole candidate rather than silently rewriting code. Context-budget failures are excluded rather than padded, truncated into an apparently complete diff, or relabeled as equivalent tasks. SWE excerpts are explicitly bounded windows, not complete repository context. Positive source references and dataset licenses do not validate model semantic quality or prove that every adapted case is solvable from its displayed excerpt.

## Reproduce or validate

The Parquet reader is optional and used only during import:

```bash
.venv/bin/python -m pip install -e '.[benchmarks]'
.venv/bin/python scripts/long_benchmark_materials.py validate \
  --catalog results/benchmarks/long-static-v5/catalog.json
```

`validate_catalog(path)` verifies the immutable catalog hash, source revisions/licenses, deterministic project splits and private input/reference hashes. `load_task(path, row)` returns only the closed agent-input schema and never loads hidden-reference content into that payload. Queue runners need no PyArrow dependency after import.

For a new import, use fresh output paths and preserve all previous artifacts:

```bash
.venv/bin/python scripts/repository_benchmark.py import \
  --out results/benchmarks/martian-FRESH --limit 30 \
  --previous results/benchmarks/martian-pinned-v2/catalog.json
.venv/bin/python scripts/long_benchmark_materials.py import \
  --out results/benchmarks/static-import-FRESH \
  --martian results/benchmarks/martian-FRESH/catalog.json --swe-limit 96
.venv/bin/python scripts/long_benchmark_materials.py assemble \
  --out results/benchmarks/static-materials-FRESH \
  --base results/benchmarks/static-import-FRESH/catalog.json \
  --martian results/benchmarks/martian-FRESH/catalog.json
```

The last stage excludes current historical/live allocations and records an exposure-index hash. Its resulting catalog depends on the available local history; preserve the actual frozen catalog for exact selection reproduction. Data import uses bounded public HTTPS requests and follows only allowlisted HTTPS source redirects. It makes no model calls, changes no server settings and never retries uncertain model inference.
