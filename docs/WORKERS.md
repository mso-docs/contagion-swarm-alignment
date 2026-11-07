# Primary and secondary AI workers

Use one experiment controller (the laptop initially), an existing Ollama server for inference, and an isolated neural worker. The second AI server can accept a separate cohort or a disjoint shard of the same frozen study. Logical agents stay controller-mediated; they never gain SSH, network or OS tools. Do not split one round or migrate an in-progress run across machines. No daemon, queue or distributed framework is required.

## Deployment boundary

The operator has requested server setup. Actual targets must be identified before connecting: primary and secondary SSH alias/user@host, approved project directory, Linux/Python/GPU hardware and available disk. Never put targets or credentials in tracked files. Do not change drivers, Ollama services/listen addresses, firewalls, SSH credentials or system packages as part of this project-local setup. Confirm any system-level prerequisite separately if preflight discovers it missing. Existing model downloads should be allowed to finish; do not restart Ollama.

The current scripts can be prepared/tested without contacting a server. Server installation is not complete until the commands below succeed on that server and actual measurement artifacts exist.

## Transfer and inventory

From the reviewed laptop source:

```sh
.venv/bin/python scripts/check_all.py
.venv/bin/python scripts/prepare_worker.py --out results/deployment/worker-source.tar.gz
```

The allowlisted archive includes source, tests, public dashboard assets, scenario definitions and a SHA-256 file manifest. It excludes `.env`, `.git`, caches, virtual environments, results and private tensors. It never overwrites an existing archive. Transfer it via the operator's SSH connection and unpack into a fresh approved project directory. No actual hostname is embedded in this guide.

On each Linux server, from the unpacked `contagion-worker` directory:

```sh
python3 scripts/setup_worker.py
# Review inventory, then install the controller and tests if it will run experiments:
python3 scripts/setup_worker.py --install --role controller
# Or controller plus isolated CPU neural environment:
python3 scripts/setup_worker.py --install --role both
```

Use Python 3.11+ with working `venv`, pip and Git. The installer stays under `.venv-worker` and `.venv-interp`, installs no model weights, runs pytest for the controller and records package versions under ignored `results/worker-setup`. It refuses to replace an existing worker environment. Use an existing environment's interpreter for subsequent commands. Dependency resolution on ARM64/other Python versions may differ from the laptop lock; inspect and audit the resulting package inventory before treating the worker as validated.

## Inference endpoints and pilot gate

For a controller running on a server, copy `.env.example` to `.env` privately and select the exact installed model. If its Ollama is local, use `http://127.0.0.1:11434`. For a laptop controller, use an existing private connection or an operator-managed SSH tunnel; avoid exposing Ollama publicly. Do not put usernames/passwords in URLs.

```sh
.venv-worker/bin/python scripts/run_pilot.py --doctor-only
.venv-worker/bin/python scripts/run_pilot.py --out results/server-rq1-pilot
```

Doctor lists installed models without pulling weights. The full pilot first validates/logs one inference response, then runs the bounded clean/injected pair and generates plots. Inspect parsing, latency and manual review before a larger batch. Existing `.env` can be used unchanged on the laptop with `.venv/bin/python` instead.

For a secondary endpoint on the laptop, create a separate ignored `.env.secondary` from the same example, and use:

```sh
.venv/bin/python scripts/run_pilot.py --env-file .env.secondary --doctor-only
.venv/bin/python scripts/run_pilot.py --env-file .env.secondary --out results/secondary-rq1-pilot
```

Shell variables override each env file. Use separate output roots and do not launch overlapping controllers against the same output root.

## Neural worker validation

