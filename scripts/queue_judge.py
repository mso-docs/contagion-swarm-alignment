"""Freeze and queue bounded advisory review after an allocated primary campaign."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from contagion.config import digest
from run_campaign import atomic,utc
from run_pilot import ROOT


def prepare(root,queue,after,model,model_digest):
    if len(model_digest)!=64 or any(c not in '0123456789abcdef' for c in model_digest):raise ValueError('Pin installed model digest')
    queue=Path(queue).resolve();root=Path(root).resolve();rows=json.loads((queue/'review_inputs.json').read_text())['samples']
    if not rows or len(rows)>64:raise ValueError('Judge queue needs1..64samples')
    root.mkdir(parents=True,exist_ok=False);runner=root/'judge_artifact_queue.py';shutil.copyfile(ROOT/'scripts/judge_artifact_queue.py',runner)
    plan={'schema_version':'primary-advisory-judge-1.0','worker':'primary','after':str(Path(after).resolve()),'queue':str(queue),
          'model':model,'model_digest':model_digest,'input_hash':digest(rows),'planned_calls':len(rows),'runner_sha256':hashlib.sha256(runner.read_bytes()).hexdigest(),
          'max_wait_seconds':24*3600,'max_run_seconds':7200,'calibrated':False}
    plan['plan_hash']=digest(plan);atomic(root/'judge-plan.private.json',plan);return plan


def run(root):
    root=Path(root).resolve();plan=json.loads((root/'judge-plan.private.json').read_text());runner=root/'judge_artifact_queue.py'
    if digest({k:v for k,v in plan.items() if k!='plan_hash'})!=plan['plan_hash']:raise ValueError('Judge plan changed')
    if hashlib.sha256(runner.read_bytes()).hexdigest()!=plan['runner_sha256']:raise ValueError('Judge controller changed')
    if digest(json.loads((Path(plan['queue'])/'review_inputs.json').read_text())['samples'])!=plan['input_hash']:raise ValueError('Review queue changed')
    with (root/'supervisor.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (root/'queue-state.json').exists():raise ValueError('No implicit reviewer retry')
        state={'status':'waiting','planned_calls':plan['planned_calls'],'completed_calls':0,'calibrated':False}
        def save(**kwargs):state.update(kwargs,updated_utc=utc());atomic(root/'queue-state.json',state)
        save();began=time.monotonic()
        try:
            while True:
                if (root/'STOP').exists():raise RuntimeError('Operator stop')
                previous=json.loads((Path(plan['after'])/'followup-state.json').read_text())
                if previous['status']=='completed':break
                if previous['status']=='stopped':raise RuntimeError('Preceding collection stopped')
                if time.monotonic()-began>plan['max_wait_seconds']:raise RuntimeError('Wait cap')
                time.sleep(30)
            save(status='running');environment=dict(os.environ,PYTHONPATH=str(ROOT/'scripts')+os.pathsep+os.environ.get('PYTHONPATH',''))
            with (root/'judge.private.log').open('x') as log:
                subprocess.run([sys.executable,str(runner),'--queue',plan['queue'],'--out',str(root/'review'),
                                '--model',plan['model'],'--digest',plan['model_digest'],'--worker','primary','--env-file',str(ROOT/'.env.primary'),
                                '--api','ollama','--max-calls',str(plan['planned_calls'])],cwd=ROOT,env=environment,stdout=log,stderr=log,check=True,timeout=plan['max_run_seconds'])
            result=json.loads((root/'review/judge-results.private.json').read_text())
            if len(result['results'])!=plan['planned_calls']:raise ValueError('Incomplete advisory review')
            save(status='completed',completed_calls=len(result['results']))
        except BaseException as exc:
            save(status='stopped',completed_calls=len(list((root/'review').glob('response-*.private.json'))),error_type=type(exc).__name__);raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    f=sub.add_parser('prepare');f.add_argument('--root',type=Path,required=True);f.add_argument('--queue',type=Path,required=True);f.add_argument('--after',type=Path,required=True);f.add_argument('--model',required=True);f.add_argument('--digest',required=True)
    r=sub.add_parser('run');r.add_argument('--root',type=Path,required=True);a=p.parse_args()
    if a.command=='prepare':plan=prepare(a.root,a.queue,a.after,a.model,a.digest);print('Frozen primary advisory review:',plan['planned_calls'],'calls; human calibration remains pending.')
    else:run(a.root)
