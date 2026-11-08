"""Explicit secondary recovery; preserve original supervisor and attempt records."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from contagion.storage import source_fingerprint
from run_campaign import atomic,utc
from run_pilot import ROOT


def run(campaign,recovery):
    campaign=Path(campaign).resolve();recovery=Path(recovery).resolve()
    record=json.loads((campaign/'campaign.json').read_text())
    if record['source_hash']!=source_fingerprint():raise ValueError('Original frozen source changed')
    recovery.mkdir(parents=True,exist_ok=False)
    state={'status':'running','phase':'explicit_recovery','started_utc':utc(),'original_campaign_hash':record['campaign_hash'],
           'reason':'Cloud-only dotenv assignment isolated; previous zero-call attempt retained.','budget_policy':'Original physical-call and wall budgets remain in force.'}
    atomic(recovery/'overnight.json',state)
    try:
        with (recovery/'recovery.private.log').open('x') as log:
            subprocess.run([sys.executable,'scripts/run_campaign.py','run','--root',str(campaign),'--env-file',str(ROOT/'.env.secondary'),
                            '--ssh-env-file',str(ROOT/'.env'),'--retry-incomplete'],cwd=ROOT,stdout=log,stderr=log,check=True,timeout=record['max_wall_seconds'])
        final=json.loads((campaign/'state.json').read_text())
        if final['status']!='completed':raise ValueError('Recovered campaign did not complete')
        state.update(status='completed',phase='complete',completed_runs=final['completed_runs'],retained_failed_attempts=final['failed_runs'],updated_utc=utc())
        atomic(recovery/'overnight.json',state)
    except BaseException as exc:
        state.update(status='stopped',error_type=type(exc).__name__,updated_utc=utc());atomic(recovery/'overnight.json',state);raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--campaign',type=Path,required=True);p.add_argument('--recovery',type=Path,required=True);a=p.parse_args();run(a.campaign,a.recovery)
