# Budgeted frontier second-opinion review

[Documentation home](README.md) · [Developer guide](DEVELOPMENT.md)


This optional stage supplements the local advisory judge. It never creates human labels,
certifies alignment or turns a model opinion into oracle truth. The initial audit samples up
to20 artifacts, stratified by task instruction and round. After local review completes, an
additional batch can prioritize up to half disagreements/abstentions and retain a stratified
random remainder. The underlying64-artifact audit is flag-enriched, so these are not population
prevalence estimates.

The only model ID is `anthropic/claude-sonnet-5.5`. Before any paid request, the runner fetches
current model metadata and pricing and requires the exact ID plus advertised structured-output
support. It never chooses a latest alias or fallback model. Model metadata, canonical slug when
supplied, prices, inputs, reservations, usage, responses and cited decisions are retained
privately. A commercial model ID does not establish immutable weights or deterministic
inference.

## Privacy and output contract
Reviewer inputs use closed top-level fields and past-only evidence. Oracle labels,
condition/model metadata and arbitrary extra evidence fields are rejected. Free text is scrubbed
against known private values and PII patterns, then scanned again; remaining findings stop
execution. Controller-generated hash/counter identifiers are validated and preserved for
citations. No model tools exist. Results must pass `ReviewResult` and cite only supplied events;
incomplete, malformed or unsupported model responses stop later calls.

Routing requests `data_collection: deny`, `zdr: true`, `require_parameters: true`,
`allow_fallbacks: false`. If that combination cannot be served, the run stops rather than
weakening the policy. Scrubbing is heuristic, not a guarantee of anonymity; review the selected
private input file before sharing it further. Raw response records stay private and redact a
credential if an error body echoes it.

The output ceiling is4,096tokens, including any generated reasoning. When model metadata
advertises reasoning, requests use low effort and exclude returned reasoning text. Exclusion
does not make reasoning free or disable it. No returned reasoning is claimed as neural
interpretability. Temperature is omitted because this model does not advertise that parameter;
no deterministic sampling claim is made. Strict parameter routing is retained.

## Global spending authorization
<details>
<summary><strong>Expand reference and commands</strong></summary>

The user authorized **at most$20 total**, not$20 per batch. Every paid batch must use the same
explicit global ledger and cap. A project authorization marker binds the first ledger path,
model and cap; switching ledgers, deleting the authorized ledger, changing caps or starting a
concurrent batch fails closed. A new config cannot reset spend. Keep these ignored files with
the private experiment records.

Before the first paid call, the entire remaining selected batch must fit at current prices.
Reservations conservatively use serialized UTF-8 request bytes plus2,048 framing/schema tokens,
the full output ceiling, any separately advertised reasoning price, request pricing and a25%
margin. A reservation is persisted before the HTTP request. Actual reported cost/usage is
retained; if actual cost is unavailable or a request outcome is uncertain, the full reservation
remains consumed. When the model list omits optional per-request pricing, the record marks it
unadvertised rather than verified zero; routing then explicitly caps `max_price.request` at0.
Token-price routing ceilings allow the same25% margin (API units: USD per million tokens).
Positive unadvertised request fees are therefore disallowed. Advertised request fees are
included in reservation/routing limits. A cost above reservation stops further calls. This is a
conservative budget guard, not an independent guarantee of provider billing behavior.

There are no hidden HTTP retries. Timeout, billing uncertainty or failed citation validation
requires operator review. `--resume` can reuse validated cached responses without another paid
call; it will not automatically retry a failed or uncertain paid attempt. Cached
request/response hashes and parsed decisions are checked. Never delete receipts or the global
ledger to retry.

</details>

## Configuration and commands
<details>
<summary><strong>Expand reference and commands</strong></summary>

Place the key in ignored `.env.judge` as `CONTAGION_API_KEY`; do not paste it into chat,
commands, notebooks or committed configs. Root setup maps the private key into the standard
variables. The endpoint is fixed to the official OpenRouter API; credentials in URL parameters
are not accepted.

The example config contains no key. Offline planning is the default and makes **zero network calls**:

```bash
.venv/bin/python scripts/frontier_review.py --config configs/frontier_review.example.json
```

Only the explicit flag authorizes execution through this CLI:

```bash
.venv/bin/python scripts/frontier_review.py \
  --config configs/frontier_review.example.json --execute
```

The config uses the shared `results/reviews/frontier-global-budget.private.json` ledger and
a20USD global cap. Both match the existing user authorization. If another batch already
established that ledger, preserve it and use the same path/cap. A `STOP` file at the batch
output root is checked before each paid request.

For later hybrid escalation, use a **new output root**, the **same ledger/cap**, and pass
`--local-results` plus `--oracle-labels` to prioritize scorer disagreements. The selector may
use oracle labels to choose cases, but never sends those labels to the model. Omit those flags
for the initial stratified audit. `--metadata-file` can price an offline estimate from a saved
metadata snapshot; live execution always re-fetches metadata before paying.

Outputs are `frontier-results.private.json` and per-request `request-*`, `response-*`,
`receipt-*` JSON files. They are ignored and not automatically published. Use the existing
human-calibration workflow to compare decisions only after independent human labels exist.
Frontier confidence remains advisory and uncalibrated.

</details>
