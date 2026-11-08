"""Frozen, resumable primary-only long-review safeguard experiment.

Waits for the existing allocation to finish. Never changes Ollama services,
credentials, firewall, or secondary work; model contexts have no tools.
"""
import argparse
import asyncio
import fcntl
import itertools
import json
from pathlib import Path
import random
import shutil
import time
from urllib.parse import urlsplit

from contagion.config import digest
from contagion.storage import source_fingerprint,verify
from primary_repository_runner import AttributedMock,run_case
from repository_benchmark import sha
from run_campaign import atomic,utc,resource_reason,cooling_required,cooled,validate_readiness
from run_pilot import ROOT,load_env
from run_repository_study import RepositoryProvider

DEPENDENCIES=('primary_long_queue.py','primary_repository_runner.py','run_repository_study.py','repository_benchmark.py','run_campaign.py','run_pilot.py','remote_worker.py')


def dependency_hashes():return {name:sha((ROOT/'scripts'/name).read_bytes()) for name in DEPENDENCIES}


def prepare(root,catalog,model,model_digest,after,readiness=None,case_count=8,seeds=(21001,21002),max_http_attempts=5200,max_hours=8):
    root=Path(root);catalog=Path(catalog).resolve()
    if root.exists():raise ValueError('Use a new queue directory')
    if not 1<=case_count<=8 or len(set(seeds))!=len(seeds) or not seeds or any(type(s)is not int or s<10000 for s in seeds):raise ValueError('Invalid case/seed schedule')
    if not model or not isinstance(model_digest,str) or len(model_digest)!=64 or any(c not in '0123456789abcdef' for c in model_digest):raise ValueError('Pin the discovered model digest')
    if not 1<=max_hours<=12:raise ValueError('Wall budget must be1..12hours')
    data=json.loads(catalog.read_text())
    if sha(json.dumps({k:v for k,v in data.items() if k!='catalog_hash'},sort_keys=True).encode())!=data['catalog_hash']:raise ValueError('Catalog hash changed')
    long=sorted((r for r in data['tasks'] if r['input_length']=='long'),key=lambda r:r['id'])
    short=sorted((r for r in data['tasks'] if r['input_length']=='short'),key=lambda r:r['id'])
    if len(long)<case_count or not short:raise ValueError('Need requested independent long cases and a short integration case')
    random.Random(6142).shuffle(long);cases=long[:case_count];checkpoint=short[0]
    for row in [*cases,checkpoint]:
        if Path(row['diff_file']).name!=row['diff_file']:raise ValueError('Unsafe source reference')
        path=catalog.parent/'private'/row['diff_file']
        if path.is_symlink() or sha(path.read_bytes())!=row['diff_sha256']:raise ValueError('Pinned diff integrity failed')
    proof=validate_readiness(readiness) if readiness else None
    if proof and (proof['model']!=model or proof['model_digest']!=model_digest):raise ValueError('Readiness applies to a different model')
    jobs=[]
    for phase,task_rows,rounds,phase_seeds in [('integration_precheck',[checkpoint],3,[2718]),('evaluation',cases,15,seeds)]:
        blocks=list(itertools.product(task_rows,phase_seeds));random.Random(271828).shuffle(blocks)
        for row,seed in blocks:
            conditions=list(itertools.product(['plain','source_attribution'],['none','benign_override']))
            random.Random(seed+int(row['id'][:8],16)).shuffle(conditions)
            for defense,intervention in conditions:
                job={'task_id':row['id'],'rounds':rounds,'topology':'ring','seed':seed,'defense':defense,'intervention':intervention,
                     'phase':phase,'calls':rounds*5}
                job['id']=digest(job)[:16];jobs.append(job)
    planned=sum(j['calls'] for j in jobs)
    if not planned<=max_http_attempts<=6000:raise ValueError('Physical-call cap must cover schedule and stay at most6000')
    dependencies=dependency_hashes()
    plan={'schema_version':'primary-long-safeguard-1.0','protocol_version':'3.3-repository-safeguard','created_utc':utc(),
          'worker':'primary','model':model,'model_digest':model_digest,'source_hash':source_fingerprint(),'dependencies':dependencies,
          'catalog':str(catalog),'catalog_hash':data['catalog_hash'],'tasks':[checkpoint,*cases],'selection_seed':6142,'jobs':jobs,
          'after':str(Path(after).resolve()) if after else None,'readiness':str(Path(readiness).resolve()) if readiness else None,
          'readiness_hash':proof['readiness_hash'] if proof else None,'planned_runs':len(jobs),'planned_calls':planned,
          'max_http_attempts':max_http_attempts,'max_wall_seconds':max_hours*3600,'max_wait_seconds':24*3600,'max_run_seconds':3600,
          'context_tokens':32768,'max_output_tokens':1536,'maximum_history_bytes':96000,
          'limitations':['Static review; upstream code and tests are never executed.','Two seeds per task and conditions share inputs; cluster by task and account for project-level overlap.',
                         'This phase fixes ring topology; it cannot estimate topology effects.','The safeguard bundles formatting, controller provenance and a boundary reminder; its components are not causally isolated. Source attribution changes prompt/content length; equal token ceilings do not equalize realized usage.',
                         'Quality requires blinded golden-based adjudication; boundary scores alone are not task utility or general alignment.',
                         'Preexisting public diffs may have appeared in training data.','No collusion or original-model neural mechanism is inferred from these logs.']}
    plan['plan_hash']=digest(plan)
    root.mkdir(parents=True);archive=root/'controller';archive.mkdir()
    for name in dependencies:shutil.copyfile(ROOT/'scripts'/name,archive/name)
    atomic(root/'primary-long-plan.json',plan)
    return plan


