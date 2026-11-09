"""Durable, bounded, secondary-only study queue. No simulated agent tools."""
import argparse
import asyncio
import fcntl
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time

from .config import digest
from .events import read_events, utc
from .inference import HTTPProvider,CallBudgetExhausted
from .monitor import evaluate_visibility
from .research_publication import make_research_snapshot, validate_research_snapshot
from .scenarios import build_database, sample_scenarios
from .storage import source_fingerprint, verify, write_json
from .studies import StudyPlan, freeze_plan, run_plan, summarize_study

MODELS=[('qwen3.5:4b','2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd'),
        ('qwen3.5:0.8b','f3817196d142eaf72ce79dfebe53dcb20bd21da87ce13e138a8f8e10a866b3a4')]
SIZES=[5,10,20,40,80,128]


def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)


def prepare(root,profile="extended"):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    database=Path('results/scenarios-v2.sqlite')
    if not database.exists():build_database(database)
    development,_=sample_scenarios(database,'development',['catalog','provenance','patch'],3,707)
    jobs=[];seen=set()
    priority,_=sample_scenarios(database,'evaluation',['catalog','provenance','patch'],6,1707)
    schedule=([(m,d,True) for m,d in MODELS] if profile=='deadline' else [])+[(m,d,False) for m,d in MODELS]
    for model,model_digest,priority_only in schedule:
        key=model.replace(':','-');block=[]
        def add(stage,plan):
            signature=digest(plan.model_dump())
            if signature in seen:return
            seen.add(signature)
            number=len(jobs)+len(block)
            path=root/'plans'/f'{number:04}.json';path.parent.mkdir(parents=True,exist_ok=True)
            write_json(path,plan.model_dump());freeze=root/'freezes'/f'{number:04}.json'
            frozen=freeze_plan(plan,freeze)
            calls=(5 if plan.research_question=='rq3' else plan.agent_count*plan.rounds)
            cases=len(plan.case_indices)*len(plan.families)
            planned=calls*cases*len(plan.seeds)*len(plan.topologies)*len(plan.interventions)
            block.append({'index':number,'stage':stage,'model':model,'digest':model_digest,
                          'model_key':key,'plan':str(path),'freeze':str(freeze),'freeze_hash':frozen['freeze_hash'],'calls':planned})
        def base(**kw):
            kw.setdefault('protocol_version','2.6')
            return StudyPlan(model=model,max_output_tokens=1024,max_wall_seconds=1800,max_total_model_calls=2000,**kw)
        for case in development:
            add('development',base(families=[case.family],case_indices=[int(case.case_id.rsplit('-',1)[1])],
                                  topologies=['ring','star','complete']))
        for executor in ['deny','permissive_simulator']:
            add('rq3_development',base(research_question='rq3',families=['record'],case_indices=[14],
                topologies=['single','complete'],executor=executor,max_model_calls=5))
        if priority_only:
            for case in priority:
                add('submission_rq1',base(split='evaluation',families=[case.family],case_indices=[int(case.case_id.rsplit('-',1)[1])],
                    seeds=[10101,10202],topologies=['ring','star','complete']))
            for executor in ['deny','permissive_simulator']:
                for case in [0,1]:
                    add('submission_rq3',base(split='evaluation',research_question='rq3',families=['record'],case_indices=[case],
                        seeds=[10101,10202],topologies=['single','complete'],executor=executor,max_model_calls=5))
            jobs.extend(block)
            continue
        for count in SIZES:
            for case in development:
                add('scaling_development',base(protocol_version='2.6',agent_count=count,families=[case.family],
                    case_indices=[int(case.case_id.rsplit('-',1)[1])],seeds=[303],max_model_calls=count*5))
        # Held-out evaluation precedes the separate exploratory scaling screen.
        for family in ['catalog','provenance','patch']:
            for case in range(32):
                add('rq1_evaluation',base(split='evaluation',families=[family],case_indices=[case],seeds=[10101,10202],
                                         topologies=['ring','star','complete']))
        for executor in ['deny','permissive_simulator']:
            for case in range(32):
                add('rq3_evaluation',base(split='evaluation',research_question='rq3',families=['record'],case_indices=[case],
                    seeds=[10101,10202],topologies=['single','complete'],executor=executor,max_model_calls=5))
        jobs.extend(block)
    suite={'schema_version':'1.0','created_utc':utc(),'source_hash':source_fingerprint(),'worker_label':'secondary',
           'judge_model':'llama3.2:latest','judge_digest':'a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72','judge_max_calls':32,
           'max_physical_calls':90000,'max_wall_seconds':72*3600,'planned_calls':sum(j['calls'] for j in jobs),
           'jobs':jobs,'profile':profile,'sizes':SIZES,'models':MODELS,'publication_interval_seconds':300}
    suite['planned_agent_calls']=suite['planned_calls']
    suite['planned_calls']+=len(MODELS)*suite['judge_max_calls']
    suite['suite_hash']=digest(suite)
    write_json(root/'suite.json',suite)
    return suite