The initial worker is deliberately CPU-only, which avoids changing the GPU stack or competing with Ollama for GPU memory. It supports small captures, not memory-efficient instrumentation of every large Ollama model. [PyTorch's installation selector](https://pytorch.org/get-started/locally/) and [NVIDIA's Spark guidance](https://docs.nvidia.com/dgx/dgx-spark/ngc.html) should govern any later GPU-specific environment; an ARM64/Blackwell server must be checked directly.

```sh
.venv-interp/bin/python scripts/capture_neural.py --doctor
.venv-interp/bin/python scripts/capture_neural.py --mode random-smoke --out results/neural/random-smoke
.venv-interp/bin/python scripts/export_research.py --neural results/neural/random-smoke --out results/neural/public-smoke.json
```

The actual random capture must complete before a pretrained checkpoint replay. A replay needs an explicitly chosen Hugging Face checkpoint, immutable revision, safe weight format, aligned clean/corrupt positions and single target token. Downloads require `--allow-download`; no existing Ollama weights are converted automatically. Keep raw safetensors/prompts private. The reduced public-smoke JSON can be transferred for inspection; random weights are instrumentation evidence only. Export with all desired study/monitor/review/neural sources on the controller before building Pages, since each export replaces the derived snapshot.

## Two-server experiment partitioning

First finish a successful pilot on each server. For the same cohort, select the same model tag and exact discovered digest, sampling parameters and source tree. Freeze the whole plan once. Each shard deterministically owns whole `(case, seed, topology)` groups, keeping control and injected runs together. Copy the same registry/freeze or run both controllers on the laptop. The assignment is persisted in each output root. No automatic failover or mid-run rerouting occurs.

Example from a single laptop controller (replace the shell variable with the exact digest shown by doctor; it is not a credential):

```sh
.venv/bin/python -m contagion.research scenarios --out results/scenarios-v2.sqlite
# Copy scenario_development.yaml to an ignored private plan, select its installed model,
# then freeze the final plan before either process starts.
.venv/bin/python -m contagion.research freeze --config results/plans/live.yaml --out results/freezes/live.json
.venv/bin/python -m contagion.research study --config results/plans/live.yaml --freeze results/freezes/live.json --provider ollama --env-file .env --expected-digest "$CONTAGION_COHORT_DIGEST" --shard-index 0 --shard-count 2 --out results/live-primary
.venv/bin/python -m contagion.research study --config results/plans/live.yaml --freeze results/freezes/live.json --provider ollama --env-file .env.secondary --expected-digest "$CONTAGION_COHORT_DIGEST" --shard-index 1 --shard-count 2 --out results/live-secondary
```

These last two commands may run in separate terminals. One active study per server bounds simultaneous inference to one call per endpoint. For differing model digests or hardware, treat outputs as different model/worker cohorts; worker allocation can confound results. Prefer independent model cohorts on each server initially. Never mix raw directories by overwriting; retain each server subtree and validate checksums during analysis. Public study rows expose the model digest where available.

## Readiness checklist

- Both targets identified; private SSH connectivity and disk/Python checks succeed.
- Core worker tests, dependency checks and mock pilot pass on every controller host.
- Existing Ollama is reachable and an installed model is discovered on each inference server.
- One logged live response and paired pilot succeed before batch inference.
- Neural import/runtime and actual random capture succeed; checkpoint replay remains separate.
- Source/plan/task/registry freezes are current and each process owns a disjoint output root.
- Generated summaries are validated and scrubbed; no raw logs/tensors or private endpoint data enter Pages.
- Publication is a separate review/commit/push action. Worker setup never pushes or deploys.

## Executed secondary installation

The operator supplied private targets/directories in `.env`. The secondary SSH preflight succeeded:Linux x86_64/Python3.14.4, approximately59GiB RAM and over1TiB free disk. Installed TransformerLens4.3.0 with torch2.15.0+cpu and transformers5.22.2 under a fresh release directory inside the approved project path. No root access, GPU allocation, service restart or firewall changes were used.

The initial offline tokenizer lacked the metadata expected by TransformerLens. Corrected the source to give its locally constructed tokenizer an explicit BOS postprocessor/name and prevent hub reload; preserved the previous source on the worker. An actual random-weight capture then succeeded:2layers,4tokens per input, residual RMS/MLP values and five logit conditions. No-op and first-position control agreed with the corrupt baseline within1e-6. This is a mechanical random-weight validation, not a trained model or original Ollama hidden state. No pretrained weight download occurred.

```sh
.venv/bin/python scripts/remote_worker.py preflight --server secondary
# To rerun a fresh random capture with the repository's reviewed capture source:
.venv/bin/python scripts/remote_worker.py smoke --server secondary
# Fetches the latest complete small capture to ignored local results and checks hashes:
.venv/bin/python scripts/remote_worker.py fetch --server secondary
# Read only scrubbed diagnostic text on a failure:
.venv/bin/python scripts/remote_worker.py diagnose --server secondary
```

The remote helper uses batch-mode SSH and strict existing host-key verification. It never echoes targets, sends private `.env`, asks for passwords, edits keys, or executes model-generated instructions. `install` needs an explicitly supplied reviewed bundle and creates a fresh release. `smoke` updates only the isolated capture module, backs up its previous contents and creates a fresh output directory. Captures record source/library hashes/versions. `fetch` accepts only four fixed artifact names and validates SHA-256 before publication processing.

Primary SSH preflight returned authentication failure; no primary shell access or configuration changes occurred. The operator confirmed the user/host are correct and normal login requires a password. For unattended key-only access, the operator must add their existing laptop public key to the primary account using ssh-copy-id in their own Terminal, then verify BatchMode SSH succeeds. Never put passwords or private keys in chat or .env. No credential changes are made automatically. The primary inference endpoint had already passed a live integration pilot before this turn; it was not load-tested while shared workloads were active. The meaning of the reported60limit is still unverified.