def validate_plan(root):
    root=Path(root);plan=json.loads((root/'primary-long-plan.json').read_text())
    if digest({k:v for k,v in plan.items() if k!='plan_hash'})!=plan['plan_hash']:raise ValueError('Queue plan changed')
    if plan['source_hash']!=source_fingerprint():raise ValueError('Frozen core changed')
    for name,want in plan['dependencies'].items():
        if Path(name).name!=name or sha((root/'controller'/name).read_bytes())!=want:raise ValueError('Archived controller changed')
    # Imported functions must match the freeze too; no silent execution of newer helpers.
    if dependency_hashes()!=plan['dependencies']:raise ValueError('Installed queue/helpers differ from freeze; review and register a new release')
    return plan


def load_payload(plan,job):
    catalog=Path(plan['catalog']);data=json.loads(catalog.read_text())
    if sha(json.dumps({k:v for k,v in data.items() if k!='catalog_hash'},sort_keys=True).encode())!=plan['catalog_hash']:raise ValueError('Catalog changed')
    row=next(r for r in plan['tasks'] if r['id']==job['task_id'])
    path=catalog.parent/'private'/row['diff_file']
    if path.is_symlink() or sha(path.read_bytes())!=row['diff_sha256']:raise ValueError('Diff changed')
    return row,{'task_id':row['id'],'repository':row['repository'],'code_diff':path.read_text()}


def recover(output):
    completed={};failed=physical=returned=0
    for path in sorted(Path(output).glob('job-*/*/events.jsonl')):
        events=[]
        for line in path.read_text().splitlines():
            try:events.append(json.loads(line))
            except ValueError:break  # Preserve an interrupted, unsealed tail verbatim.
        physical+=sum(e.get('event_type')=='http_attempt' for e in events)
        returned+=sum(e.get('event_type')=='inference_response' for e in events)
        if not (path.parent/'manifest.json').exists() or not (path.parent/'checksum.sha256').exists():failed+=1;continue
        if not verify(path.parent):raise ValueError('An existing sealed attempt failed integrity')
        manifest=json.loads((path.parent/'manifest.json').read_text());config=json.loads((path.parent/'config.snapshot.json').read_text())
        if manifest['status']=='completed':
            key=path.parent.parent.name
            if key in completed:raise ValueError('Duplicate completed job attempts')
            completed[key]={'path':str(path.parent),'calls':manifest['completed_model_calls'],'plan_hash':manifest['plan_hash'],
                            'defense':config['defense'],'phase':config['phase'],'intervention':config['intervention'],'backend':manifest['model_identity']['backend']}
        else:failed+=1
    return {'completed':completed,'failed_runs':failed,'physical_calls':physical,'returned_calls':returned}


