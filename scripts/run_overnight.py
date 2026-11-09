#!/usr/bin/env python3
"""Sequential repository checkpoints then one bounded, frozen secondary campaign."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from contagion.config import digest
from contagion.storage import source_fingerprint
from run_campaign import atomic,utc,validate_readiness
from run_pilot import ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--repository-freeze',type=Path,required=True)
    parser.add_argument('--catalog',type=Path,required=True)
    parser.add_argument('--readiness',type=Path,required=True)
    args=parser.parse_args();root=args.root
    if (root/'overnight.json').exists():raise ValueError('Use a fresh supervisor root; previous attempts are immutable')
    campaign=json.loads((root/'campaign.json').read_text());proof=validate_readiness(args.readiness)
    if campaign['provider']!='ollama' or campaign['readiness_hash']!=proof['readiness_hash'] or campaign['source_hash']!=source_fingerprint():
        raise ValueError('Overnight freeze/readiness mismatch')
    freeze=json.loads(args.repository_freeze.read_text())
    if digest({k:v for k,v in freeze.items() if k!='freeze_hash'})!=freeze['freeze_hash']:
        # Repository freeze uses its separately registered JSON hash encoding.
        from repository_benchmark import sha
        if sha(json.dumps({k:v for k,v in freeze.items() if k!='freeze_hash'},sort_keys=True).encode())!=freeze['freeze_hash']:
            raise ValueError('Repository freeze changed')
    state={'status':'starting','started_utc':utc(),'pid':os.getpid(),'completed_checkpoints':[],
           'planned_repository_calls':260,'planned_campaign_calls':campaign['planned_calls']}
    def save(**values):state.update(values,updated_utc=utc());atomic(root/'overnight.json',state)
    def checkpoint():
        if (root/'STOP').exists():raise RuntimeError('Operator stop')
        if source_fingerprint()!=campaign['source_hash']:raise RuntimeError('Source changed')
    def execute(command,label,timeout):
        checkpoint();save(status='running',phase=label)
        with (root/(label+'.private.log')).open('x') as log:
            subprocess.run([sys.executable,*command],cwd=ROOT,stdout=log,stderr=log,timeout=timeout,check=True)
        state['completed_checkpoints'].append(label);save()
    try:
        # Fail closed on a repeated supervisor invocation; prior child attempts stay intact.
        for size in ['short','medium','long']:
            task=next(row for row in freeze['tasks'] if row['input_length']==size)
            execute(['scripts/run_repository_study.py','--freeze',str(args.repository_freeze),'--catalog',str(args.catalog),
                     '--task-id',task['id'],'--out',str(ROOT/'results/repository-runs'/root.name/size),
                     '--provider','ollama','--readiness',str(args.readiness),'--max-calls','150','--stop-file',str(root/'STOP')],
                    'repository-'+size,7200)
        execute(['scripts/run_campaign.py','run','--root',str(root)],'synthetic-campaign',campaign['max_wall_seconds']+300)
        execute(['scripts/research_report.py','--out',str(ROOT/'results/reports'/root.name)],'report',600)
        save(status='completed',phase='complete')
    except BaseException as exc:
        save(status='stopped',error_type=type(exc).__name__)
        raise


if __name__=='__main__':
    try:main()
    except Exception as exc:sys.exit(f'Overnight stopped ({type(exc).__name__}); private logs and completed attempts retained.')
