# Expanded trained-checkpoint reference grid

[Documentation home](README.md) · [Developer guide](DEVELOPMENT.md)


The expanded pilot measures the pinned trained GPT-2 checkpoint
`openai-community/gpt2@607a30d783dfa663caf39e06633721c8d4cfcd7e` on CPU. It is a
reference experiment, **not activation access to Ollama, Qwen or an agent swarm**.
The frozen capture implementation is reused without modification.

Six predeclared clean/corrupt pairs cross all twelve patch layers:

| Pair | Purpose | Predeclared target |
|---|---|---|
| France / Italy capital prompt | Familiar capability control | Paris |
| Pending / approved record prompt | Task-shaped instruction exploration | approved |
| Sum of2and2 /2and3 | Arithmetic capability control |4 |
| Four / five peer instruction | Task-shaped arithmetic exploration | five |
| Unknown / certain evidence claim | Missing-evidence reporting exploration | certain |
| No / yes verification claim | Unsupported-verification exploration | yes |

The tokenizer must observe each aligned span and target as a single token, preserve
the shared first-token position control and fit the32-token context ceiling.
The two existing capital/record pairs are mandatory; unsupported optional pairs
are rejected before measuring, with explicit reasons. No target-effect sign or
model correctness is used to select pairs. Target logits are measurements of
next-token prediction, not proof that GPT-2 follows an instruction, intentionally
lies or possesses an alignment mechanism.

The full grid has72cells. Existing capital/record captures at layers0,5and11 are
reused only when seals, checkpoint revision, seed, exact private prompts/token IDs,
target ID, alignment, layer, dtype, device, capture implementation and top-four
neuron shape match. With all six eligible pairs, this gives **six reused cells and
66new captures**, rather than counting identical old measurements as new coverage.
Repeated baselines, layers and prompt pairs are dependent;72cells are not72
independent scientific trials.

## Measurements and checks
Each new capture contains actual residual RMS, selected MLP activation values,
clean/corrupt target logits and a clean-to-corrupt residual patch at one layer.
The raw model and instrumented bridge must agree at the frozen tolerances. A
no-op hook and aligned identical-prefix position patch must differ from the
corrupt baseline by at most1e-5. Target restoration is undefined when the clean–
corrupt gap is near zero; arbitrary sign, overshoot and null effects are retained.
Top neurons are selected by prespecified clean activation magnitude. There are no
SAE feature labels, invented neuron meanings, private-thinking transcripts or
claims about the deployed swarm model's internals.

`capture.json`, `private_inputs.json` and `activations.safetensors` are sealed by
`checksums.json` per capture. Plans bind local source and cached checkpoint files.
Resume verifies completed cells, preserves partial attempts and requires explicit
retry for failed attempts. New processes and attempts have finite budgets; prior
attempts are not overwritten. File checksums detect accidental changes and are not
an externally anchored tamper-proof record.

## Worker boundaries
The operator helper creates a separate `interp-grid-*` project release. It does
not match legacy `trained-*`, `neural-*` or `suite-*` selectors. It reuses the
existing CPU Python environment and exact local GPT-2 cache, installs nothing and
downloads nothing. CUDA devices are hidden. Child processes use two CPU threads,
a3GiB RSS watchdog, a120-second per-capture wall ceiling and a CPU-time limit.
The allocation ceiling is two hours. Each new child requires4GiB available RAM,
8GiB free disk and known CPU thermal telemetry below85°C; during capture,90°C or
critical RAM pressure stops the process. These are conservative operational
limits, not a guarantee against hardware failure. GPU behavioral collection keeps
its separate controller and model allocation.

## Operator commands
<details>
<summary><strong>Expand reference and commands</strong></summary>

Use the isolated two-field SSH snapshot, never the broad credential environment:

```bash
.venv/bin/python scripts/expanded_neural_worker.py discover \
  --env-file results/campaigns/secondary-isolated-recovery-20261108/telemetry.env \
  --record results/neural-expanded/discovery.private.json

.venv/bin/python scripts/expanded_neural_worker.py bundle \
  --env-file results/campaigns/secondary-isolated-recovery-20261108/telemetry.env \
  --record results/neural-expanded/source.private.json \
  --bundle results/neural-expanded/worker-source-FRESH.tar.gz

# Deploy only reviewed project source; this prepares the tokenizer-frozen plan,
# reuses installed dependencies/cache and starts no capture process.
.venv/bin/python scripts/expanded_neural_worker.py deploy \
  --env-file results/campaigns/secondary-isolated-recovery-20261108/telemetry.env \
  --record results/neural-expanded/deployment.private.json \
  --bundle results/neural-expanded/worker-source-FRESH.tar.gz

# Separate explicit launch, after reviewing source and prepared bounds.
.venv/bin/python scripts/expanded_neural_worker.py launch \
  --env-file results/campaigns/secondary-isolated-recovery-20261108/telemetry.env \
  --record results/neural-expanded/deployment.private.json

.venv/bin/python scripts/expanded_neural_worker.py watch \
  --env-file results/campaigns/secondary-isolated-recovery-20261108/telemetry.env \
  --record results/neural-expanded/deployment.private.json
```

Discovery/deployment records contain private worker/cache paths and remain under
ignored `results`. User-facing output prints counts and booleans, never hosts or
credentials. Deployment is separate from launch. The worker runs independently
on the secondary machine; the local sync loop requires connectivity to display
fresh data. Actual elapsed time and remaining-time estimates become available
after new measured captures complete; earlier0.4-second forward measurements omit
Python startup and model loading and are not a full-run ETA.

The generic collector reads the new pilot's completed sealed cells, rather than a
legacy six-capture status file. It verifies transferred files, stages them outside
the neural source tree and atomically renames complete captures into `results/neural`.
The existing derived dashboard sync then consumes all measured numeric summaries.
Private prompts and tensors remain private; public snapshots use the existing
closed neural schema. The helper's `sync(env_file, deployment_file, limit=2)` API
also supports a dashboard-managed polling loop.

</details>
