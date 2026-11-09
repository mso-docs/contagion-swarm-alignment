# Large-study acceptance and claim limits

[Documentation home](README.md) · [Developer guide](DEVELOPMENT.md)


Protocol 3.4 adds controller-mediated static review and issue diagnosis from pinned benchmark
materials. It is an adaptation of task inputs, not an execution of an official agentic
benchmark. Models receive no shell, browser, filesystem or real testing tools. A verification
plan is a proposal; a claim that tests ran is not evidence of execution.

## Operational acceptance
<details>
<summary><strong>Expand reference and commands</strong></summary>

```bash
.venv/bin/python scripts/large_study_acceptance.py \
  --queue results/campaigns/PRIMARY_LARGE_ALLOCATION \
  --out results/large-acceptance-FRESH.json
```

The read-only checker validates the registered plan and source catalog through the queue
validator, then checks:

- Exact held-out/development separation and complete control/injection × plain/attributed blocks.
- Task, seed, graph, safeguard, phase and batch assignment against immutable manifests.
- All retained attempts, checksums, real-call accounting and Cartesian agent/round artifacts.
  Incomplete attempts reserve the whole admitted job when actual calls are uncertain; recorded
  HTTP attempts are reported separately.
- Every scheduled graph delivery exactly once, strictly from the prior round, and the current
  inbox exactly as recorded in the actual request.
- The immutable initial task plus only the last two own request/response rounds.
  Retained/omitted-round disclosures must match; oracle/reference fields may not appear in model
  inputs.
- Completion of every task-kind precheck before the full coverage gate, and completion of the
  registered matrix before whole-study boundary analysis.

A model's boundary flags or poor findings do **not** make a harness test fail. Operational
failures, invalid seals, leaked evaluator context, missing artifacts and ambiguous request
history do. Failed attempts remain in counts and require review; a retry cannot erase them. The
report is a closed numeric schema with source-plan/catalog/seal/code hashes and a validation
helper, `validate_report(path)`.

An append-only explicit-retry receipt can resolve a retained attempt only when its exact
evidence/reservations still validate and a later successful attempt completes the same
registered job. The report then says `operational_checks_passed_with_reviewed_retries` and
retains original failure counts, calls and exclusions. Without this approval, full-matrix
acceptance stays blocked. An explicitly requested completed-batch descriptive analysis may still
use otherwise valid whole batches when only retained-attempt/matrix gates fail; assignment,
request/routing, intervention or checksum failures cannot be bypassed.

Before held-out calls, each task kind needs at least one finding anchored to a visible source
path and original line across its two clean development runs/ten final agents. The checker
recomputes the receipt from actual final artifacts and pinned visible inputs. This weak
feasibility check does not establish that a finding is useful or correct, and requires no
positive boundary outcome. An indeterminate development result is reported as such and blocks
held-out progression.

The full-coverage design guards require 32 independent cases across at least 8 upstream project
groups and 2 source families. These are practical coverage targets, not a power calculation or
proof that projects are exchangeable. Small pilot allocations can pass operational checks while
correctly showing limited diversity and a closed full-coverage gate.

</details>

## Scientific acceptance
<details>
<summary><strong>Expand reference and commands</strong></summary>

Keep four measurements separate: valid output format, task/reference quality, scored boundary
behavior and actual simulated state changes. Unknown semantic precision/recall stay null. The
previous 16-label compliant artifact audit does not calibrate new repository/issue-quality
judgments. A different-family or frontier judge remains advisory without a matching held-out
human reference. Do not rank judges using different covered subsets.

Use case/seed/topology blocks for paired comparisons, with agents and rounds nested. Cluster
across upstream projects where supported; a count threshold alone does not establish valid
population intervals. The attribution treatment bundles provenance, format and a reminder, so it
does not isolate one mechanism. Ring-only allocations cannot identify topology effects. Longer
text, more rounds and a two-round working-memory window are different experimental properties;
none alone demonstrates harder reasoning or unrestricted long-horizon agency.

Every figure must name its endpoint, denominator, backend, protocol and cohort. Plot source/task
coverage and observed attempt/call counts while collecting; keep incomplete outcomes
indeterminate. Full-matrix effect/utility figures need their respective completed paired data
and validated quality references. No generic alignment score, intentional-cheating label,
collusion conclusion or swarm neural-mechanism claim follows from this static track. Six GPT-2
reference captures remain separate measurements.

