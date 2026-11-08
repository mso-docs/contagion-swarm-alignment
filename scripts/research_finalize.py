"""Offline completion sidecar for registered research stages; no model calls or deployment."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import time

from contagion.config import digest
from contagion.storage import source_fingerprint,verify
from run_campaign import atomic,utc
from run_pilot import ROOT

DEPENDENCIES=('research_finalize.py','analyze_confirmatory.py','followup_monitor.py','triage_reviews.py',
              'build_review_workspace.py','judge_artifact_queue.py','analyze_primary_long.py','repository_quality.py')
TERMINAL={'completed','blocked'}
SOURCE_FAILURES={'failed','stopped','budget_exhausted','blocked'}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def private_path(base,path):
    base=Path(base).resolve();path=Path(path)
    if (base/'results').resolve() not in path.resolve().parents:raise ValueError('Finalizer paths must remain in ignored results')
    if path.is_symlink() or any(p.is_symlink() for p in path.parents if p!=base):raise ValueError('Finalizer source/output symlink rejected')
    return path


def script_hashes():
    files=[*(ROOT/'scripts'/name for name in DEPENDENCIES),ROOT/'review_workspace/review.js',ROOT/'review_workspace/style.css',ROOT/'docs/FOLLOWUP_MONITOR_PROTOCOL.md']
    return {str(p.relative_to(ROOT)):sha(p) for p in files}


def registry(base):
    base=Path(base).resolve();campaign=base/'results/campaigns/primary-confirmatory-v4-20261108';judge=base/'results/reviews/primary-artifact-judge-v2';long=base/'results/campaigns/primary-long-safeguard-v33-20261108'
    return [
        {'id':'primary_rq1','readiness':str(campaign/'rq1/completion.json'),'failure_state':str(campaign/'followup-state.json'),
         'sources':[str(campaign/'rq1/plan.json')],'raw':str(campaign/'rq1'),
         'outputs':[str(campaign/'rq1-analysis-finalized.private.json'),str(base/'results/monitors/primary-protocol4-patch-v1')],
         'operations':['analyze_confirmatory','followup_monitor']},
        {'id':'advisory_triage','readiness':str(judge/'queue-state.json'),'failure_state':str(judge/'queue-state.json'),
         'sources':[str(judge/'review/judge-results.private.json'),str(base/'results/reviews/compact-artifact-audit-v1/review_inputs.json'),str(base/'results/reviews/compact-artifact-audit-v1/oracle_labels.private.json'),str(base/'results/reviews/frontier-spotcheck-v2/frontier-results.private.json')],
         'outputs':[str(base/'results/reviews/workspaces/triage')],'operations':['triage_reviews_limit16']},
        {'id':'primary_long','readiness':str(long/'primary-long-state.json'),'failure_state':str(long/'primary-long-state.json'),
         'sources':[str(long/'primary-long-plan.json'),str(base/'results/benchmarks/martian-pinned-v2/catalog.json')],
         'raw':str(base/'results/repository-runs/primary-long-safeguard-v33-20261108'),
         'outputs':[str(long/'long-analysis-finalized.private.json'),str(base/'results/reviews/workspaces/quality-long')],
         'operations':['analyze_primary_long','repository_quality_one_agent64_7MiB','build_repository_workspace']},
    ]


def prepare(directory,project_root=ROOT,max_wait_seconds=24*3600,poll_seconds=15):
    if not 1<=max_wait_seconds<=24*3600 or not 1<=poll_seconds<=30:raise ValueError('Finalizer wait/poll cap exceeded')
    base=Path(project_root).resolve();directory=private_path(base,Path(directory).resolve());directory.mkdir(parents=True,exist_ok=False)
    stages=registry(base)
    registered_sources=[Path(p) for stage in stages for p in stage['sources'] if Path(p).is_file()]
    plan={'schema_version':'research-finalizer-1.0','created_utc':utc(),'project_root':str(base),'stages':stages,
          'immutable_source_sha256_at_registration':fingerprint(registered_sources,base),
          'output_sha256_policy':'Generated immutable output hashes and completed source hashes are required in per-stage receipts before reuse.',
          'script_sha256':script_hashes(),'core_source_hash':source_fingerprint(),'max_wait_seconds':max_wait_seconds,'poll_seconds':poll_seconds,
          'claims':'Offline derivation and blank human-review workspaces only; no model inference, public publication or automatic paper freeze.'}
    plan['plan_hash']=digest(plan);atomic(directory/'finalizer-plan.private.json',plan);return plan


def validate_plan(directory):
    plan=json.loads((Path(directory)/'finalizer-plan.private.json').read_text())
    if digest({k:v for k,v in plan.items() if k!='plan_hash'})!=plan['plan_hash']:raise ValueError('Finalizer plan changed')
    if plan['stages']!=registry(plan['project_root']):raise ValueError('Only registered fixed stages may execute')
    if plan['script_sha256']!=script_hashes() or plan['core_source_hash']!=source_fingerprint():raise ValueError('Finalizer implementation changed; review a new plan')
    return plan


def readiness(stage):
    path=Path(stage['readiness'])
    if path.is_file():
        state=json.loads(path.read_text())
        if state.get('status')=='completed':return 'ready'
        if state.get('status') in SOURCE_FAILURES:return 'blocked'
    fallback=Path(stage['failure_state'])
    if fallback.is_file() and json.loads(fallback.read_text()).get('status') in SOURCE_FAILURES:return 'blocked'
    return 'waiting'


def source_files(stage,base):
    files=[Path(stage['readiness']),*(Path(p) for p in stage['sources'])]
    raw=Path(stage['raw']) if 'raw' in stage else None
    if raw:
        directories=sorted(raw.glob('run-*')) if stage['id']=='primary_rq1' else sorted(raw.glob('job-*/*'))
        for root in directories:
            if not root.is_dir():continue
            private_path(base,root)
            sealed=(root/'checksum.sha256').is_file()
            if sealed and not verify(root):raise ValueError('Completed source seal invalid')
            if stage['id']=='primary_rq1' and not sealed:raise ValueError('RQ1 source is not sealed')
            # Long queues preserve interrupted tails; hash every existing standard file.
            files.extend(root/name for name in ['manifest.json','config.snapshot.json','events.jsonl','outcome.json','checksum.sha256'] if (root/name).is_file())
    if stage['id']=='primary_long':
        catalog=Path(stage['sources'][1]);data=json.loads(catalog.read_text())
        for row in data['tasks']:
            for field in ['diff_file','oracle_file']:
                if field in row:
                    reference=Path(row[field])
                    if reference.name!=str(reference):raise ValueError('Unsafe catalog source reference')
                    files.append(catalog.parent/'private'/reference)
    for path in files:
        private_path(base,path)
        if not path.is_file():raise ValueError('Completed stage source is missing')
    return sorted(set(files))


def fingerprint(files,base):return {str(private_path(base,p).resolve().relative_to(Path(base).resolve())):sha(p) for p in files}


def output_files(stage,base):
    immutable=[];mutable=[]
    for name in stage['outputs']:
        path=private_path(base,Path(name))
        if not path.exists():raise ValueError('Stage output missing')
        files=[path] if path.is_file() else sorted(p for p in path.rglob('*') if p.is_file())
        if not files:raise ValueError('Empty stage output')
        for p in files:
            private_path(base,p)
            (mutable if p.name in {'human_labels.csv','human_quality.csv','sample_confirmations.csv'} else immutable).append(p)
    return immutable,mutable


def execute_stage(stage,base):
    # Deliberately fixed Python calls, never shell/eval or model-generated command text.
    if stage['id']=='primary_rq1':
        from analyze_confirmatory import analyze
        from followup_monitor import evaluate
        from contagion.storage import write_json
        result=analyze(stage['raw']);write_json(Path(stage['outputs'][0]),result)
        monitored=evaluate(stage['raw'],stage['outputs'][1])
        return {'completed_runs':result['completed'],'treatment_pairs':len(result['pairs']),'monitor_trajectories':monitored['trajectory_count'],
                'monitor_observations':monitored['observation_count'],'human_validation':'pending','paper_freeze':'not_changed'}
    if stage['id']=='advisory_triage':
        from triage_reviews import triage
        result=triage(Path(base)/'results/reviews/compact-artifact-audit-v1',stage['sources'][0],stage['outputs'][0],limit=16,root=base,second_judge=stage['sources'][3])
        return {'machine_reviewed_samples':result['machine_reviewed_samples'],'human_selected_samples':result['human_selected_samples'],
                'human_labels_generated':0,'human_validation':'pending','paper_freeze':'not_changed'}
    if stage['id']=='primary_long':
        from analyze_primary_long import analyze
        from repository_quality import prepare as prepare_quality
        from build_review_workspace import build
        from contagion.storage import write_json
        queue=Path(stage['readiness']).parent;result=analyze(queue,stage['raw']);write_json(Path(stage['outputs'][0]),result)
        samples=prepare_quality(stage['raw'],stage['sources'][1],stage['outputs'][1],max_samples=64,one_agent_per_run=True,max_bytes=7*1024*1024)
        if samples:build(stage['outputs'][1],Path(stage['outputs'][1])/'repository-quality.html',kind='repository',root=base)
        return {'evaluation_runs':result['evaluation_runs'],'case_clusters':result['case_clusters'],'project_clusters':result['project_clusters'],
                'quality_review_samples':samples,'quality_status':'awaiting_human_adjudication','human_labels_generated':0,'paper_freeze':'not_changed'}
    raise ValueError('Unregistered operation')


def verify_receipt(directory,stage,plan):
    receipt_path=Path(directory)/(stage['id']+'.receipt.private.json')
    if not receipt_path.is_file():raise ValueError('Existing outputs have no completed receipt')
    receipt=json.loads(receipt_path.read_text());base=plan['project_root']
    if receipt.get('status')!='completed' or receipt.get('plan_hash')!=plan['plan_hash'] or receipt.get('script_sha256')!=plan['script_sha256']:raise ValueError('Stage receipt mismatch')
    if receipt['source_sha256']!=fingerprint(source_files(stage,base),base):raise ValueError('Stage sources changed after completion')
    immutable,_=output_files(stage,base)
    if receipt['output_sha256']!=fingerprint(immutable,base):raise ValueError('Completed immutable stage outputs changed')
    # Human CSVs may legitimately change; initial hashes are provenance, not a ban on review.
    return receipt


def run(directory,now=time.time,sleep=time.sleep):
    directory=Path(directory);plan=validate_plan(directory);base=plan['project_root']
    with (directory/'finalizer.lock').open('a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state_path=directory/'finalizer-state.private.json'
        state=json.loads(state_path.read_text()) if state_path.exists() else {'plan_hash':plan['plan_hash'],'started_epoch':now(),'stages':{s['id']:{'status':'waiting'} for s in plan['stages']}}
        if state['plan_hash']!=plan['plan_hash']:raise ValueError('State belongs to another finalizer plan')
        # Every reuse after restart revalidates immutable inputs and outputs.
        for stage in plan['stages']:
            current=state['stages'][stage['id']]
            if current['status']=='completed':
                try:verify_receipt(directory,stage,plan)
                except (ValueError,OSError,KeyError):current.update(status='blocked',reason='completed_receipt_validation_failed')
        def save():state.update(updated_utc=utc());atomic(state_path,state)
        while True:
            validate_plan(directory)
            if all(s['status'] in TERMINAL for s in state['stages'].values()):
                state['status']='completed' if all(s['status']=='completed' for s in state['stages'].values()) else 'completed_with_blockers';save();return state
            if now()-state['started_epoch']>=plan['max_wait_seconds']:
                for current in state['stages'].values():
                    if current['status'] not in TERMINAL:current.update(status='blocked',reason='wait_budget_exhausted')
                state['status']='completed_with_blockers';save();return state
            for stage in plan['stages']:
                current=state['stages'][stage['id']]
                if current['status'] in TERMINAL:continue
                if (directory/'STOP').exists():current.update(status='blocked',reason='operator_stop');save();continue
                try:status=readiness(stage)
                except (ValueError,OSError,KeyError,TypeError):
                    current.update(status='blocked',reason='invalid_source_state');save();continue
                if status=='blocked':current.update(status='blocked',reason='source_stopped_or_failed');save();continue
                if status=='waiting':continue
                try:
                    receipt=directory/(stage['id']+'.receipt.private.json')
                    if receipt.exists():
                        verified=verify_receipt(directory,stage,plan);current.update(status='completed',stats=verified['stats']);save();continue
                    if any(Path(p).exists() for p in stage['outputs']):raise ValueError('Unreceipted output exists; preserving it for review')
                    before=fingerprint(source_files(stage,base),base)
                    registered=plan['immutable_source_sha256_at_registration']
                    if any(key in registered and registered[key]!=value for key,value in before.items()):raise ValueError('Registered immutable input changed')
                    current.update(status='running');save();stats=execute_stage(stage,base)
                    if before!=fingerprint(source_files(stage,base),base):raise ValueError('Source changed during finalization')
                    immutable,mutable=output_files(stage,base)
                    completed={'schema_version':'research-stage-receipt-1.0','status':'completed','stage':stage['id'],'completed_utc':utc(),'plan_hash':plan['plan_hash'],
                               'source_sha256':before,'output_sha256':fingerprint(immutable,base),'initial_human_csv_sha256':fingerprint(mutable,base),
                               'script_sha256':plan['script_sha256'],'stats':stats}
                    atomic(receipt,completed);current.update(status='completed',stats=stats);save()
                except Exception as exc:
                    current.update(status='blocked',reason='offline_stage_validation_failed',error_type=type(exc).__name__);save()
            if all(s['status'] in TERMINAL for s in state['stages'].values()):
                state['status']='completed' if all(s['status']=='completed' for s in state['stages'].values()) else 'completed_with_blockers';save();return state
            if now()-state['started_epoch']>=plan['max_wait_seconds']:
                for current in state['stages'].values():
                    if current['status'] not in TERMINAL:current.update(status='blocked',reason='wait_budget_exhausted')
                state['status']='completed_with_blockers';save();return state
            state['status']='waiting';save();sleep(plan['poll_seconds'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('prepare');q.add_argument('--root',type=Path,required=True);q.add_argument('--max-wait-seconds',type=int,default=24*3600);q.add_argument('--poll-seconds',type=int,default=15)
    r=sub.add_parser('run');r.add_argument('--root',type=Path,required=True);a=p.parse_args()
    if a.command=='prepare':prepare(a.root,max_wait_seconds=a.max_wait_seconds,poll_seconds=a.poll_seconds);print('Registered3offline completion stages; no inference or publication.')
    else:
        result=run(a.root);print('Offline finalizer:',result['status'],'; human review and paper freeze remain separate.')
        if result['status']!='completed':raise SystemExit(1)
