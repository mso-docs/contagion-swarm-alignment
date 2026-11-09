# Secondary bounded-report recovery

**Current operational continuation:** after three3.8completions, a separate
settings-parser failure required isolated SSH configuration. Active collection is
now `secondary-isolated-recovery-20261108`, with the same scientific protocol3.8.
See [active experiments](ACTIVE_EXPERIMENTS.md) and
[telemetry isolation](SECONDARY_TELEMETRY_ISOLATION.md). Earlier states and attempts remain preserved.

The original protocol3.1 allocation preserved12completed runs and a failed attempt
at the1,536-token output ceiling. A separately registered protocol3.5 recovery
raised that ceiling to3,072tokens, but its first run again stopped after five
responses: the final response was truncated and only four artifacts parsed.
The input used5,855tokens, so neither failure was the32,768-token context ceiling.
No malformed artifact is scored as a completed answer.

Protocol `3.8-repository-bounded-output` addresses the reporting contract rather
than repeatedly increasing the output ceiling. It retains3,072output tokens and
the original task objectives, seeds, graph routing and full own history. It closes
extra answer fields, explicitly exposes the optional forbidden marker for adoption
measurement, and appends numerical field limits to the system instruction:
four findings, path256characters, description320characters, peer message256characters,
and complete JSON at most4,000characters. It forbids copying the input diff or peer
transcripts into output fields. These limits are checked by the parser even if the
backend does not enforce JSON-schema string limits. Length, context, parsing and
resource failures still stop later calls; no output is silently repaired or clipped.

The composite authoritative ledger contains630physical requests:625from protocol3.1
and five from protocol3.5. Both failed attempts and the12completed runs are retained.
There are24unfinished assignments /940scheduled responses and970requests available
under the original1,600-request ceiling. The old pair-level state reported620,
which excluded failed attempts; recovery never uses that undercount as its budget.

```bash
.venv/bin/python scripts/secondary_bounded_recovery.py inspect \
  --parent results/campaigns/secondary-output-recovery-20261108

.venv/bin/python scripts/secondary_bounded_recovery.py prepare \
  --parent results/campaigns/secondary-output-recovery-20261108 \
  --root results/campaigns/secondary-bounded-recovery-FRESH \
  --supplemental-hours 8

.venv/bin/python scripts/secondary_bounded_recovery.py run \
  --root results/campaigns/secondary-bounded-recovery-FRESH \
  --provider ollama --env-file .env.secondary
```

The first registered arm is the format preflight: every response is parsed and
checked before any later request, and the full first run must pass before another
assignment starts. There is no extra uncharged one-shot probe or automatic retry.
The first failed case is retried as the new documented protocol, with the prior
failed bytes preserved. New failures require explicit review/resume decisions.

Registration binds both ancestors' seals/counters, records a supplemental execution
allowance of one to twelve hours and reserves remaining physical authorization uniquely.
The active `secondary-bounded-recovery-20261108` registration uses twelve hours. It
does not alter prior plans, states or source. The live runner retains the pinned
secondary model/digest/readiness, loopback-only endpoint, secondary controller
lease, RAM/thermal/disk guards and full-history96,000-byte limit. Only the controller
may request inference or read-only telemetry; simulated agents remain tool-free.

Format instructions and answer schema are changed experimental conditions. Only
unfinished assignments enter3.8, so this is not a balanced new factorial matrix.
Keep3.1,3.5and3.8cohorts separate, preserve the failed-attempt denominators and
disclose the selected recovery subset. No compliance, correctness, intentional
dishonesty, official benchmark score or neural mechanism follows merely from a
successful schema/operational preflight. Public exports require the new closed
protocol schema; raw histories remain private.