def publish(root):
    root=Path(root)
    source=root/'runs'
    if not list(source.rglob('manifest.json')):return
    public=root/'public/data';public.mkdir(parents=True,exist_ok=True)
    snapshot=make_research_snapshot(study_sources=[source],include_text=True,detail_directory=public/'studies',
                                    scenario_index='configs/scenarios_index.json')
    # Preserve already-approved reduced neural evidence; no raw prior tensors copied.
    prior=Path('dashboard/data/research.json')
    for review in (root/'reviews').glob('*/manifest.json'):
        reviewed=make_research_snapshot(review_source=review.parent)
        snapshot.reviews.extend(reviewed.reviews);snapshot.unreviewed_samples+=reviewed.unreviewed_samples
        snapshot.review_source=reviewed.review_source;snapshot.review_model=reviewed.review_model
    if prior.is_file():
        approved=validate_research_snapshot(prior)
        snapshot.neural=approved.neural
        current_ids={r.id for r in snapshot.studies}
        for row in approved.studies:
            if row.id in current_ids:continue
            if row.detail_file:
                original=Path('dashboard')/row.detail_file
                target=root/'public'/row.detail_file
                if original.is_file():
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(original,target)
                    from .research_publication import validate_study_detail
                    detail=validate_study_detail(original)
                    if not detail.omitted_events:row.parse_failures=sum(t.event_type=='parse_failure' for t in detail.traces)
            row.violation_status='observed' if row.violation else 'indeterminate' if row.parse_failures or row.status!='completed' else 'not_observed'
            snapshot.studies.append(row)
    monitor_root=root/'monitor'/str(time.time_ns())
    try:
        result=evaluate_visibility(source,monitor_root,topology=None)
        from .research_publication import MonitorRow
        snapshot.monitor=[MonitorRow(**r) for r in result['summary']]
    except ValueError as exc:
        if str(exc)!='No matching completed catalog RQ1 runs for monitor evaluation':raise
        # No completed catalog trajectory yet; no metrics fabricated.
    # Queue progress and hardware readings are private operator telemetry.
    snapshot.suite=None;snapshot.resources=None
    temp=public/'research.tmp';temp.write_text(snapshot.model_dump_json()+'\n')
    validate_research_snapshot(temp);temp.replace(public/'research.json')
    from .reporting import generate_report
    generate_report(public/'research.json',root/'reports/latest')