`large_benchmark_analysis.py` supplies source/task-kind/model/controller-separated paired
boundary contrasts, per-round artifact/delivery counts and source seals. Full mode requires the
registered matrix. An explicit alternative selects only whole registered completed batches at a
declared cutoff and suppresses population intervals:

```bash
.venv/bin/python scripts/large_benchmark_analysis.py \
  --queue results/campaigns/PRIMARY_LARGE_ALLOCATION \
  --completed-batches --cutoff 2026-11-08T23:00:00Z \
  --out results/large-analysis-CUTOFF.private.json
```

Use an actual past/current cutoff and a fresh path. Remove the batch flag for the completed full
matrix; mock analysis additionally requires `--allow-mock`. Completed-batch subsets are
timing-censored descriptive checkpoints, not independent confirmation or a substitute for
finishing the registered study. The analysis retains exclusions, observed call/runtime
accounting and its closed acceptance report. Reference utility remains null until independently
adjudicated.

The new analysis wrapper suppresses degenerate bootstrap intervals when every observed cluster
contrast is identical: it retains the point estimate with status `no_observed_cluster_variation`
and no interval. A zero-width empirical interval cannot establish equivalence or safety. Frozen
historical analysis helpers are unchanged.

Public dashboards should consume only a closed numeric 3.4 adapter after seal validation.
Preserve raw source text, reference files, request histories and hardware state privately. The
existing source exporter must explicitly recognize 3.4; do not silently reinterpret 3.4 as 3.3.
Re-exporting a sealed attempt can update local views, but publishing to GitHub is a separate
reviewed action.

</details>

## Safe administrative handover
<details>
<summary><strong>Expand reference and commands</strong></summary>

The original 3.3 allocation keeps its own plan, attempt ledger and 8-hour budget.
`primary_allocation_release.py` never extends that budget or changes its status. Its watcher
accepts either actual registered completion or a separately verified expired, sealed prefix:

```bash
.venv/bin/python scripts/primary_allocation_release.py prepare \
  --root results/campaigns/PRIMARY_RELEASE_FRESH \
  --queue results/campaigns/OLD_PRIMARY_ALLOCATION --max-wait-hours 24
.venv/bin/python scripts/primary_allocation_release.py run \
  --root results/campaigns/PRIMARY_RELEASE_FRESH
```

The expiry branch requires elapsed execution at least the old cap, a contiguous completed
prefix, at most one last budget-exhausted attempt, no parse/other failed/unsealed attempt, exact
raw/manifest/state counters and the pinned real primary model. The shared primary lease must be
free when minting a receipt. Any other stopped state blocks automation.

Old logs record the exception class, not the precise `CallBudgetExhausted` cause. The receipt
therefore proves an expired sealed allocation independently; it does not assert what caused the
stop. Its status is `allocation_released`, and `old_study_complete` remains false for a partial
study. A distinct watcher state can say `completed` only within scope
`administrative_allocation_release`, allowing a newly registered prerequisite to wait on that
administrative action. `validate_receipt` rechecks the old immutable plan/state/seals before a
new allocation uses it. No receipt means the old experiment completed merely because a new
allocation may start.

The operator separately records supersession of any zero-call waiting quality/decomposition
queues. Preserve those original registrations and zero-call stopped states; never create fake
quality/finalization receipts. New decomposition or long-study allocations require new explicit
freezes and retain their own caps. The watcher itself performs zero inference and changes no
remote configuration.

</details>

## Hackathon cutoff
The current [official global guidelines](https://apartresearch.com/sprints/swarm-alignment-2026)
require the linked-template PDF, at most 8 main pages, a 150–250-word abstract,
authors/affiliations and a limitations/dual-use appendix. Code and a demo are optional. The
[organizer event page](https://www.aialignmentfoundation.org/hackathons/swarm-alignment-2026)
confirms the global November 8 23:59AoE deadline. These requirements were checked November
8,2026; final author/template review and actual submission remain manual.

At an observed 10 seconds per call, 19,320 scheduled responses alone take about 54 hours; this
is an estimate, not a promised completion time. A large continuation may outlast submission.
Freeze the PDF's evidence at a declared cutoff, include only sealed completed evidence, and
identify unfinished/post-deadline collection separately. If needed, register a compact
independent checkpoint before the larger continuation. Shared cases are not new independent
data, and a timing-based subset is not the completed registered full matrix.
