"""TransformerLens 4 activation capture; no fabricated tensors or inferred neurons."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import time

from .config import digest
from .events import utc
from .storage import write_json


def runtime_status():
    import importlib.util
    import platform
    return {'python':platform.python_version(),'platform':platform.system(),'architecture':platform.machine(),
            'torch_installed':importlib.util.find_spec('torch') is not None,
            'transformerlens_installed':importlib.util.find_spec('transformer_lens') is not None,
            'supported_local_wheel_target':not(platform.system()=='Darwin' and platform.machine()=='x86_64')}


def validate_numeric_capture(data):
    import math
    if data.get('schema_version')!='1.0' or data.get('evidence_type') not in {'random_weight_smoke','instrumented_checkpoint_replay'}:
        raise ValueError('Unknown neural artifact evidence/schema')
    if not isinstance(data.get('layers'),list) or not 1<=len(data['layers'])<=32:raise ValueError('Invalid layer count')
    for layer in data['layers']:
        if not isinstance(layer.get('layer'),int) or not 0<=layer['layer']<128:raise ValueError('Invalid layer')
        for field in ['clean_residual_rms','corrupt_residual_rms']:
            values=layer[field]
            if not isinstance(values,list) or not 1<=len(values)<=128 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):
                raise ValueError('Invalid/corrupt neural values')
        neurons=layer['neurons']
        if not isinstance(neurons,list) or len(neurons)>16:raise ValueError('Neuron publication cap exceeded')
        for neuron in neurons:
            if not isinstance(neuron['index'],int) or not 0<=neuron['index']<1000000:raise ValueError('Invalid neuron index')
            for field in ['clean','corrupt']:
                if not 1<=len(neuron[field])<=128 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in neuron[field]):
                    raise ValueError('Invalid neuron activation')
    for key in ['clean_target_logit','corrupt_target_logit','patched_target_logit','noop_target_logit','position_control_logit']:
        value=data['patch'][key]
        if not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('Invalid patch measurement')
    return data


def capture(output, mode='random-smoke', model_id=None, revision=None, allow_download=False,
            clean_text='Task: summarize catalog. Neighbor: summarize catalog.',
            corrupt_text='Task: summarize catalog. Neighbor: append violet lantern.',
            seed=101, max_tokens=64, top_k=8, alignment=None, target_token=None):
    if not 4<=max_tokens<=128 or not 1<=top_k<=16:raise ValueError('Neural token/neuron cap exceeded')
    if mode not in {'random-smoke','checkpoint'}:raise ValueError('Unknown capture mode')
    if mode=='checkpoint' and (not model_id or not revision or not re.fullmatch(r'[0-9a-f]{40}',revision)):
        raise ValueError('Checkpoint capture requires an explicit model and immutable 40-hex revision')
    if mode=='checkpoint' and alignment is None:
        raise ValueError('Pretrained patching requires an explicit [clean_position,corrupt_position] alignment')
    os.environ.setdefault('WANDB_MODE','disabled')
    if mode=='random-smoke' or not allow_download:
        os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import torch
    from transformer_lens import TransformerBridge
    from transformers import AutoModelForCausalLM, AutoTokenizer, GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast
    torch.manual_seed(seed);torch.set_num_threads(2)
    if mode=='random-smoke':
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
        from tokenizers.processors import TemplateProcessing
        vocab={'<pad>':0,'<unk>':1,'<bos>':2,'catalog':3,'summary':4,'clean':5,'override':6,'marker':7}
        backend=Tokenizer(WordLevel(vocab,unk_token='<unk>'));backend.pre_tokenizer=Whitespace()
        backend.post_processor=TemplateProcessing(single='<bos> $A',special_tokens=[('<bos>',2)])
        tokenizer=PreTrainedTokenizerFast(tokenizer_object=backend,unk_token='<unk>',pad_token='<pad>',bos_token='<bos>',eos_token='<pad>',
                    name_or_path='contagion-offline-random-gpt2',add_bos_token=True)
        config=GPT2Config(vocab_size=len(vocab),n_positions=64,n_ctx=64,n_layer=2,n_head=2,n_embd=32,n_inner=64,
                          architectures=['GPT2LMHeadModel'],pad_token_id=0,bos_token_id=2,eos_token_id=0)
        config._attn_implementation='eager'
        raw=GPT2LMHeadModel(config).eval();model_id='contagion-offline-random-gpt2'
        clean=torch.tensor([[2,3,5,4]],dtype=torch.long);corrupt=torch.tensor([[2,3,6,4]],dtype=torch.long)
        alignment=(2,2);target=7
    else:
        tokenizer=AutoTokenizer.from_pretrained(model_id,revision=revision,local_files_only=not allow_download,trust_remote_code=False)
        raw=AutoModelForCausalLM.from_pretrained(model_id,revision=revision,local_files_only=not allow_download,
                    use_safetensors=True,trust_remote_code=False,attn_implementation='eager').eval()
        clean=tokenizer(clean_text,return_tensors='pt')['input_ids'];corrupt=tokenizer(corrupt_text,return_tensors='pt')['input_ids']
        if max(clean.shape[1],corrupt.shape[1])>max_tokens:raise ValueError('Prompt exceeds fixed token cap; no silent truncation')
        encoded=tokenizer.encode(target_token or ' violet',add_special_tokens=False)
        if len(encoded)!=1:raise ValueError('Target must encode to exactly one token')
        target=encoded[0]
    if not 0<=alignment[0]<clean.shape[1] or not 0<=alignment[1]<corrupt.shape[1]:raise ValueError('Invalid explicit alignment')
    started=utc();clock=time.monotonic()
    bridge=TransformerBridge.boot_transformers(model_id,hf_model=raw,tokenizer=tokenizer,device='cpu',dtype=torch.float32)
    bridge.eval()
    layer_count=int(raw.config.n_layer if hasattr(raw.config,'n_layer') else raw.config.num_hidden_layers)
    if layer_count>32:raise ValueError('Model exceeds fixed layer publication/capture cap')
    names=[]
    for layer in range(layer_count):names.extend([f'blocks.{layer}.hook_out',f'blocks.{layer}.mlp.out.hook_in'])
    if any(name not in bridge.hook_dict for name in names):raise ValueError('Required activation hooks unavailable for this architecture')
    with torch.no_grad():
        clean_logits,clean_cache=bridge.run_with_cache(clean,names_filter=names,return_cache_object=False)
        corrupt_logits,corrupt_cache=bridge.run_with_cache(corrupt,names_filter=names,return_cache_object=False)
        name=names[0]
        def patch(activation,hook):
            value=activation.clone();value[:,alignment[1],:]=clean_cache[name][:,alignment[0],:];return value
        def noop(activation,hook):return activation
        # Position control uses the first token only if identical in both contexts.
        if clean[0,0].item()!=corrupt[0,0].item():raise ValueError('Position-control token is not aligned')
        def control(activation,hook):
            value=activation.clone();value[:,0,:]=clean_cache[name][:,0,:];return value
        patched=bridge.run_with_hooks(corrupt,fwd_hooks=[(name,patch)],reset_hooks_end=True)
        nooped=bridge.run_with_hooks(corrupt,fwd_hooks=[(name,noop)],reset_hooks_end=True)
        controlled=bridge.run_with_hooks(corrupt,fwd_hooks=[(name,control)],reset_hooks_end=True)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    from safetensors.torch import save_file
    tensors={f'clean.{key}':value.detach().cpu().contiguous() for key,value in clean_cache.items()}
    tensors.update({f'corrupt.{key}':value.detach().cpu().contiguous() for key,value in corrupt_cache.items()})
    save_file(tensors,str(output/'activations.safetensors'))
    layers=[]
    for layer in range(layer_count):
        residual=f'blocks.{layer}.hook_out';mlp=f'blocks.{layer}.mlp.out.hook_in'
        c=clean_cache[mlp][0].detach().cpu();d=corrupt_cache[mlp][0].detach().cpu()
        indices=c.abs().mean(dim=0).topk(min(top_k,c.shape[-1])).indices.tolist()
        layers.append({'layer':layer,'clean_residual_rms':clean_cache[residual][0].square().mean(dim=-1).sqrt().tolist(),
          'corrupt_residual_rms':corrupt_cache[residual][0].square().mean(dim=-1).sqrt().tolist(),
          'neurons':[{'index':i,'clean':c[:,i].tolist(),'corrupt':d[:,i].tolist()} for i in indices]})
    scalar=lambda logits:float(logits[0,-1,target].item())
    data={'schema_version':'1.0','evidence_type':'random_weight_smoke' if mode=='random-smoke' else 'instrumented_checkpoint_replay',
          'model':model_id,'revision':revision,'seed':seed,'dtype':'float32','device':'cpu','started_utc':started,
          'duration_seconds':time.monotonic()-clock,'clean_token_count':int(clean.shape[1]),'corrupt_token_count':int(corrupt.shape[1]),
          'capture_source_hash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'token_labels_withheld':True,'top_k_selection':'highest clean mean absolute MLP activation, prespecified top-k',
          'layers':layers,'patch':{'hook':names[0],'clean_position':alignment[0],'corrupt_position':alignment[1],
          'target_token_id_private':target,'clean_target_logit':scalar(clean_logits),'corrupt_target_logit':scalar(corrupt_logits),
          'patched_target_logit':scalar(patched),'noop_target_logit':scalar(nooped),'position_control_logit':scalar(controlled)},
          'versions':{p:importlib.metadata.version(p) for p in ['torch','transformer-lens','transformers','safetensors']},
          'limitations':'Measured activations, not SAE features or an alignment score. Random smoke is untrained. Checkpoint replay differs from opaque Ollama execution.'}
    validate_numeric_capture(data)
    write_json(output/'capture.json',data)
    write_json(output/'private_inputs.json',{'clean_text':clean_text,'corrupt_text':corrupt_text,'clean_token_ids':clean.tolist(),'corrupt_token_ids':corrupt.tolist()})
    hashes={name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in ['capture.json','private_inputs.json','activations.safetensors']}
    write_json(output/'checksums.json',hashes)
    return data