async def run(root):
    root=Path(root);suite=json.loads((root/'suite.json').read_text())
    if suite['worker_label']!='secondary' or suite['source_hash']!=source_fingerprint():
        raise ValueError('Suite worker/source mismatch')
    expected=suite['suite_hash'];content={k:v for k,v in suite.items() if k!='suite_hash'}
    if digest(content)!=expected:raise ValueError('Suite schedule changed')
    with (root/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state_path=root/'state.json'
        state=json.loads(state_path.read_text()) if state_path.exists() else {
            'suite_hash':expected,'status':'running','started_utc':utc(),'job_cursor':0,'planned_jobs':len(suite['jobs']),
            'planned_calls':suite['planned_calls'],'physical_calls':0,'completed_runs':0,'failed_runs':0,
            'consecutive_failures':0,'elapsed_seconds':0,'seen_runs':[],'replay_candidates':[],'judged_models':[],'judge_calls':0}
        if state['suite_hash']!=expected:raise ValueError('Suite state mismatch')
        clock=time.monotonic();previous_elapsed=max(state['elapsed_seconds'],(datetime.now(timezone.utc)-datetime.fromisoformat(state['started_utc'])).total_seconds());last_publication=0
        state['status']='running'
        # Recover physical-attempt accounting from flushed raw events, including unfinished attempts.
        recovered_calls=0;recovered_by_path={}
        for event_path in (root/'runs').rglob('events.jsonl'):
            count=0
            with event_path.open() as stream:
                for line in stream:
                    try:item=json.loads(line)
                    except ValueError:break # Keep unfinished logs private; never analyze as sealed results.
                    count+=item.get('event_type')=='http_attempt'
            recovered_by_path[str(event_path.parent.relative_to(root))]=count
            recovered_calls+=count
        state['physical_calls']=max(state['physical_calls'],recovered_calls)
        atomic(state_path,state)
        journal=root/'suite.events.jsonl'
        def event(kind,**metadata):
            with journal.open('a') as stream:stream.write(json.dumps({'timestamp_utc':utc(),'event_type':kind,**metadata})+'\n')
        def observe(path):
            nonlocal last_publication
            marker=str(path.relative_to(root))
            if marker in state['seen_runs']:return
            if not verify(path):raise ValueError('Completed run failed checksum verification')
            manifest=json.loads((path/'manifest.json').read_text());outcome=json.loads((path/'outcome.json').read_text())
            state['seen_runs'].append(marker)
            state['physical_calls']+=max(0,manifest['http_attempts']-recovered_by_path.get(marker,0))
            recovered_by_path[marker]=manifest['http_attempts']
            ok=manifest['status']=='completed'
            state['completed_runs' if ok else 'failed_runs']+=1
            state['consecutive_failures']=0 if ok else state['consecutive_failures']+1
            state['elapsed_seconds']=previous_elapsed+time.monotonic()-clock;state['updated_utc']=utc()
            if outcome['any_violation'] or outcome['attempted_forbidden'] or outcome.get('parse_failures',0):
                events=read_events(path/'events.jsonl')
                ids=[e['event_id'] for e in events if e['event_type']=='parse_failure' or e['event_type']=='artifact' and e['metadata']['score']['violation']]
                state['replay_candidates'].append({'run':marker,'task_case':outcome['task_case'],'evidence_event_ids':ids,
                                                  'reason':'objective_behavior_flag_not_neural_detection' if outcome['any_violation'] else 'invalid_output_candidate_not_neural_detection'})
            atomic(state_path,state);event('run_finished',run=marker,status=manifest['status'],physical_calls=manifest['http_attempts'])
            if time.monotonic()-last_publication>suite['publication_interval_seconds']:
                publish(root);last_publication=time.monotonic()
            if (root/'STOP').exists():raise RuntimeError('operator_stop')
            if state['elapsed_seconds']>=suite['max_wall_seconds']:raise RuntimeError('wall_budget')
            if state['consecutive_failures']>=3:raise RuntimeError('three_consecutive_failed_runs')
        async def watch_resources():
            from .resources import sample,pause_reason,record
            previous=None
            while True:
                data,previous=sample(previous);record(root,data)
                reason=pause_reason(data)
                if reason:
                    atomic(root/'resource-pause.json',{'reason':reason,'observed_utc':utc()})
                    (root/'STOP').write_text(reason)
                    return
                await asyncio.sleep(15)
        class SecondaryProvider(HTTPProvider):
            async def chat(self,messages,config):
                if (root/'STOP').exists():raise CallBudgetExhausted()
                return await super().chat(messages,config)
        watcher=asyncio.create_task(watch_resources())
        async def judge_window(model):
            if not model or model in state.setdefault('judged_models',[]):return
            from .review import review_batch
            state['judged_models'].append(model);atomic(state_path,state)
            judge=HTTPProvider('http://127.0.0.1:11434',timeout=60,retries=0,api='ollama')
            try:
                available=await judge.discover()
                if not any(m.get('name')==suite['judge_model'] and m.get('digest')==suite['judge_digest'] for m in available):
                    event('judge_unavailable',model=suite['judge_model']);return
                judge.identity.update(model=suite['judge_model'],digest=suite['judge_digest'],worker_label='secondary')
                key=model.replace(':','-');directory=root/'reviews'/key
                if (root/'STOP').exists() or state['physical_calls']+suite['judge_max_calls']>suite['max_physical_calls']:return
                remaining=suite['max_wall_seconds']-previous_elapsed-(time.monotonic()-clock)
                result=await asyncio.wait_for(review_batch(root/'runs'/key,directory,judge,suite['judge_model'],suite['judge_max_calls']),timeout=max(.1,remaining))
                state['judge_calls']=state.get('judge_calls',0)+result['reviewed']
                state['physical_calls']+=result['reviewed']
                event('judge_window_completed',target=model,reviewed=result['reviewed'],uncalibrated=True)
            except Exception as exc:event('judge_window_failed',reason=type(exc).__name__)
            finally:await judge.close();atomic(state_path,state)
        provider=None;active=None
        try:
            for job in suite['jobs'][state['job_cursor']:]:
                if (root/'STOP').exists():raise RuntimeError('operator_stop')
                if shutil.disk_usage(root).free<10*2**30:raise RuntimeError('disk_budget')
                if previous_elapsed+time.monotonic()-clock>suite['max_wall_seconds']:raise RuntimeError('wall_budget')
                if state['physical_calls']+job['calls']>suite['max_physical_calls']:raise RuntimeError('call_budget')
                if source_fingerprint()!=suite['source_hash']:raise RuntimeError('source_changed')
                if job['model']!=active:
                    if provider:
                        await provider.close()
                        await judge_window(active)
                    # Fixed loopback endpoint: this runner cannot contact primary or arbitrary targets.
                    provider=SecondaryProvider('http://127.0.0.1:11434',timeout=60,retries=0,api='ollama')
                    installed=await provider.discover()
                    if not any(m.get('name')==job['model'] and m.get('digest')==job['digest'] for m in installed):
                        raise RuntimeError('model_digest_mismatch')
                    provider.identity.update(model=job['model'],digest=job['digest'],worker_label='secondary')
                    active=job['model']
                state.update(current_job=job['index'],current_stage=job['stage'],model=job['model'])
                atomic(state_path,state);event('job_started',index=job['index'],stage=job['stage'],model=job['model'])
                plan=StudyPlan.model_validate_json(Path(job['plan']).read_text())
                remaining=suite['max_wall_seconds']-previous_elapsed-(time.monotonic()-clock)
                await asyncio.wait_for(run_plan(plan,provider,root/'runs'/job['model_key']/f"job-{job['index']:04}",job['freeze'],
                               continue_on_failure=True,on_run=observe),timeout=max(.1,remaining))
                state['job_cursor']=job['index']+1;atomic(state_path,state)
            await judge_window(active)
            state['status']='completed'
        except (Exception,asyncio.CancelledError,KeyboardInterrupt) as exc:
            state['status']='stopped';state['stop_reason']=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
            event('suite_stopped',reason=state['stop_reason'])
        finally:
            watcher.cancel()
            try:await watcher
            except asyncio.CancelledError:pass
            if provider:await provider.close()
            state['elapsed_seconds']=previous_elapsed+time.monotonic()-clock;state['updated_utc']=utc()
            atomic(state_path,state);publish(root)
        return {k:state[k] for k in ['status','physical_calls','completed_runs','failed_runs']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',choices=['extended','deadline'],default='extended')
    parser.add_argument('command',choices=['prepare','run','publish']);parser.add_argument('--root',default='results/secondary-suite')
    args=parser.parse_args()
    try:
        if args.command=='prepare':
            result=prepare(args.root,args.profile);print(json.dumps({'jobs':len(result['jobs']),'planned_calls':result['planned_calls']}))
        elif args.command=='publish':publish(args.root)
        else:print(json.dumps(asyncio.run(run(args.root))))
    except Exception as exc:parser.exit(1,f'Suite operation stopped ({type(exc).__name__}); inspect private state.\n')


if __name__=='__main__':main()
