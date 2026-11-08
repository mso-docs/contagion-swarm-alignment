"""Verify administrative primary-capacity release without completing an old study."""
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import math
from pathlib import Path
import time

from contagion.config import digest
from contagion.storage import verify
from run_pilot import ROOT


ACTIVE={'waiting','running','cooling','waiting_for_primary_lease'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc():return datetime.now(timezone.utc).isoformat()


def read(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError('Missing or unsafe allocation artifact')
    return json.loads(path.read_text())


def private_write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(data,stream,indent=2,sort_keys=True);stream.write('\n')
    path.chmod(0o600)


def _plan(queue):
    from primary_long_queue import validate_plan
    return validate_plan(queue)


def inspect(queue,source=None):
    """Read raw counters/seals, not model quality or a guessed failure message."""
    queue=Path(queue);plan=_plan(queue);state_path=queue/'primary-long-state.json'
    state=read(state_path) if state_path.exists() else {'status':'waiting'}
    if state.get('plan_hash',plan['plan_hash'])!=plan['plan_hash']:raise ValueError('Old state/plan mismatch')
    source=Path(source) if source else ROOT/'results/repository-runs'/queue.name
    jobs=plan['jobs'];complete={};budget_attempts=[];bad=[];unsealed=0;physical=returned=0
    for directory in sorted(source.glob('job-*/*')):
        if not directory.is_dir():continue
        if directory.is_symlink() or directory.parent.is_symlink():raise ValueError('Unexpected old allocation symlink')
        if not (directory/'events.jsonl').is_file():unsealed+=1
    for path in sorted(source.glob('job-*/*/events.jsonl')):
        root=path.parent;job_name=root.parent.name
        try:index=int(job_name.removeprefix('job-'));job=jobs[index]
        except (ValueError,IndexError):raise ValueError('Unexpected old allocation job') from None
        if index<0 or job_name!=f'job-{index:03}':raise ValueError('Unexpected old allocation index')
        if any(p.is_symlink() for p in [root,root.parent,path]):raise ValueError('Unexpected old allocation symlink')
        events=[];tail=False
        for line in path.read_text().splitlines():
            try:events.append(json.loads(line))
            except ValueError:tail=True;break
        attempts=sum(e.get('event_type')=='http_attempt' for e in events)
        responses=sum(e.get('event_type')=='inference_response' for e in events)
        physical+=attempts;returned+=responses
        if not all((root/name).is_file() for name in ['manifest.json','checksum.sha256','config.snapshot.json','outcome.json']):
            unsealed+=1;continue
        if tail or not verify(root):raise ValueError('Old allocation seal or event integrity failed')
        m=read(root/'manifest.json');c=read(root/'config.snapshot.json');identity=m.get('model_identity',{})
        if (m.get('protocol_version')!='3.3-repository-safeguard' or c.get('protocol_version')!=m['protocol_version'] or
            m.get('plan_hash')!=plan['plan_hash'] or c.get('registry_freeze_hash')!=plan['plan_hash'] or
            m.get('source_hash')!=plan['source_hash'] or c.get('source_hash')!=plan['source_hash'] or
            m.get('source_unchanged_on_exit') is not True):raise ValueError('Old attempt provenance mismatch')
        if (identity.get('backend')!='ollama' or identity.get('model')!=plan['model'] or
            identity.get('digest')!=plan['model_digest'] or identity.get('worker_label')!='primary'):
            raise ValueError('Only the pinned real primary allocation can release capacity')
        if any(c.get(k)!=job[k] for k in ['rounds','topology','seed','defense','intervention','phase','task_id']):
            raise ValueError('Old attempt does not match registered job')
        if (m.get('completed_model_calls')!=responses or m.get('http_attempts')!=attempts or
            m.get('parse_failures')!=0 or attempts!=responses or not 0<=responses<=job['calls']):
            raise ValueError('Old attempt counters/parse gate failed')
        artifacts=[e for e in events if e.get('event_type')=='artifact']
        expected=[(f'agent_{a}',r) for r in range(job['rounds']) for a in range(5)]
        actual=[(e.get('agent_id'),e.get('round')) for e in artifacts]
        if actual!=expected[:responses] or len(artifacts)!=responses:raise ValueError('Old artifact coverage failed')
        finishes=[e for e in events if e.get('event_type')=='run_finished']
        if len(finishes)!=1 or finishes[-1]!=events[-1] or finishes[0].get('metadata',{}).get('status')!=m['status']:
            raise ValueError('Old finish record mismatch')
        if m['status']=='completed':
            if responses!=job['calls'] or index in complete:raise ValueError('Duplicate/incomplete old completed job')
            complete[index]=sha(root/'checksum.sha256')
        elif m['status']=='budget_exhausted' and m.get('failure')=='CallBudgetExhausted':
            budget_attempts.append((index,sha(root/'checksum.sha256')))
        else:bad.append(index)
    elapsed=state.get('execution_seconds',0)
    if type(elapsed) not in {float,int} or not math.isfinite(elapsed) or elapsed<0:raise ValueError('Invalid old execution ledger')
    if physical>plan['max_http_attempts']:raise ValueError('Old physical budget exceeded')
    terminal=state['status'] not in ACTIVE
    if terminal:
        if (state.get('completed_runs')!=len(complete) or state.get('physical_calls')!=physical or
            state.get('returned_calls')!=returned or state.get('failed_runs')!=len(budget_attempts)+len(bad)+unsealed):
            raise ValueError('Terminal old allocation ledger mismatch')
    prefix=set(complete)==set(range(len(complete)))
    result={'schema_version':'primary-allocation-inspection-1.0','old_plan_hash':plan['plan_hash'],
            'old_state_sha256':sha(state_path) if state_path.exists() else None,'old_status':state['status'],
            'planned_runs':plan['planned_runs'],'completed_runs':len(complete),'budget_exhausted_attempts':len(budget_attempts),
            'other_failed_attempts':len(bad),'unsealed_attempts':unsealed,'physical_calls':physical,'returned_calls':returned,
            'execution_seconds':elapsed,'registered_wall_seconds':plan['max_wall_seconds'],
            'source_seals_hash':digest({'completed':complete,'budget':budget_attempts}),'release_kind':None,
            'study_complete':False,'eligible':False,'reason':'allocation_active' if not terminal else 'review_required'}
    if not terminal:return result
    if bad or unsealed or not prefix or len(budget_attempts)>1:return result
    if state['status']=='completed' and len(complete)==plan['planned_runs'] and not budget_attempts:
        result.update(eligible=True,study_complete=True,release_kind='completed',reason='all_registered_jobs_complete')
    elif (state['status']=='stopped' and len(complete)<plan['planned_runs'] and elapsed>=plan['max_wall_seconds'] and
          (not budget_attempts or budget_attempts[0][0]==len(complete))):
        result.update(eligible=True,release_kind='expired_sealed_allocation',reason='expired_ledger_and_sealed_prefix')
    return result


def release(queue,out,source=None):
    """Mint a fresh receipt while the shared primary lease is observed free."""
    out=Path(out)
    if (ROOT/'results').resolve() not in out.resolve().parents:raise ValueError('Release receipt stays under ignored results')
    lock=ROOT/'results/checkpoint-gates/controller-primary.lock';lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open('a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        check=inspect(queue,source)
        if not check['eligible']:raise ValueError('Old allocation is not eligible for administrative release')
        data={'schema_version':'primary-allocation-release-1.0','status':'allocation_released',
              'scope':'administrative_capacity_release_not_study_completion','created_utc':utc(),
              'lease_observed_free':True,'inspection':check,'release_kind':check['release_kind'],
              'old_study_complete':check['study_complete'],'script_sha256':sha(__file__)}
        data['receipt_id']=digest(data);private_write(out,data)
    return data


def validate_receipt(queue,receipt,source=None):
    data=read(receipt)
    if (set(data)!={'schema_version','status','scope','created_utc','lease_observed_free','inspection','release_kind','old_study_complete','script_sha256','receipt_id'} or
        data['schema_version']!='primary-allocation-release-1.0' or data['status']!='allocation_released' or
        data['scope']!='administrative_capacity_release_not_study_completion' or data['lease_observed_free'] is not True or
        data['script_sha256']!=sha(__file__) or digest({k:v for k,v in data.items() if k!='receipt_id'})!=data['receipt_id']):
        raise ValueError('Invalid administrative release receipt')
    current=inspect(queue,source)
    if not current['eligible'] or current!=data['inspection'] or data['release_kind']!=current['release_kind'] or data['old_study_complete']!=current['study_complete']:
        raise ValueError('Old allocation changed after release or receipt interpretation mismatch')
    return data


def prepare(root,queue,max_wait_hours=24):
    root=Path(root);queue=Path(queue).resolve()
    if (ROOT/'results').resolve() not in root.resolve().parents:raise ValueError('Administrative watcher stays under ignored results')
    if not 1<=max_wait_hours<=48:raise ValueError('Bound administrative wait to1..48hours')
    old=_plan(queue)
    plan={'schema_version':'primary-release-watch-1.0','queue':str(queue),'old_plan_hash':old['plan_hash'],
          'max_wait_seconds':max_wait_hours*3600,'script_sha256':sha(__file__),'created_utc':utc()}
    plan['plan_hash']=digest(plan);root.mkdir(parents=True,exist_ok=False);private_write(root/'release-watch-plan.private.json',plan)
    return plan


def run(root):
    root=Path(root);plan=read(root/'release-watch-plan.private.json')
    if digest({k:v for k,v in plan.items() if k!='plan_hash'})!=plan['plan_hash'] or sha(__file__)!=plan['script_sha256']:
        raise ValueError('Registered release watcher changed')
    state_path=root/'allocation-release-state.json'
    lease=(root/'watch.lock').open('a');fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if state_path.exists():lease.close();raise ValueError('No implicit watcher restart; preserve original registration')
    state={'scope':'administrative_allocation_release','status':'waiting','old_plan_hash':plan['old_plan_hash'],'model_calls':0}
    def save(**kw):
        state.update(kw,updated_utc=utc());temporary=state_path.with_suffix('.tmp');temporary.write_text(json.dumps(state,indent=2)+'\n');temporary.chmod(0o600);temporary.replace(state_path)
    start=time.monotonic();save()
    try:
        while True:
            if (root/'STOP').exists():raise RuntimeError('Administrative watcher operator stop')
            check=inspect(plan['queue'])
            if check['old_plan_hash']!=plan['old_plan_hash']:raise ValueError('Old allocation registration changed')
            if check['eligible']:
                try:receipt=release(plan['queue'],root/'release.private.json')
                except BlockingIOError:save(status='waiting_for_primary_lease');time.sleep(15);continue
                save(status='completed',receipt_id=receipt['receipt_id'],release_kind=receipt['release_kind'],
                     old_status=check['old_status'],old_completed_runs=check['completed_runs'],old_study_complete=check['study_complete']);return state
            if check['old_status'] not in ACTIVE:raise RuntimeError('Old allocation stopped outside safe release criteria')
            if time.monotonic()-start>=plan['max_wait_seconds']:raise RuntimeError('Administrative wait budget exhausted')
            save(status='waiting',old_status=check['old_status'],old_completed_runs=check['completed_runs']);time.sleep(15)
    except BaseException as exc:save(status='stopped',error_type=type(exc).__name__);raise
    finally:lease.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--root',type=Path,required=True);p.add_argument('--queue',type=Path,required=True);p.add_argument('--max-wait-hours',type=int,default=24)
    r=sub.add_parser('run');r.add_argument('--root',type=Path,required=True)
    i=sub.add_parser('inspect');i.add_argument('--queue',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='prepare':prepare(args.root,args.queue,args.max_wait_hours);print('Registered bounded administrative release watcher; zero model calls.')
    elif args.command=='run':run(args.root);print('Administrative capacity released; old study status is preserved.')
    else:
        result=inspect(args.queue);print(json.dumps(result,indent=2))
