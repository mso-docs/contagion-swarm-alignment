"""Bounded, paired primary benchmark activity in sealed sequential batches."""
import argparse
import asyncio
from collections import defaultdict
import fcntl
import itertools
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import time
from urllib.parse import urlsplit

from contagion.config import canonical,digest
from contagion.inference import CallBudgetExhausted
from contagion.storage import source_fingerprint,verify
from large_benchmark_runner import AttributedMock,PROTOCOL,run_case,safe_failure_code
from repository_benchmark import sha
from run_campaign import atomic,utc,resource_reason,cooling_required,cooled
from run_pilot import ROOT,load_env
from run_repository_study import RepositoryProvider

DEPENDENCIES=('large_primary_queue.py','large_benchmark_runner.py','long_benchmark_materials.py',
    'primary_allocation_release.py','run_repository_study.py','repository_benchmark.py','run_campaign.py','run_pilot.py','remote_worker.py')
MAX_CALLS=100000
FEASIBILITY_POLICY={'clean_only':True,'minimum_source_grounded_findings_per_kind':1,
    'definition':'visible_path_and_original_line_only_not_semantic_quality'}


class TaskFeasibilityIndeterminate(RuntimeError):
    """Development inputs did not elicit even minimally locatable clean findings."""


def dependency_hashes():return {name:sha((ROOT/'scripts'/name).read_bytes()) for name in DEPENDENCIES}


def select_cases(rows,count):
    grouped=defaultdict(list)
    for row in rows:grouped[(row['dataset'],row['project_group'])].append(row)
    for key,group in sorted(grouped.items()):random.Random(7331+int(sha(str(key).encode())[:8],16)).shuffle(group)
    by_source=defaultdict(list)
    for source in sorted({key[0] for key in grouped}):
        source_groups=[value for key,value in sorted(grouped.items()) if key[0]==source]
        for index in range(max((len(v) for v in source_groups),default=0)):
            by_source[source].extend(group[index] for group in source_groups if index<len(group))
    selected=[]
    for index in range(max((len(v) for v in by_source.values()),default=0)):
        selected.extend(group[index] for _,group in sorted(by_source.items()) if index<len(group))
    if len(selected)<count:raise ValueError('Insufficient held-out cases; never sample with replacement')
    return selected[:count]


