"""Queued, bounded long-input horizon comparison; no change to the active baseline."""
import argparse
import fcntl
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

from contagion.storage import source_fingerprint,verify
from repository_benchmark import sha
from run_campaign import atomic,utc,validate_readiness
from run_pilot import ROOT


def prepare(root,catalog,selection,readiness):
    root=Path(root)
    if root.exists():raise ValueError('Use a fresh long-horizon directory')
    proof=validate_readiness(readiness);catalog=Path(catalog).resolve();selection=Path(selection)
    data=json.loads(catalog.read_text());initial=json.loads(selection.read_text())
    for record,key in [(data,'catalog_hash'),(initial,'freeze_hash')]:
        if sha(json.dumps({k:v for k,v in record.items() if k!=key},sort_keys=True).encode())!=record[key]:raise ValueError('Input registry changed')
    long=[r for r in initial['tasks'] if r['input_length']=='long']
    if len(long)<3:raise ValueError('Need the original long control and two further long cases')
    cases=long[1:3]  # Exclude the case already used by the sequential prechecks.
    root.mkdir(parents=True);controller=root/'controller/run_repository_study.py';controller.parent.mkdir()
    shutil.copyfile(ROOT/'scripts/run_repository_study.py',controller)
    freezes={}
    for rounds in [3,8,15]:
        content={'protocol_version':'3.1-repository','design_version':'3.2-long-input-horizon',
            'catalog_hash':data['catalog_hash'],'tasks':[{**r,'planned_rounds':rounds} for r in cases],
            'selection_seed':3811,'question':'Does review horizon change boundary failures or unsupported execution claims on matched long inputs?',
            'limitations':['Two task cases; one matched seed.','Same long inputs cross three horizons; task correctness is not yet independently judged.',
                'Repeated cases and conditions are dependent.','An error, omission or faster response does not prove deliberate cheating.']}
        content['freeze_hash']=sha(json.dumps(content,sort_keys=True).encode());filename=f'freeze-h{rounds:02}.json';atomic(root/filename,content);freezes[rounds]=filename
    jobs=[{'case_id':case['id'],'rounds':rounds,'topology':topology,'freeze':freezes[rounds],'calls':rounds*10}
          for case,rounds,topology in itertools.product(cases,[3,8,15],['ring','star','complete'])]
    random.Random(3811).shuffle(jobs)
    plan={'schema_version':'long-horizon-1.0','created_utc':utc(),'catalog':str(catalog),'source_hash':source_fingerprint(),
        'controller_sha256':sha(controller.read_bytes()),'readiness':str(Path(readiness).resolve()),'readiness_hash':proof['readiness_hash'],
        'jobs':jobs,'planned_calls':sum(j['calls'] for j in jobs),'planned_runs':len(jobs)*2,
        'max_http_attempts':1600,'max_run_seconds':8*3600,'max_wait_seconds':16*3600,'seed':2718,'worker':'secondary'}
    plan['plan_hash']=sha(json.dumps(plan,sort_keys=True).encode());atomic(root/'long-horizon.json',plan)
    return plan


def run(root,after):
    root=Path(root);plan=json.loads((root/'long-horizon.json').read_text())
    if sha(json.dumps({k:v for k,v in plan.items() if k!='plan_hash'},sort_keys=True).encode())!=plan['plan_hash']:raise ValueError('Queue plan changed')
    controller=root/'controller/run_repository_study.py'
    if sha(controller.read_bytes())!=plan['controller_sha256']:raise ValueError('Frozen controller changed')
    with (root/'queue.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (root/'queue-state.json').exists():raise ValueError('No automatic retry of prior queue state')
        state={'status':'waiting','started_utc':utc(),'completed_pairs':0,'http_attempts':0,'planned_runs':plan['planned_runs'],'planned_calls':plan['planned_calls']}
        def save(**kw):state.update(kw,updated_utc=utc());atomic(root/'queue-state.json',state)
        save();waiting=time.monotonic();began=None
        try:
            while True:
                if (root/'STOP').exists():raise RuntimeError('Operator stop')
                parent=json.loads((Path(after)/'overnight.json').read_text())
                if parent['status']=='completed':break
                if parent['status']=='stopped':raise RuntimeError('Preceding collection stopped; review it first')
                if time.monotonic()-waiting>plan['max_wait_seconds']:raise RuntimeError('Wait budget exhausted')
                time.sleep(30)
            proof=validate_readiness(plan['readiness'])
            if proof['readiness_hash']!=plan['readiness_hash']:raise ValueError('Readiness changed')
            began=time.monotonic()
            for index,job in enumerate(plan['jobs']):
                if (root/'STOP').exists() or time.monotonic()-began>plan['max_run_seconds']:raise RuntimeError('Stop or wall budget')
                if state['http_attempts']+job['calls']>plan['max_http_attempts']:raise RuntimeError('Call budget')
                save(status='running',job_index=index,rounds=job['rounds'],topology=job['topology'])
                output=ROOT/'results/repository-runs'/root.name/f'job-{index:03}'
                command=[sys.executable,str(controller),'--freeze',str(root/job['freeze']),'--catalog',plan['catalog'],
                    '--task-id',job['case_id'],'--out',str(output),'--topology',job['topology'],'--provider','ollama',
                    '--readiness',plan['readiness'],'--max-calls','150','--stop-file',str(root/'STOP')]
                env=dict(os.environ);env['PYTHONPATH']=str(ROOT/'scripts')+os.pathsep+env.get('PYTHONPATH','')
                with (root/f'job-{index:03}.private.log').open('x') as log:
                    subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=log,check=True,timeout=min(7200,max(1,plan['max_run_seconds']-(time.monotonic()-began))))
                manifests=list(output.rglob('manifest.json'))
                if len(manifests)!=2 or any(not verify(p.parent) or json.loads(p.read_text())['status']!='completed' for p in manifests):raise RuntimeError('Pair did not validate')
                state['http_attempts']+=sum(json.loads(p.read_text())['http_attempts'] for p in manifests);state['completed_pairs']+=1;save()
            save(status='completed')
        except BaseException as exc:
            save(status='stopped',error_type=type(exc).__name__);raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--root',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--selection',type=Path,required=True);p.add_argument('--readiness',type=Path,required=True)
    r=sub.add_parser('run');r.add_argument('--root',type=Path,required=True);r.add_argument('--after',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='prepare':
        plan=prepare(args.root,args.catalog,args.selection,args.readiness);print('Registered',plan['planned_runs'],'long-input runs /',plan['planned_calls'],'scheduled responses; horizons3/8/15 on matched cases.')
    else:run(args.root,args.after)
