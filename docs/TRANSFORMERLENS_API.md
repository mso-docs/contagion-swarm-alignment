# TransformerLens 4 integration notes

These are primary-source API checks, not evidence that this repository has run TransformerLens. The current laptop environment has not executed these snippets. Pin the exact tested TransformerLens release and its dependency versions in the separate interpretability environment before collecting research data.

## Supported entry points

TransformerLens 4 uses `TransformerBridge`; legacy `HookedTransformer.from_pretrained` examples must not be copied unchanged. The [v4 migration guide](https://raw.githubusercontent.com/TransformerLensOrg/TransformerLens/main/docs/source/content/migrating_to_v4.md) documents `TransformerBridge.boot_native(TransformerBridgeConfig(...))` for randomly initialized native models. That native constructor was verified in documentation, not executed here; the fully specified offline alternative below uses a locally constructed Transformers model.

The [Transformers source adapter](https://raw.githubusercontent.com/TransformerLensOrg/TransformerLens/main/transformer_lens/model_bridge/sources/transformers/source.py) exposes these relevant arguments:

```python
TransformerBridge.boot_transformers(
    model_name, hf_config_overrides=None, device=None,
    dtype=torch.float32, tokenizer=None, load_weights=True,
    trust_remote_code=False, model_class=None, hf_model=None,
    n_ctx=None, revision=None, code_revision=None,
    checkpoint_index=None, checkpoint_value=None,
    device_map=None, n_devices=None, max_memory=None,
    offload_folder=None,
)
```

It does **not** accept `local_files_only` or `use_safetensors` directly. Supplying both `hf_model` and `tokenizer` avoids the adapter's Hub model/config/tokenizer loading paths for an ordinary text model. Leave compatibility transformations disabled when comparing against original model activations: folding and centering transformations change the numerical representation.

## Offline random-model smoke test

This validates tensor capture and hook plumbing only. Random activations say nothing about trained-model behavior, alignment, or the Ollama experiment.

```python
import torch
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
from transformers import GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast
from transformer_lens import TransformerBridge

vocab = {"<pad>": 0, "<unk>": 1, "<bos>": 2, "amber": 3, "blue": 4}
backend = Tokenizer(WordLevel(vocab, unk_token="<unk>"))
backend.pre_tokenizer = Whitespace()
tokenizer = PreTrainedTokenizerFast(
    tokenizer_object=backend, unk_token="<unk>",
    pad_token="<pad>", bos_token="<bos>", eos_token="<pad>",
)
torch.manual_seed(101)
config = GPT2Config(
    vocab_size=len(vocab), n_positions=64, n_ctx=64,
    n_layer=2, n_head=2, n_embd=32, n_inner=64,
    architectures=["GPT2LMHeadModel"],
    pad_token_id=0, bos_token_id=2, eos_token_id=0,
)
raw = GPT2LMHeadModel(config).eval()
bridge = TransformerBridge.boot_transformers(
    "contagion-offline-random-gpt2", hf_model=raw,
    tokenizer=tokenizer, device="cpu", dtype=torch.float32,
)
bridge.eval()
tokens = torch.tensor([[2, 3, 4]], dtype=torch.long)
```

The model name above is a local label, not a downloadable model tag. No pretrained weights are requested by this construction. For an actual smoke check, set offline mode externally as an additional guard and run the capture below.

## Pretrained checkpoints: pinned and local-only

Populate a local Hugging Face cache separately under explicit operator control. Replace both placeholders with the approved checkpoint identifier and its full commit SHA. This snippet deliberately fails if the approved cached files are missing:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = "<approved Hugging Face checkpoint>"
revision = "<full checkpoint commit SHA>"
tokenizer = AutoTokenizer.from_pretrained(
    model_id, revision=revision, local_files_only=True,
    trust_remote_code=False,
)
raw = AutoModelForCausalLM.from_pretrained(
    model_id, revision=revision, local_files_only=True,
    use_safetensors=True, trust_remote_code=False,
    attn_implementation="eager",
).eval()
bridge = TransformerBridge.boot_transformers(
    model_id, hf_model=raw, tokenizer=tokenizer,
    device="cpu", dtype=torch.float32,
)
```

The adapter source explicitly accepts an existing Hugging Face model. Review model architecture support and storage requirements before loading; an Ollama quantization is not automatically the same checkpoint or numerical model as its Transformers counterpart. Record repository, revision, tokenizer revision, dtype, quantization, library versions and token IDs with every artifact.

## Capture and activation interventions

The [bridge API source](https://raw.githubusercontent.com/TransformerLensOrg/TransformerLens/main/transformer_lens/model_bridge/bridge_core.py) supports `run_with_cache(input, names_filter=..., return_cache_object=False, remove_batch_dim=False, **kwargs)` returning `(output, cache)`, and `run_with_hooks(input, fwd_hooks=[(name, callback)], reset_hooks_end=True, **kwargs)`. Hook callbacks receive the activation tensor and `hook` context. Use inference mode for forward-only capture; backward capture requires gradients and an appropriate scalar loss.

Current canonical names are `blocks.L.hook_out` for the residual stream after a block and `blocks.L.mlp.out.hook_in` for post-activation MLP values. Familiar aliases `blocks.L.hook_resid_post` and `blocks.L.mlp.hook_post` map to these locations. Verify the actual available names for each architecture: [block aliases](https://raw.githubusercontent.com/TransformerLensOrg/TransformerLens/main/transformer_lens/model_bridge/generalized_components/block.py), [MLP aliases](https://raw.githubusercontent.com/TransformerLensOrg/TransformerLens/main/transformer_lens/model_bridge/generalized_components/mlp.py).

```python
names = ["blocks.0.hook_out", "blocks.0.mlp.out.hook_in"]
missing = [name for name in names if name not in bridge.hook_dict]
if missing:
    raise RuntimeError(f"Unsupported capture locations: {missing}")
with torch.no_grad():
    logits, cache = bridge.run_with_cache(
        tokens, names_filter=names, return_cache_object=False,
    )
assert cache[names[0]].shape[:2] == tokens.shape
# Residual: [batch, position, d_model]; MLP: [batch, position, d_mlp].
```

A minimal clean-to-corrupt residual patch is below. Require an explicit token-position alignment; matching string length is insufficient. Predeclare the target-token logit difference or other outcome before inspecting the patch result.

```python
name, position = "blocks.0.hook_out", 1
with torch.no_grad():
    clean_logits, clean_cache = bridge.run_with_cache(
        clean_tokens, names_filter=[name], return_cache_object=False,
    )
    corrupt_logits = bridge(corrupt_tokens)

    def patch(activation, hook):
        result = activation.clone()
        result[:, position, :] = clean_cache[name][:, position, :]
        return result

    patched_logits = bridge.run_with_hooks(
        corrupt_tokens, fwd_hooks=[(name, patch)], reset_hooks_end=True,
    )
```

Plot clean, corrupt and patched outcomes together, including no-op and position controls. Heatmaps show measured activation magnitudes; patch effects support a bounded causal claim about that intervention and outcome. Neither is a generic alignment score. A replay with another checkpoint is exploratory evidence, not the hidden state of the original Ollama run. Text explanations or exposed reasoning text must never be rendered as measured neural activations.

## Separate Linux CPU environment

Use a supported Linux machine under the operator's control; do not alter the experiment runner's environment or a remote host automatically. A conservative Python 3.11 environment avoids relying on Intel macOS Python 3.14 wheel availability:

```sh
python3.11 -m venv .venv-interp
.venv-interp/bin/python -m pip install --upgrade pip
.venv-interp/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
# Replace TESTED_VERSION with the exact verified TransformerLens 4 release.
.venv-interp/bin/python -m pip install 'transformer-lens==TESTED_VERSION'
.venv-interp/bin/python -m pip check
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv-interp/bin/python path/to/smoke.py
.venv-interp/bin/python -m pip freeze > interp-environment.lock.txt
```

Select PyTorch builds using its [official installation instructions](https://pytorch.org/get-started/locally/). The commands above are a setup recipe, not an installation or successful test claim. Run the seeded random smoke first, then a pinned trained-checkpoint replay, and keep both artifact types visibly distinct in the dashboard.
