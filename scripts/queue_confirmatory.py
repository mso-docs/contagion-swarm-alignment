"""Wait for registered long-input work, then run frozen follow-ups serially."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from contagion.config import digest
from contagion.storage import verify
from run_campaign import atomic,utc
from run_confirmatory import build_plan,verify_plan,precheck_plan
from run_pilot import ROOT


def prepare(root,model,model_digest,after=None,worker="secondary"):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    if len(model_digest)!=64 or any(c not in '0123456789abcdef' for c in model_digest):raise ValueError('Pin discovered digest')
    jobs=[]
    for question in (['rq3-precheck'] if worker=='primary' else [])+['rq3','rq1']:
        plan=precheck_plan(model,model_digest,worker) if question=='rq3-precheck' else build_plan(question,model,model_digest,worker);atomic(root/(question+'.json'),plan)
        jobs.append({'question':question,'freeze_hash':plan['freeze_hash'],'planned_calls':plan['planned_calls'],'planned_runs':plan['planned_runs']})
    frozen=root/'run_confirmatory.py';frozen.write_bytes((ROOT/'scripts/run_confirmatory.py').read_bytes())
    record={'schema_version':'confirmatory-queue-1.0','created_utc':utc(),'worker':worker,'after':str(Path(after).resolve()) if after else None,'jobs':jobs,
            'controller_sha256':hashlib.sha256(frozen.read_bytes()).hexdigest(),'max_wait_seconds':24*3600,'max_execution_seconds':8*3600,
            'planned_runs':sum(j['planned_runs'] for j in jobs),'planned_calls':sum(j['planned_calls'] for j in jobs)}
    record['queue_hash']=digest(record);atomic(root/'followup-plan.json',record);return record


def run(root):
    root=Path(root);record=json.loads((root/'followup-plan.json').read_text());controller=root/'run_confirmatory.py'
    if digest({k:v for k,v in record.items() if k!='queue_hash'})!=record['queue_hash']:raise ValueError('Queue changed')
    if hashlib.sha256(controller.read_bytes()).hexdigest()!=record['controller_sha256']:raise ValueError('Controller changed')
    with (root/'followup.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (root/'followup-state.json').exists():raise ValueError('No implicit resume/retry')
        state={'status':'waiting','planned_runs':record['planned_runs'],'planned_calls':record['planned_calls'],'completed_runs':0,'physical_calls':0,'failed_runs':0}
        def save(**kw):state.update(kw,updated_utc=utc());atomic(root/'followup-state.json',state)
        save();waiting=time.monotonic();began=None
        try:
            while record['after'] is not None:
                if (root/'STOP').exists():raise RuntimeError('Operator stop')
                previous=json.loads((Path(record['after'])/'queue-state.json').read_text())
                if previous['status']=='completed':break
                if previous['status'] in {'stopped','failed','budget_exhausted'}:raise RuntimeError('Preceding queue stopped; review before more inference')
                if time.monotonic()-waiting>record['max_wait_seconds']:raise RuntimeError('Wait budget')
                time.sleep(30)
            began=time.monotonic()
            for job in record['jobs']:
                plan=json.loads((root/(job['question']+'.json')).read_text());verify_plan(plan)
                if plan['freeze_hash']!=job['freeze_hash']:raise ValueError('Follow-up freeze changed')
                if (root/'STOP').exists():raise RuntimeError('Operator stop')
                save(status='running',question=job['question'])
                output=root/job['question']
                # run_confirmatory needs scripts imports; keep its frozen filename/module __file__ hash.
                import os
                env=dict(os.environ,PYTHONPATH=str(ROOT/'scripts')+os.pathsep+os.environ.get('PYTHONPATH',''))
                with (root/(job['question']+'.private.log')).open('x') as log:
                    subprocess.run([sys.executable,str(controller),'run','--plan',str(root/(job['question']+'.json')),'--out',str(output),
                                    '--provider','ollama','--env-file',str(ROOT/('.env.'+record['worker']))],cwd=ROOT,env=env,stdout=log,stderr=log,check=True,
                                   timeout=max(1,record['max_execution_seconds']-(time.monotonic()-began)))
                manifests=list(output.glob('run-*/manifest.json'))
                if len(manifests)!=job['planned_runs'] or any(not verify(p.parent) or json.loads(p.read_text())['status']!='completed' for p in manifests):raise ValueError('Incomplete follow-up')
                state['completed_runs']+=len(manifests);state['physical_calls']+=sum(json.loads(p.read_text())['http_attempts'] for p in manifests);save()
                subprocess.run([sys.executable,str(ROOT/'scripts/analyze_confirmatory.py'),'--source',str(output),'--out',str(root/(job['question']+'-analysis.private.json'))],cwd=ROOT,env=env,check=True)
            save(status='completed')
        except BaseException as exc:
            # Existing raw attempts are retained even when the supervisor is stopped.
            manifests=list(root.glob('rq*/run-*/manifest.json'))
            save(status='stopped',error_type=type(exc).__name__,completed_runs=sum(json.loads(p.read_text())['status']=='completed' for p in manifests),
                 failed_runs=sum(json.loads(p.read_text())['status']!='completed' for p in manifests),physical_calls=sum(json.loads(p.read_text())['http_attempts'] for p in manifests));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('prepare');q.add_argument('--root',type=Path,required=True);q.add_argument('--model',required=True);q.add_argument('--digest',required=True);q.add_argument('--after',type=Path);q.add_argument('--worker',choices=['primary','secondary'],default='secondary')
    r=sub.add_parser('run');r.add_argument('--root',type=Path,required=True);a=p.parse_args()
    if a.command=='prepare':
        record=prepare(a.root,a.model,a.digest,a.after,a.worker);print('Frozen',record['planned_runs'],'runs /',record['planned_calls'],'calls; waits for prior long-input queue.')
    else:run(a.root)
