"""Queue local semantic quality review after immutable long-task finalization."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import time

from contagion.config import digest
from run_campaign import atomic,utc
from run_pilot import ROOT


def prepare(output,receipt,queue,model_digest):
    from judge_repository_quality import MODEL
    if len(model_digest)!=64 or any(c not in '0123456789abcdef' for c in model_digest):raise ValueError('Pin discovered local judge digest')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    plan={'schema_version':'repository-advisory-queue-1.0','model':MODEL,'model_digest':model_digest,
          'receipt':str(Path(receipt).resolve()),'queue':str(Path(queue).resolve()),'max_wait_seconds':24*3600,
          'max_scheduled_calls':128,'max_physical_calls':160,'max_execution_seconds':14400,
          'driver_sha256':hashlib.sha256((ROOT/'scripts/judge_repository_quality.py').read_bytes()).hexdigest()}
    plan['plan_hash']=digest(plan);atomic(output/'queue-plan.private.json',plan);return plan


def run(output):
    from judge_repository_quality import prepare as freeze,run as judge
    output=Path(output);plan=json.loads((output/'queue-plan.private.json').read_text())
    if digest({k:v for k,v in plan.items() if k!='plan_hash'})!=plan['plan_hash'] or hashlib.sha256((ROOT/'scripts/judge_repository_quality.py').read_bytes()).hexdigest()!=plan['driver_sha256']:raise ValueError('Registered advisory driver changed')
    state_file=output/'queue-state.json'
    if state_file.exists():raise ValueError('No implicit requeue; preserve original allocation')
    state={'status':'waiting','worker':'primary','max_calls':plan['max_scheduled_calls'],'human_labels_generated':0}
    def save(**kw):state.update(kw,updated_utc=utc());atomic(state_file,state)
    save();began=time.monotonic()
    try:
        while True:
            if (output/'STOP').exists():raise RuntimeError('Operator stop')
            receipt=Path(plan['receipt'])
            if receipt.is_file():
                data=json.loads(receipt.read_text())
                if data.get('status')!='completed' or data.get('stage')!='primary_long':raise ValueError('Invalid long-stage receipt')
                break
            if time.monotonic()-began>plan['max_wait_seconds']:raise RuntimeError('Wait budget exhausted')
            time.sleep(30)
        model_output=output/'review';frozen=freeze(plan['queue'],plan['receipt'],model_output,plan['model'],plan['model_digest'],plan['max_scheduled_calls'],plan['max_physical_calls'],plan['max_execution_seconds'])
        save(status='running',planned_calls=frozen['planned_calls'])
        result=asyncio.run(judge(model_output,ROOT/'.env.primary'))
        save(status='completed',machine_reviewed_samples=result['machine_advisory_completed_rows'],unreviewed_samples=result['unreviewed_rows'])
    except BaseException as exc:save(status='stopped',error_type=type(exc).__name__);raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('prepare');q.add_argument('--out',type=Path,required=True);q.add_argument('--receipt',type=Path,required=True);q.add_argument('--queue',type=Path,required=True);q.add_argument('--digest',required=True)
    r=sub.add_parser('run');r.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.command=='prepare':prepare(a.out,a.receipt,a.queue,a.digest);print('Registered bounded local semantic quality review after long-run finalization.')
    else:run(a.out)