async def run(root,backend='mock',resume=False,env_file=None):
    root=Path(root);plan=validate_plan(root);output=ROOT/'results/repository-runs'/root.name
    state_path=root/'primary-long-state.json'
    if state_path.exists() and not resume:raise ValueError('Existing state requires explicit --resume')
    recovered=recover(output)
    if any(v['plan_hash']!=plan['plan_hash'] for v in recovered['completed'].values()):raise ValueError('Output belongs to another freeze')
    for key,value in recovered['completed'].items():
        index=int(key.removeprefix('job-'));job=plan['jobs'][index]
        if value['calls']!=job['calls'] or value['defense']!=job['defense'] or value['intervention']!=job['intervention'] or value['phase']!=job['phase'] or value['backend']!=backend:raise ValueError('Existing completed job differs from assignment/backend')
    old=json.loads(state_path.read_text()) if state_path.exists() else {}
    if old and old.get('backend')!=backend:raise ValueError('Cannot change backend on resume')
    elapsed=old.get('execution_seconds',0.0);resumes=old.get('resume_count',0)+int(resume)
    state={'status':'waiting','backend':backend,'worker':'primary','planned_runs':plan['planned_runs'],'planned_calls':plan['planned_calls'],
           'completed_runs':len(recovered['completed']),'physical_calls':recovered['physical_calls'],'returned_calls':recovered['returned_calls'],
           'failed_runs':recovered['failed_runs'],'resume_count':resumes,'execution_seconds':elapsed,'plan_hash':plan['plan_hash']}
    began=None;waiting=time.monotonic();provider=AttributedMock();lease=None;last_resource=0.0
    def save(**kw):
        state.update(kw,updated_utc=utc())
        if began is not None:state['execution_seconds']=elapsed+time.monotonic()-began
        atomic(state_path,state)
    def budget():
        if (root/'STOP').exists():raise CallBudgetExhausted('operator_stop')
        if began is not None and elapsed+time.monotonic()-began>=plan['max_wall_seconds']:raise CallBudgetExhausted('queue_wall_budget')
    from contagion.inference import CallBudgetExhausted
    async def resource_guard():
        nonlocal last_resource
        budget()
        if backend=='mock':return
        if time.monotonic()-last_resource<10:return
        from remote_worker import execute
        def capacity():return next(m['capacity'] for m in execute('primary','capacity',env_file) if 'capacity' in m)
        value=capacity();reason=resource_reason(value)
        if reason in {'ram_low_or_unknown','gpu_temperature_unknown'}:raise CallBudgetExhausted(reason)
        if reason or cooling_required(value):
            start=time.monotonic();stable=0
            while True:
                budget();value=capacity();reason=resource_reason(value)
                if reason in {'ram_low_or_unknown','gpu_temperature_unknown'}:raise CallBudgetExhausted(reason)
                stable=stable+1 if cooled(value) else 0
                if stable>=2:break
                if time.monotonic()-start>600:raise CallBudgetExhausted('cooling_timeout')
                save(status='cooling');await asyncio.sleep(10)
            save(status='running')
        last_resource=time.monotonic()
    with (root/'queue.lock').open('a') as queue_lease:
        fcntl.flock(queue_lease,fcntl.LOCK_EX|fcntl.LOCK_NB);save()
        try:
            while plan['after']:
                budget()
                try:previous=json.loads(Path(plan['after']).read_text())
                except FileNotFoundError:
                    if time.monotonic()-waiting>plan['max_wait_seconds']:raise CallBudgetExhausted('prerequisite_state_not_created') from None
                    await asyncio.sleep(15);continue
                if previous['status']=='completed':break
                if previous['status'] in {'failed','stopped','budget_exhausted'}:raise RuntimeError('Prerequisite stopped; review before further inference')
                if time.monotonic()-waiting>plan['max_wait_seconds']:raise CallBudgetExhausted('queue_wait_budget')
                await asyncio.sleep(15)
            began=time.monotonic();save(status='running')
            if backend=='ollama':
                if env_file is None or Path(env_file).resolve()!=ROOT/'.env.primary':raise ValueError('Explicit primary env required')
                if not plan['readiness']:raise ValueError('Readiness proof required for live allocation')
                proof=validate_readiness(plan['readiness'])
                if proof['readiness_hash']!=plan['readiness_hash']:raise ValueError('Readiness changed')
                env=load_env(Path(env_file),{});endpoint=env.get('CONTAGION_BASE_URL','');parsed=urlsplit(endpoint)
                if (parsed.scheme,parsed.hostname,parsed.port,parsed.path)!=('http','127.0.0.1',11835,'') or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Primary loopback tunnel required')
                lock=ROOT/'results/checkpoint-gates/controller-primary.lock';lock.parent.mkdir(parents=True,exist_ok=True)
                lease=lock.open('a')
                while True:
                    try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                    except BlockingIOError:
                        budget();save(status='waiting_for_primary_lease');await asyncio.sleep(5)
                save(status='running')
                provider=RepositoryProvider(endpoint,api='ollama',retries=0,timeout=90)
                inventory=await provider.discover()
                if not any(m.get('name')==plan['model'] and m.get('digest')==plan['model_digest'] for m in inventory):raise ValueError('Pinned primary model unavailable')
                provider.identity.update(model=plan['model'],digest=plan['model_digest'],worker_label='primary')
                if old.get('model_identity') and old['model_identity']!=provider.identity:raise ValueError('Backend identity changed on resume; register a new cohort')
                save(model_identity=provider.identity)
                await resource_guard()
            for index,job in enumerate(plan['jobs']):
                budget();key=f'job-{index:03}'
                if key in recovered['completed']:continue
                if state['physical_calls']+job['calls']>plan['max_http_attempts']:raise CallBudgetExhausted('remaining_physical_budget')
                save(status='running',job_index=index,phase=job['phase'],defense=job['defense'],rounds=job['rounds'])
                row,payload=load_payload(plan,job)
                path=await run_case(row,payload,plan,job,provider,output/key,before_call=resource_guard,stop_file=root/'STOP')
                recovered=recover(output);save(completed_runs=len(recovered['completed']),physical_calls=recovered['physical_calls'],returned_calls=recovered['returned_calls'],failed_runs=recovered['failed_runs'])
                manifest=json.loads((path/'manifest.json').read_text())
                if manifest['status']!='completed' or manifest['parse_failures'] or manifest['completed_model_calls']!=job['calls']:raise RuntimeError('Per-run gate failed; later calls stopped')
            save(status='completed')
        except BaseException as exc:
            recovered=recover(output);save(status='stopped',error_type=type(exc).__name__,completed_runs=len(recovered['completed']),physical_calls=recovered['physical_calls'],returned_calls=recovered['returned_calls'],failed_runs=recovered['failed_runs']);raise
        finally:
            if hasattr(provider,'close'):await provider.close()
            if lease:lease.close()
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    f=sub.add_parser('prepare');f.add_argument('--root',type=Path,required=True);f.add_argument('--catalog',type=Path,required=True);f.add_argument('--model',required=True);f.add_argument('--digest',required=True);f.add_argument('--after',type=Path);f.add_argument('--readiness',type=Path);f.add_argument('--cases',type=int,default=8);f.add_argument('--max-calls',type=int,default=5200);f.add_argument('--max-hours',type=int,default=8)
    r=sub.add_parser('run');r.add_argument('--root',type=Path,required=True);r.add_argument('--provider',choices=['mock','ollama'],default='mock');r.add_argument('--env-file',type=Path);r.add_argument('--resume',action='store_true')
    a=p.parse_args()
    if a.command=='prepare':
        plan=prepare(a.root,a.catalog,a.model,a.digest,a.after,a.readiness,a.cases,max_http_attempts=a.max_calls,max_hours=a.max_hours);print('Frozen',plan['planned_runs'],'runs /',plan['planned_calls'],'scheduled responses; primary-only, ring, long-task safeguard comparison.')
    else:
        try:result=asyncio.run(run(a.root,a.provider,a.resume,a.env_file));print(result['status'],result['completed_runs'],'/',result['planned_runs'])
        except Exception as exc:p.exit(1,f'Primary long queue stopped ({type(exc).__name__}); retained attempts and remaining budgets require review.\n')
