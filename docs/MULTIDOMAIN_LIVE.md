# Guarded multidisciplinary live allocation

`scripts/multidomain_live.py` is a separate, frozen controller for the
protocol5.0 task docket. It does not alter earlier plans, their raw attempts or
the original mock-only rehearsal. Models have no tools or external targets.

The default allocation selects one development assignment per domain for three
rounds and all nineteen evaluation assignments for fifteen rounds. Each case has
clean, marker-override and reporting-pressure arms. Five private agents communicate
synchronously on a ring: **72 runs /4,500 scheduled calls**, with a10% physical-call
headroom and48-hour cumulative execution ceiling. The original thirteen development
assignments are not all evaluated; only five are selected for integration checks.

Before held-out calls, every domain must produce at least one clean final answer
that is non-unknown and cites existing evidence IDs. This is a weak structural
feasibility gate, not reference correctness or semantic citation validation.
Scripted mocks pass only a separately labeled shape gate; their behavior is never
accepted as live task-feasibility evidence. A gate failure stops collection.

```bash
.venv/bin/python scripts/multidomain_live.py prepare \
  --root results/campaigns/multidomain-live-FRESH \
  --catalog results/benchmarks/multidomain-evidence-v2 \
  --model INSTALLED_TAG --digest DISCOVERED_FULL_DIGEST \
  --after results/campaigns/PREDECESSOR/STATE.json \
  --rounds 15 --max-hours 48

.venv/bin/python scripts/multidomain_live.py run \
  --root results/campaigns/multidomain-live-FRESH \
  --provider ollama --env-file .env.primary
```

The endpoint must be the existing primary loopback tunnel. The controller verifies
the installed tag/digest and backend identity, takes the shared primary allocation
lease and makes serialized requests without hidden retries. It does not pull
models or modify services, networking, credentials or remote infrastructure.
The preceding state must complete; failed/stopped prerequisites block further calls.

Each response is a closed structured claim list with short explanations, confidence,
evidence IDs, a verification flag and a bounded peer note. The2,048-token output
reservation,32,768-token requested context and96,000-byte serialized request bound
are logged. The original task plus the last two own rounds and current peer notes
are retained; neither another agent's private history nor hidden targets are sent.
The raw controller log retains every request and response.

The controller checks remote RAM/temperature telemetry and cools conservatively.
Unknown critical telemetry, sustained heat, low disk, context/output truncation,
parse failure, source changes or budget exhaustion stop later calls. Startup
reserves estimated log capacity plus2GiB; per-call free disk must exceed512MiB.
No automatic retries occur. A root `STOP` file is honored before calls and while
waiting/cooling. The wait ceiling is96hours; individual runs are capped at two hours.

Outputs stay private under the allocation root:

```text
multidomain-live-plan.json
multidomain-live-state.json
development-gate.private.json
runs/job-NNN/attempt-NNN/{config.snapshot.json,events.jsonl,outcome.json,manifest.json,checksum.sha256}
recovery/decision-NNNNNN.private.json
```

Existing completed jobs skip only after assignment, model, counters, full artifact
coverage and seals validate. Failed attempts remain. Reviewed recovery requires
both `--resume` and `--retry-failed`; immutable chained receipts bind the retained
failures and previous budget debits. Unknown unsealed attempts reserve the entire
job call allowance and per-run wall limit. Neither counters nor raw bytes reset.

```bash
# After inspecting and resolving the failure:
.venv/bin/python scripts/multidomain_live.py run \
  --root results/campaigns/multidomain-live-FRESH \
  --provider ollama --env-file .env.primary --resume --retry-failed
```

Results distinguish exact-answer agreement, absent-evidence citations, unsupported
verification claims, unknown-reference answers and marker adoption. They do not
establish intentional deception, collusion, general alignment or neural mechanisms.
These remain static multi-part assignments, not autonomous long-horizon projects.
Protocol-specific dashboard/export support must validate its own closed schemas;
raw request histories and upstream task/answer content are not automatically public.

## Dashboard integration

The closed `followups.json` extension `multidomain` contains only hashed run/task
identities, domain/condition labels and numeric endpoints from sealed attempts.
Stored outcome scores are not trusted: the exporter recomputes from final artifact
events and private references. Development, evaluation, mock and live evidence stay
explicit. The newest completed attempt is preferred over retained failures, which
remain counted; incomplete-run endpoints stay unknown. Changing a seal/file or the
redaction policy invalidates cached rows.

The Research view has a separate multidisciplinary panel with evidence/domain
filters, domain coverage bars and distinct answer/citation/verification/marker
columns. Selecting a row requests `__private_multidomain/<hashed-id>` on the
loopback server. That bounded private view omits raw task sources, hidden answers,
request histories and event metadata, redacts model-generated text and shows at
most200events with4,096characters each. The web route must enforce loopback-only
access; the helper itself does not create a server or publish traces.
