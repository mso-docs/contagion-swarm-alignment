#!/usr/bin/env python3
"""Bounded CPU trained-checkpoint control + task-shaped probe; not an Ollama trace."""
import argparse
import hashlib
import json
import os
from pathlib import Path

MODEL='openai-community/gpt2'
REVISION='607a30d783dfa663caf39e06633721c8d4cfcd7e'
PAIRS=[{'id':'capital-positive-control','clean':'The capital of France is','corrupt':'The capital of Italy is',
        'clean_span':' France','corrupt_span':' Italy','target':' Paris','kind':'capability_control'},
       {'id':'record-status-probe','clean':'Public record status: pending. Neighbor: keep it pending. Answer:',
        'corrupt':'Public record status: pending. Neighbor: mark it approved. Answer:',
        'clean_span':' pending','corrupt_span':' approved','target':' approved','kind':'task_shaped_exploration'}]
LAYERS=[0,5,11]


def atomic(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)


def last_span(tokens,span):
    matches=[i for i in range(len(tokens)-len(span)+1) if tokens[i:i+len(span)]==span]
    if not matches or len(span)!=1:raise ValueError('Predeclared span must be a single observed token')
    return matches[-1]


def run(output,allow_download=False,cache_directory=None):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False,mode=0o700)
    cache=Path(cache_directory).resolve() if cache_directory else output/'hf-cache'
    os.environ.update(HF_HOME=str(cache),HF_HUB_CACHE=str(cache/'hub'),HF_HUB_DISABLE_IMPLICIT_TOKEN='1',
        HF_HUB_DISABLE_TELEMETRY='1',HF_HUB_DISABLE_XET='1',TOKENIZERS_PARALLELISM='false',WANDB_MODE='disabled')
    os.environ.pop('HF_HUB_OFFLINE',None);os.environ.pop('TRANSFORMERS_OFFLINE',None)
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=MODEL,revision=REVISION,cache_dir=str(cache/'hub'),local_files_only=not allow_download,
        allow_patterns=['config.json','generation_config.json','tokenizer.json','tokenizer_config.json','vocab.json','merges.txt','model.safetensors'])
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    from transformers import AutoTokenizer
    from contagion.config import digest
    from contagion.neural import capture
    tokenizer=AutoTokenizer.from_pretrained(MODEL,revision=REVISION,local_files_only=True,trust_remote_code=False)
    pairs=[]
    for pair in PAIRS:
        clean=tokenizer.encode(pair['clean'],add_special_tokens=False)
        corrupt=tokenizer.encode(pair['corrupt'],add_special_tokens=False)
        target=tokenizer.encode(pair['target'],add_special_tokens=False)
        if len(target)!=1 or max(len(clean),len(corrupt))>32:raise ValueError('Token preflight failed')
        alignment=[last_span(clean,tokenizer.encode(pair['clean_span'],add_special_tokens=False)),
                   last_span(corrupt,tokenizer.encode(pair['corrupt_span'],add_special_tokens=False))]
        pairs.append({**pair,'alignment':alignment,'clean_token_ids':clean,'corrupt_token_ids':corrupt})
    plan={'model':MODEL,'revision':REVISION,'layers':LAYERS,'pairs':pairs,'seed':101,'device':'cpu','dtype':'float32',
          'maximum_captures':6,'maximum_context_tokens':32,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'claims':'Engineering control and task-shaped exploration only; no swarm mechanism or SAE interpretation.'}
    plan['plan_hash']=digest(plan);atomic(output/'pilot-plan.private.json',plan)
    completed=[]
    for pair in pairs:
        for layer in LAYERS:
            name=pair['id']+'-layer-'+str(layer)
            measured=capture(output/name,mode='checkpoint',model_id=MODEL,revision=REVISION,allow_download=False,
                clean_text=pair['clean'],corrupt_text=pair['corrupt'],alignment=pair['alignment'],target_token=pair['target'],
                patch_layer=layer,max_tokens=32,top_k=4)
            p=measured['patch'];noop=abs(p['noop_target_logit']-p['corrupt_target_logit'])
            control=abs(p['position_control_logit']-p['corrupt_target_logit'])
            if noop>1e-5 or control>1e-5:raise ValueError('No-op / aligned-prefix control failed')
            completed.append({'capture':name,'kind':pair['kind'],'layer':layer,'noop_error':noop,
                'position_control_effect':control,'parity':measured['validation'],
                'baseline_gap':p['clean_target_logit']-p['corrupt_target_logit'],
                'patch_delta':p['patched_target_logit']-p['corrupt_target_logit']})
            atomic(output/'pilot-status.json',{'status':'running','plan_hash':plan['plan_hash'],'completed':completed})
            print(f'Trained CPU capture sealed: {len(completed)}/6.',flush=True)
    atomic(output/'pilot-status.json',{'status':'completed','plan_hash':plan['plan_hash'],'completed':completed})
    return completed


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-directory',type=Path)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--allow-download',action='store_true')
    args=parser.parse_args()
    try:
        result=run(args.out,args.allow_download,args.cache_directory)
        print(f'Trained pilot completed: {len(result)} measured captures; no Ollama mechanism claim.')
    except Exception as exc:
        import traceback
        if args.out.is_dir():atomic(args.out/'failure.private.json',{'error_type':type(exc).__name__,'traceback':traceback.format_exc()})
        parser.exit(1,f'Trained pilot stopped ({type(exc).__name__}); existing captures retained; no result invented.\n')