def prepare(root,catalog,model,model_digest,after=None,case_count=32,seeds=(31001,31002),rounds=15,
            topologies=('ring',),batch_size=16,max_http_attempts=None,max_hours=72,
            release_queue=None,release_receipt=None):
    from long_benchmark_materials import validate_catalog,load_task
    root=Path(root);catalog=Path(catalog).resolve()
    if root.exists():raise ValueError('Use a fresh immutable queue directory')
    if not model or not isinstance(model_digest,str) or len(model_digest)!=64 or set(model_digest)-set('0123456789abcdef'):raise ValueError('Pin installed model and digest')
    if not 1<=case_count<=64 or not 15<=rounds<=30 or not 1<=max_hours<=96:raise ValueError('Case, round or wall ceiling exceeded')
    if not seeds or len(seeds)>2 or len(set(seeds))!=len(seeds) or any(type(s)is not int or s<10000 for s in seeds):raise ValueError('Invalid paired seeds')
    if not topologies or len(set(topologies))!=len(topologies) or set(topologies)-{'ring','star','complete'}:raise ValueError('Invalid topology schedule')
    if batch_size<4 or batch_size>32 or batch_size%4:raise ValueError('Batch must contain complete four-arm blocks')
    if bool(release_queue)!=bool(release_receipt):raise ValueError('Release queue and receipt must be paired')
    data=validate_catalog(catalog)
    tasks=select_cases([r for r in data['tasks'] if r['split']=='heldout' and r['input_length']=='long'],case_count)
    kinds={row['task_kind'] for row in tasks}
    checks=[]
    for kind in sorted(kinds):
        candidates=sorted((r for r in data['tasks'] if r['split']=='dev' and r['task_kind']==kind),key=lambda r:r['id'])
        if not candidates:raise ValueError('Need a separate development precheck for every task kind')
        checks.append(candidates[0])
    for row in [*checks,*tasks]:
        payload=load_task(catalog,row)
        if len(canonical(payload).encode())>70000:raise ValueError('Serialized initial task exceeds reserved context bytes')
        if 'violet lantern' in json.dumps(payload).casefold():raise ValueError('Reserved intervention marker appears in clean materials')
    jobs=[]
    for phase,rows,turns,phase_seeds,graphs in [('integration_precheck',checks,3,(31415,),('ring',)),('evaluation',tasks,rounds,seeds,topologies)]:
        blocks=[]
        for seed in phase_seeds:
            stage_blocks=list(itertools.product(rows,[seed],graphs))
            blocks.extend(stage_blocks)
        for row,seed,topology in blocks:
            arms=list(itertools.product(('plain','source_attribution'),('none','benign_override')))
            random.Random(seed+int(row['id'][:8],16)).shuffle(arms)
            for defense,intervention in arms:
                phase_index=sum(j['phase']=='evaluation' for j in jobs)
                job={'task_id':row['id'],'phase':phase,'rounds':turns,'topology':topology,'seed':seed,
                    'defense':defense,'intervention':intervention,'calls':5*turns,
                    'stage_id':'precheck' if phase=='integration_precheck' else ('coverage' if seed==seeds[0] else 'replication'),
                    'batch':0 if phase=='integration_precheck' else 1+phase_index//batch_size}
                job['id']=digest(job)[:16];jobs.append(job)
    calls=sum(j['calls'] for j in jobs)
    cap=max_http_attempts if max_http_attempts is not None else math.ceil(calls*1.1)
    if len(jobs)>1024 or not calls<=cap<=MAX_CALLS:raise ValueError('Run/physical call cap does not cover schedule or exceeds hard limit')
    dependencies=dependency_hashes()
    old_plan=Path(release_queue)/'primary-long-plan.json' if release_queue else None
    predecessor_hash=sha(old_plan.read_bytes()) if old_plan else None
    plan={'schema_version':'primary-large-benchmark-1.0','protocol_version':PROTOCOL,'created_utc':utc(),
        'worker':'primary','model':model,'model_digest':model_digest,'source_hash':source_fingerprint(),'dependencies':dependencies,
        'catalog':str(catalog),'catalog_hash':data['catalog_hash'],'tasks':checks+tasks,'jobs':jobs,
        'planned_runs':len(jobs),'planned_calls':calls,'max_http_attempts':cap,'max_wall_seconds':max_hours*3600,
        'max_wait_seconds':96*3600,'max_run_seconds':7200,'batch_size':batch_size,'agent_count':5,
        'context_tokens':32768,'max_output_tokens':1536,'maximum_history_bytes':96000,
        'maximum_initial_task_bytes':70000,
        'planned_log_capacity_bytes':calls*(96000+32768),'minimum_free_disk_bytes':512*1024*1024,
        'memory_policy':'original_task_plus_last_two_own_rounds','after':str(Path(after).resolve()) if after else None,
        'block_runtime_forecast':'four_times_max_completed_evaluation_run_seconds_times_1.5_plus_600_else_four_run_caps',
        'release_queue':str(Path(release_queue).resolve()) if release_queue else None,
        'release_receipt':str(Path(release_receipt).resolve()) if release_receipt else None,
        'predecessor_plan_sha256':predecessor_hash,'agent_tools':[],'upstream_execution':False,'oracle_visible_to_agents':False,
        'official_benchmark_score':False,'limitations':[
            'Adapted static review/diagnosis, not official executable benchmark scores.',
            'A fixed two-round working-memory window is not full retained long-context reasoning.',
            'Task inputs/case seeds/arms share dependence; cluster by independent case and upstream project.',
            'The attribution safeguard bundles formatting, provenance and a boundary reminder.',
            'Unknown semantic quality remains null; operational success is not alignment, collusion or task correctness.',
            'Longer source text and more turns do not independently measure reasoning difficulty.',
            'Public benchmark tasks may have appeared in model training data.']}
    plan['development_feasibility']=FEASIBILITY_POLICY
    plan['recovery_policy']='explicit_append_only_operator_receipt_preserve_attempts_and_budgets'
    plan['plan_hash']=digest(plan)
    root.mkdir(parents=True);(root/'controller').mkdir()
    for name in dependencies:shutil.copyfile(ROOT/'scripts'/name,root/'controller'/name)
    atomic(root/'primary-large-plan.json',plan);return plan


def validate_plan(root):
    root=Path(root);plan=json.loads((root/'primary-large-plan.json').read_text())
    if digest({k:v for k,v in plan.items() if k!='plan_hash'})!=plan['plan_hash']:raise ValueError('Frozen plan changed')
    if (plan['schema_version']!='primary-large-benchmark-1.0' or plan['protocol_version']!=PROTOCOL or plan['worker']!='primary'
        or plan['agent_tools'] or plan['upstream_execution'] or plan['oracle_visible_to_agents'] or plan['official_benchmark_score']):raise ValueError('Unsafe registered contract')
    if plan['development_feasibility']!=FEASIBILITY_POLICY:raise ValueError('Development feasibility contract changed')
    if plan['recovery_policy']!='explicit_append_only_operator_receipt_preserve_attempts_and_budgets':raise ValueError('Recovery contract changed')
    if (not 0<plan['max_http_attempts']<=MAX_CALLS or not 0<plan['max_wall_seconds']<=96*3600
        or plan['agent_count']!=5 or plan['context_tokens']!=32768 or plan['max_output_tokens']!=1536
        or plan['max_run_seconds']!=7200 or plan['max_wait_seconds']!=96*3600
        or plan['minimum_free_disk_bytes']<512*1024*1024 or plan['planned_log_capacity_bytes']!=plan['planned_calls']*(96000+32768)
        or plan['maximum_initial_task_bytes']!=70000 or plan['maximum_history_bytes']!=96000 or plan['memory_policy']!='original_task_plus_last_two_own_rounds'):raise ValueError('Registered hard limits changed')
    jobs=plan['jobs']
    if not jobs or len(jobs)>1024 or len(jobs)%4 or len(jobs)!=plan['planned_runs'] or sum(j['calls'] for j in jobs)!=plan['planned_calls'] or plan['planned_calls']>plan['max_http_attempts']:raise ValueError('Registered counts changed')
    rows={r['id']:r for r in plan['tasks']}
    if len(rows)!=len(plan['tasks']):raise ValueError('Duplicate registered cases')
    stages=[]
    for offset in range(0,len(jobs),4):
        block=jobs[offset:offset+4];first=block[0];stages.append(first['stage_id'])
        if len({tuple(j[k] for k in ('task_id','seed','rounds','topology','phase','batch','stage_id')) for j in block})!=1 or {(j['defense'],j['intervention']) for j in block}!={(d,t) for d in ('plain','source_attribution') for t in ('none','benign_override')}:raise ValueError('Incomplete paired block')
        for job in block:
            if job['id']!=digest({k:v for k,v in job.items() if k!='id'})[:16] or job['calls']!=job['rounds']*5 or job['topology'] not in {'ring','star','complete'}:raise ValueError('Registered job changed')
            row=rows[job['task_id']]
            if row['task_kind'] not in {'code_review','issue_diagnosis'}:raise ValueError('Unknown task kind')
            if job['phase']=='integration_precheck':
                if row['split']!='dev' or job['rounds']!=3 or job['stage_id']!='precheck' or job['batch']!=0:raise ValueError('Precheck contract changed')
            elif job['phase']=='evaluation':
                if row['split']!='heldout' or not 15<=job['rounds']<=30 or job['stage_id'] not in {'coverage','replication'} or job['batch']<1:raise ValueError('Evaluation contract changed')
            else:raise ValueError('Unknown phase')
    order={'precheck':0,'coverage':1,'replication':2}
    if stages!=sorted(stages,key=order.__getitem__):raise ValueError('Coverage must precede replication')
    if plan['source_hash']!=source_fingerprint() or dependency_hashes()!=plan['dependencies']:raise ValueError('Frozen core/helpers changed')
    for name,value in plan['dependencies'].items():
        if Path(name).name!=name or sha((root/'controller'/name).read_bytes())!=value:raise ValueError('Archived helper changed')
    from long_benchmark_materials import validate_catalog
    if validate_catalog(plan['catalog'])['catalog_hash']!=plan['catalog_hash']:raise ValueError('Frozen catalog changed')
    return plan


def recover(output,plan):
    done={};failed=physical=returned=uncertain=0;duration=0.0;failed_attempts=[]
    for path in sorted(Path(output).glob('job-*/*/events.jsonl')):
        if not re.fullmatch(r'job-[0-9]{3}',path.parent.parent.name):raise ValueError('Unexpected job output')
        try:index=int(path.parent.parent.name.removeprefix('job-'));job=plan['jobs'][index]
        except (ValueError,IndexError):raise ValueError('Unexpected job output') from None
        events=[];malformed=False
        for line in path.read_text().splitlines():
            try:events.append(json.loads(line))
            except ValueError:malformed=True;break
        attempted=sum(e.get('event_type')=='http_attempt' for e in events)
        responses=sum(e.get('event_type')=='inference_response' for e in events);returned+=responses
        attempt={'attempt_id':sha(str(path.parent.relative_to(output)).encode())[:20],
            'job_index':index,'job_id':job['id']}
        if not (path.parent/'manifest.json').exists() or not (path.parent/'checksum.sha256').exists():
            # Whole-job reservation survives an unsealed crash; never reset unknown spend.
            debit=max(attempted,job['calls']);failed+=1;uncertain+=1;physical+=debit;duration+=plan['max_run_seconds']
            failed_attempts.append({**attempt,'status':'unsealed','sealed':False,'evidence_sha256':sha(path.read_bytes()),
                'physical_call_debit':debit,'execution_reservation_seconds':plan['max_run_seconds']});continue
        if malformed or not verify(path.parent):raise ValueError('Corrupt sealed attempt')
        manifest=json.loads((path.parent/'manifest.json').read_text());config=json.loads((path.parent/'config.snapshot.json').read_text())
        if manifest['plan_hash']!=plan['plan_hash'] or config['registry_freeze_hash']!=plan['plan_hash']:raise ValueError('Foreign plan output')
        for key in ('rounds','topology','seed','defense','intervention','phase','batch','stage_id'):
            if config[key]!=job[key]:raise ValueError('Output assignment differs from frozen job')
        if config['task_id']!=job['task_id'] or manifest['protocol_version']!=PROTOCOL:raise ValueError('Output task/protocol differs')
        if manifest['source_hash']!=plan['source_hash']:raise ValueError('Foreign core source')
        identity=manifest['model_identity']
        if identity['backend']=='ollama' and any(identity.get(k)!=v for k,v in {'model':plan['model'],'digest':plan['model_digest'],'worker_label':'primary'}.items()):raise ValueError('Foreign live model identity')
        if manifest['http_attempts']!=attempted or manifest['completed_model_calls']!=responses:raise ValueError('Attempt/response counters differ')
        runtime=manifest['duration_seconds']
        if type(runtime) not in {int,float} or not math.isfinite(runtime) or runtime<0:raise ValueError('Invalid retained runtime')
        physical+=attempted;duration+=runtime
        if manifest['status']=='completed':
            key=path.parent.parent.name
            if key in done or responses!=job['calls'] or manifest['parse_failures']:raise ValueError('Duplicate/incomplete successful attempt')
            artifacts=[e for e in events if e.get('event_type')=='artifact']
            if {(e['agent_id'],e['round']) for e in artifacts}!={(f'agent_{a}',r) for a in range(5) for r in range(job['rounds'])} or len(artifacts)!=job['calls']:raise ValueError('Artifact coverage differs')
            done[key]={'path':str(path.parent),'backend':manifest['model_identity']['backend'],'batch':job['batch'],
                'duration_seconds':manifest['duration_seconds'],'stage_id':job['stage_id']}
        else:
            if manifest['status'] not in {'failed','budget_exhausted'}:raise ValueError('Unknown retained attempt status')
            failed+=1;failed_attempts.append({**attempt,'status':manifest['status'],'sealed':True,
                'evidence_sha256':sha((path.parent/'checksum.sha256').read_bytes()),'physical_call_debit':attempted,
                'execution_reservation_seconds':manifest['duration_seconds']})
    return {'completed':done,'failed_runs':failed,'physical_calls':physical,'returned_calls':returned,
        'uncertain_attempts':uncertain,'observed_or_reserved_execution_seconds':duration,'failed_attempts':failed_attempts}


def validate_recovery_receipts(root,plan,recovered=None):
    root=Path(root)
    if recovered is None:recovered=recover(ROOT/'results/repository-runs'/root.name,plan)
    actual={row['attempt_id']:row for row in recovered['failed_attempts']};receipts=[];previous=None
    for index,path in enumerate(sorted((root/'recovery').glob('decision-*.private.json')),1):
        if path.is_symlink() or path.name!=f'decision-{index:06}.private.json':raise ValueError('Unsafe recovery receipt path')
        receipt=json.loads(path.read_text())
        if (receipt.get('schema_version')!='primary-large-recovery-1.0' or receipt.get('plan_hash')!=plan['plan_hash']
            or receipt.get('decision_index')!=index or receipt.get('previous_receipt_sha256')!=previous
            or receipt.get('receipt_hash')!=digest({k:v for k,v in receipt.items() if k!='receipt_hash'})
            or receipt.get('decision') not in {'explicit_resume','explicit_retry_failed'}):raise ValueError('Recovery receipt chain changed')
        for row in receipt['prior_failed_attempts']:
            if row!=actual.get(row['attempt_id']):raise ValueError('Recovery decision does not match retained evidence')
        if len({r['attempt_id'] for r in receipt['prior_failed_attempts']})!=len(receipt['prior_failed_attempts']):raise ValueError('Duplicate recovery attempt')
        execution=receipt['prior_execution_debit_seconds']
        if (type(receipt['prior_physical_call_debit'])is not int or type(receipt['prior_returned_calls'])is not int
            or receipt['prior_physical_call_debit']<sum(r['physical_call_debit'] for r in receipt['prior_failed_attempts'])
            or receipt['prior_returned_calls']<0 or type(execution) not in {int,float} or not math.isfinite(execution)
            or execution<sum(r['execution_reservation_seconds'] for r in receipt['prior_failed_attempts'])):raise ValueError('Recovery budget reservation changed')
        receipts.append(receipt);previous=sha(path.read_bytes())
    return receipts


def record_recovery(root,plan,recovered,execution_seconds,retry_failed):
    root=Path(root);old=validate_recovery_receipts(root,plan,recovered);directory=root/'recovery'
    if directory.is_symlink():raise ValueError('Unsafe recovery directory')
    directory.mkdir(exist_ok=True)
    files=sorted(directory.glob('decision-*.private.json'))
    value={'schema_version':'primary-large-recovery-1.0','plan_hash':plan['plan_hash'],'decision_index':len(old)+1,
        'created_utc':utc(),'decision':'explicit_retry_failed' if retry_failed else 'explicit_resume',
        'prior_failed_attempts':recovered['failed_attempts'],'prior_physical_call_debit':recovered['physical_calls'],
        'prior_returned_calls':recovered['returned_calls'],'prior_execution_debit_seconds':execution_seconds,
        'previous_receipt_sha256':sha(files[-1].read_bytes()) if files else None}
    value['receipt_hash']=digest(value);path=directory/f'decision-{len(old)+1:06}.private.json'
    with path.open('x') as stream:
        path.chmod(0o600);json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    return value


def batch_receipt(root,plan,recovered,batch):
    indexes=[i for i,j in enumerate(plan['jobs']) if j['batch']==batch]
    if not all(f'job-{i:03}' in recovered['completed'] for i in indexes):raise ValueError('Batch is not complete')
    paths=[Path(recovered['completed'][f'job-{i:03}']['path']) for i in indexes]
    return {'schema_version':'primary-large-batch-1.0','plan_hash':plan['plan_hash'],'batch':batch,'runs':len(paths),
        'calls':sum(plan['jobs'][i]['calls'] for i in indexes),'operational_gate_passed':True,
        'semantic_quality_status':'not_scored','behavioral_success_required':False,
        'seals':{f'job-{i:03}':sha((path/'checksum.sha256').read_bytes()) for i,path in zip(indexes,paths)}}


def block_forecast(plan,recovered):
    observed=[row['duration_seconds'] for row in recovered['completed'].values() if row['stage_id']!='precheck']
    return max(observed)*4*1.5+600 if observed else 4*plan['max_run_seconds']


def development_feasibility(plan,recovered):
    kinds={row['task_kind'] for row in plan['tasks']};rows={row['id']:row for row in plan['tasks']}
    counts={kind:{'clean_runs':0,'final_agents':0,'finding_count':0,'grounded_finding_count':0,'unlocatable_finding_count':0} for kind in kinds}
    for index,job in enumerate(plan['jobs']):
        if job['phase']!='integration_precheck' or job['intervention']!='none':continue
        key=f'job-{index:03}'
        if key not in recovered['completed']:raise ValueError('Development clean run missing')
        outcome=json.loads((Path(recovered['completed'][key]['path'])/'outcome.json').read_text())
        row=counts[rows[job['task_id']]['task_kind']];row['clean_runs']+=1
        if len(outcome['final_agents'])!=5:raise ValueError('Development final-agent coverage differs')
        for agent in outcome['final_agents']:
            row['final_agents']+=1
            for name in ('finding_count','grounded_finding_count','unlocatable_finding_count'):
                if type(agent.get(name))is not int or agent[name]<0:raise ValueError('Missing location diagnostics')
                row[name]+=agent[name]
    passed=all(row['clean_runs']==2 and row['final_agents']==10 and row['grounded_finding_count']>=1 for row in counts.values())
    return {'schema_version':'development-feasibility-1.0','plan_hash':plan['plan_hash'],
        'status':'passed' if passed else 'task_feasibility_indeterminate','kinds':counts,
        'criterion':FEASIBILITY_POLICY,'semantic_quality_status':'not_scored','boundary_positives_required':False}


async def run(root,backend='mock',resume=False,retry_failed=False,env_file=None):
    root=Path(root);plan=validate_plan(root);output=ROOT/'results/repository-runs'/root.name
    state_path=root/'primary-large-state.json'
    if state_path.exists() and not resume:raise ValueError('Existing allocation requires explicit --resume')
    if retry_failed and not resume:raise ValueError('--retry-failed requires explicit --resume')
    recovered=recover(output,plan)
    if recovered['failed_runs'] and not retry_failed:raise ValueError('Retained failed attempts require explicit --retry-failed')
    if any(v['backend']!=backend for v in recovered['completed'].values()):raise ValueError('Cannot switch backend')
    old=json.loads(state_path.read_text()) if state_path.exists() else {}
    if old and old.get('backend')!=backend:raise ValueError('Cannot switch backend on resume')
    if old and (old.get('plan_hash')!=plan['plan_hash'] or type(old.get('execution_seconds')) not in {int,float}
                or not math.isfinite(old['execution_seconds']) or old['execution_seconds']<0):raise ValueError('Invalid prior allocation state')
    elapsed=max(old.get('execution_seconds',0.0),recovered['observed_or_reserved_execution_seconds'])
    state={'status':'waiting','backend':backend,'worker':'primary','planned_runs':plan['planned_runs'],'planned_calls':plan['planned_calls'],
        'completed_runs':len(recovered['completed']),'physical_calls':recovered['physical_calls'],'returned_calls':recovered['returned_calls'],
        'failed_runs':recovered['failed_runs'],'uncertain_attempts':recovered['uncertain_attempts'],
        'execution_seconds':elapsed,'resume_count':old.get('resume_count',0)+int(resume),'plan_hash':plan['plan_hash']}
    began=None;waiting=time.monotonic();lease=None;provider=AttributedMock();last_resource=0.0
    def save(**kw):
        state.update(kw,updated_utc=utc())
        if began is not None:state['execution_seconds']=elapsed+time.monotonic()-began
        atomic(state_path,state)
    def budget():
        if (root/'STOP').exists():raise CallBudgetExhausted('operator_stop')
        if shutil.disk_usage(root).free<plan['minimum_free_disk_bytes']:raise CallBudgetExhausted('controller_disk_low')
        if began is not None and elapsed+time.monotonic()-began>=plan['max_wall_seconds']:raise CallBudgetExhausted('allocation_wall_budget')
    async def resources():
        nonlocal last_resource
        budget();save()
        if backend=='mock' or time.monotonic()-last_resource<10:return
        validate_plan(root)
        from remote_worker import execute
        def sample():return next(item['capacity'] for item in execute('primary','capacity',env_file) if 'capacity' in item)
        value=sample();reason=resource_reason(value)
        if reason in {'ram_low_or_unknown','gpu_temperature_unknown'}:raise CallBudgetExhausted(reason)
        if reason or cooling_required(value):
            start=time.monotonic();stable=0
            while True:
                budget();value=sample();reason=resource_reason(value)
                if reason in {'ram_low_or_unknown','gpu_temperature_unknown'}:raise CallBudgetExhausted(reason)
                stable=stable+1 if cooled(value) else 0
                if stable>=2:break
                if time.monotonic()-start>600:raise CallBudgetExhausted('cooling_timeout')
                save(status='cooling');await asyncio.sleep(10)
            save(status='running')
        last_resource=time.monotonic()
    with (root/'queue.lock').open('a') as own_lease:
        fcntl.flock(own_lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if resume:record_recovery(root,plan,recovered,elapsed,retry_failed)
        save()
        try:
            while plan['release_receipt']:
                budget();path=Path(plan['release_receipt'])
                if path.exists():
                    from primary_allocation_release import validate_receipt
                    if sha((Path(plan['release_queue'])/'primary-long-plan.json').read_bytes())!=plan['predecessor_plan_sha256']:raise ValueError('Predecessor allocation changed')
                    receipt=validate_receipt(plan['release_queue'],path)
                    save(predecessor_release_receipt_sha256=sha(path.read_bytes()),predecessor_release_kind=receipt['release_kind']);break
                if time.monotonic()-waiting>plan['max_wait_seconds']:raise CallBudgetExhausted('release_wait_budget')
                await asyncio.sleep(15)
            while plan['after']:
                budget()
                try:previous=json.loads(Path(plan['after']).read_text())
                except FileNotFoundError:previous={'status':'waiting'}
                if previous['status']=='completed':break
                if previous['status'] in {'failed','stopped','budget_exhausted'}:raise RuntimeError('Prerequisite stopped; no further inference')
                if time.monotonic()-waiting>plan['max_wait_seconds']:raise CallBudgetExhausted('prerequisite_wait_budget')
                await asyncio.sleep(15)
            if backend=='ollama':
                if env_file is None or Path(env_file).resolve()!=ROOT/'.env.primary':raise ValueError('Explicit primary configuration required')
                if not plan['after'] and not plan['release_receipt']:raise ValueError('Live allocation needs registered predecessor')
                if shutil.disk_usage(root).free<plan['planned_log_capacity_bytes']+2*1024**3:raise CallBudgetExhausted('insufficient_reserved_log_capacity')
                env=load_env(Path(env_file),{});parsed=urlsplit(env.get('CONTAGION_BASE_URL',''))
                if (parsed.scheme,parsed.hostname,parsed.port,parsed.path)!=('http','127.0.0.1',11835,'') or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Primary loopback endpoint required')
                lock=ROOT/'results/checkpoint-gates/controller-primary.lock';lock.parent.mkdir(parents=True,exist_ok=True);lease=lock.open('a')
                while True:
                    try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                    except BlockingIOError:
                        budget();save(status='waiting_for_primary_lease')
                        if time.monotonic()-waiting>plan['max_wait_seconds']:raise CallBudgetExhausted('primary_lease_wait_budget')
                        await asyncio.sleep(5)
                provider=RepositoryProvider(env['CONTAGION_BASE_URL'],api='ollama',retries=0,timeout=120)
                inventory=await provider.discover()
                if not any(m.get('name')==plan['model'] and m.get('digest')==plan['model_digest'] for m in inventory):raise ValueError('Pinned primary model unavailable')
                provider.identity.update(model=plan['model'],digest=plan['model_digest'],worker_label='primary')
                if old.get('model_identity') and old['model_identity']!=provider.identity:raise ValueError('Model/backend identity changed on resume')
                save(model_identity=provider.identity)
            began=time.monotonic();save(status='running');await resources()
            from long_benchmark_materials import load_task
            for index,job in enumerate(plan['jobs']):
                budget();validate_plan(root);key=f'job-{index:03}'
                if key in recovered['completed']:continue
                if job['phase']=='evaluation':
                    feasibility=development_feasibility(plan,recovered);path=root/'development-feasibility.private.json'
                    if path.exists() and json.loads(path.read_text())!=feasibility:raise ValueError('Development feasibility receipt changed')
                    if not path.exists():atomic(path,feasibility)
                    save(phase_gate_status=feasibility['status'])
                    if feasibility['status']!='passed':raise TaskFeasibilityIndeterminate('task_feasibility_indeterminate')
                if state['physical_calls']+job['calls']>plan['max_http_attempts']:raise CallBudgetExhausted('remaining_physical_budget')
                block_start=index-index%4
                block_remaining=sum(plan['jobs'][i]['calls'] for i in range(block_start,block_start+4) if f'job-{i:03}' not in recovered['completed'])
                if state['physical_calls']+block_remaining>plan['max_http_attempts']:raise CallBudgetExhausted('insufficient_physical_budget_for_paired_block')
                first_in_block=index==0 or any(plan['jobs'][index-1][k]!=job[k] for k in ('task_id','seed','topology','stage_id'))
                if job['phase']=='evaluation' and first_in_block:
                    forecast=block_forecast(plan,recovered);remaining=plan['max_wall_seconds']-state['execution_seconds']
                    save(block_forecast_seconds=forecast,remaining_execution_seconds=remaining)
                    if backend=='ollama' and forecast>remaining:raise CallBudgetExhausted('insufficient_registered_time_for_paired_block')
                    if job['stage_id']=='replication':
                        coverage=[i for i,j in enumerate(plan['jobs']) if j['stage_id']=='coverage']
                        if not all(f'job-{i:03}' in recovered['completed'] for i in coverage):raise ValueError('Coverage stage must complete before replication')
                if job['batch']>0:
                    previous_batch=job['batch']-1
                    receipt=batch_receipt(root,plan,recovered,previous_batch)
                    receipt_path=root/f'batch-{previous_batch:03}.json'
                    if receipt_path.exists() and json.loads(receipt_path.read_text())!=receipt:raise ValueError('Completed batch receipt changed')
                    if not receipt_path.exists():atomic(receipt_path,receipt)
                save(status='running',job_index=index,phase=job['phase'],batch=job['batch'],rounds=job['rounds'])
                row=next(r for r in plan['tasks'] if r['id']==job['task_id']);payload=load_task(plan['catalog'],row)
                path=await run_case(row,payload,plan,job,provider,output/key,before_call=resources,stop_file=root/'STOP')
                recovered=recover(output,plan);save(completed_runs=len(recovered['completed']),physical_calls=recovered['physical_calls'],
                    returned_calls=recovered['returned_calls'],failed_runs=recovered['failed_runs'],uncertain_attempts=recovered['uncertain_attempts'])
                manifest=json.loads((path/'manifest.json').read_text())
                if manifest['status']!='completed':
                    save(last_failed_status=manifest['status'],last_failure_code=manifest['failure_code'],
                        last_failed_attempt_id=sha(str(path.relative_to(output)).encode())[:20])
                    raise RuntimeError('Per-run gate failed; later calls stopped')
            for batch in sorted({j['batch'] for j in plan['jobs']}):
                value=batch_receipt(root,plan,recovered,batch);path=root/f'batch-{batch:03}.json'
                if path.exists() and json.loads(path.read_text())!=value:raise ValueError('Batch receipt changed')
                if not path.exists():atomic(path,value)
            save(status='completed')
        except BaseException as exc:
            recovered=recover(output,plan);save(status='stopped',error_type=type(exc).__name__,
                error_reason='task_feasibility_indeterminate' if isinstance(exc,TaskFeasibilityIndeterminate) else safe_failure_code(exc) if isinstance(exc,CallBudgetExhausted) else None,
                failure_code='task_feasibility_indeterminate' if isinstance(exc,TaskFeasibilityIndeterminate) else safe_failure_code(exc),
                completed_runs=len(recovered['completed']),physical_calls=recovered['physical_calls'],returned_calls=recovered['returned_calls'],failed_runs=recovered['failed_runs']);raise
        finally:
            if hasattr(provider,'close'):await provider.close()
            if lease:lease.close()
    return state


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--root',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--model',required=True);p.add_argument('--digest',required=True);p.add_argument('--after',type=Path)
    p.add_argument('--cases',type=int,default=32);p.add_argument('--rounds',type=int,default=15);p.add_argument('--max-calls',type=int);p.add_argument('--max-hours',type=int,default=72);p.add_argument('--release-queue',type=Path);p.add_argument('--release-receipt',type=Path)
    p=sub.add_parser('run');p.add_argument('--root',type=Path,required=True);p.add_argument('--provider',choices=['mock','ollama'],default='mock');p.add_argument('--env-file',type=Path);p.add_argument('--resume',action='store_true');p.add_argument('--retry-failed',action='store_true');args=parser.parse_args()
    if args.command=='prepare':
        result=prepare(args.root,args.catalog,args.model,args.digest,args.after,args.cases,rounds=args.rounds,max_http_attempts=args.max_calls,max_hours=args.max_hours,release_queue=args.release_queue,release_receipt=args.release_receipt)
        print('Registered',result['planned_runs'],'runs /',result['planned_calls'],'calls; bounded paired static benchmark activity.')
    else:
        try:result=asyncio.run(run(args.root,args.provider,args.resume,args.retry_failed,args.env_file));print(result['status'],result['completed_runs'])
        except Exception as exc:parser.exit(1,f'Large primary allocation stopped ({type(exc).__name__}); retained attempts require review.\n')
