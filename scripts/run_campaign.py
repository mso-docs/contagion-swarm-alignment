#!/usr/bin/env python3
"""Bounded, durable secondary-only campaigns; one controller, immutable studies."""
import argparse
import asyncio
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit

from contagion.config import digest
from contagion.inference import CallBudgetExhausted, HTTPProvider, MockProvider
from contagion.monitor import evaluate_visibility
from contagion.storage import source_fingerprint, verify
from contagion.studies import StudyPlan, freeze_plan, load_plan, run_plan, verify_freeze
from run_pilot import ROOT, load_env


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        import os
        os.fsync(stream.fileno())
    temporary.replace(path)


def utc():
    return datetime.now(timezone.utc).isoformat()


def controller_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def archive_source():
    import contagion.storage as storage
    source=source_fingerprint();target=ROOT/'results/frozen-sources'/source/'src/contagion'
    target.mkdir(parents=True,exist_ok=True)
    package=Path(storage.__file__).parent
    for path in package.glob('*.py'):
        destination=target/path.name
        if destination.exists() and destination.read_bytes()!=path.read_bytes():raise ValueError('Frozen-source collision')
        if not destination.exists():shutil.copyfile(path,destination)
    observed=digest({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.glob('*.py'))})
    if observed!=source or source_fingerprint()!=source:raise ValueError('Source changed during archival')
    return source


def use_archived_source(root):
    import contagion.storage as storage
    record=json.loads((Path(root)/'campaign.json').read_text());source=record['source_hash']
    frozen=ROOT/'results/frozen-sources'/source/'src'
    if frozen.is_dir() and frozen not in Path(storage.__file__).resolve().parents:
        env=dict(os.environ,PYTHONPATH=str(frozen)+os.pathsep+os.environ.get('PYTHONPATH',''),PYTHONDONTWRITEBYTECODE='1')
        os.execve(sys.executable,[sys.executable,str(Path(__file__).resolve()),*sys.argv[1:]],env)


def prepare(root, plans, provider, expected_digest=None, max_attempts=1000, max_seconds=7200, readiness=None):
    root = Path(root)
    if root.exists():
        raise ValueError('Use a new campaign directory')
    if provider not in {'mock', 'ollama'}:
        raise ValueError('Unsupported campaign backend')
    if provider == 'ollama' and (not expected_digest or len(expected_digest) != 64):
        raise ValueError('Pin the discovered model digest')
    if not plans or len({p.model for p in plans}) != 1:
        raise ValueError('One pinned model per campaign')
    planned = sum((5 if p.research_question=='rq3' else p.agent_count*p.rounds) *
        len(p.families)*len(p.case_indices)*len(p.seeds)*len(p.topologies)*len(p.interventions) for p in plans)
    if any(p.scenario_database for p in plans):
        raise ValueError('Use explicit preselected cases in campaign plans')
    if planned > max_attempts or not 1 <= max_attempts <= 100000 or not 1 <= max_seconds <= 72*3600:
        raise ValueError('Invalid campaign budget')
    # Large or variable-size campaigns require a prior successful compact campaign.
    if planned > 2000 or any(p.agent_count > 5 for p in plans):
        if readiness is None:raise ValueError('Expansion requires validated readiness promotion')
        proof=validate_readiness(readiness)
        if proof['model']!=plans[0].model or proof['model_digest']!=expected_digest:
            raise ValueError('Readiness applies only to its pinned model')
    archive_source()
    root.mkdir(parents=True)
    jobs=[]
    for index, plan in enumerate(plans):
        frozen=root/f'freeze-{index:03}.json'
        record=freeze_plan(plan,frozen)
        jobs.append({'plan':plan.model_dump(),'freeze':frozen.name,'freeze_hash':record['freeze_hash']})
    content={'schema_version':'1.0','source_hash':source_fingerprint(),'controller_hash':controller_hash(),
        'provider':provider,'model':plans[0].model,'model_digest':expected_digest,
        'planned_calls':planned,'max_attempts':max_attempts,'max_wall_seconds':max_seconds,'jobs':jobs,
        'worker_label':'secondary','readiness_hash':validate_readiness(readiness)['readiness_hash'] if readiness else None,'created_utc':utc()}
    content['campaign_hash']=digest(content)
    content['run_root']=str((ROOT/'results/studies'/('campaign-'+content['campaign_hash'][:16])).resolve())
    atomic(root/'campaign.json',content)
    return content


def resource_reason(capacity):
    if capacity.get('available_ram_gib') is None or capacity['available_ram_gib']<4:
        return 'ram_low_or_unknown'
    thermal=capacity.get('gpu_thermal',[])
    if not thermal or any(g.get('temperature_c') is None for g in thermal):
        return 'gpu_temperature_unknown'
    if any(g['temperature_c']>=85 for g in thermal):
        return 'gpu_temperature_high'
    if any(t>=90 for t in capacity.get('cpu_temperature_c',[])):
        return 'cpu_temperature_high'
    return None


def cooling_required(capacity):
    return any(t>=85 for t in capacity.get('cpu_temperature_c',[])) or any(g.get('temperature_c',0)>=80 for g in capacity.get('gpu_thermal',[]))


def cooled(capacity):
    return resource_reason(capacity) is None and all(t<80 for t in capacity.get('cpu_temperature_c',[])) and all(g['temperature_c']<75 for g in capacity.get('gpu_thermal',[]))


async def wait_for_cooling(reader,guard,event,state,save,sleep=asyncio.sleep):
    began=time.monotonic();stable=0
    while True:
        guard(starting_call=False)
        capacity=reader();reason=resource_reason(capacity)
        if reason in {'ram_low_or_unknown','gpu_temperature_unknown'}:raise CallBudgetExhausted(reason)
        if cooled(capacity):stable+=1
        else:stable=0
        if stable>=2:
            state['status']='running';save();event('cooling_complete');return
        if time.monotonic()-began>600:raise CallBudgetExhausted('cooling_timeout')
        state['status']='cooling';save();event('cooling_wait',reason=reason or 'thermal_warning')
        await sleep(10)


def recover(run_root):
    completed=failed=attempts=0
    for event_file in Path(run_root).rglob('events.jsonl'):
        for line in event_file.read_text().splitlines():
            try: event=json.loads(line)
            except ValueError: break  # Unsealed interrupted tail is retained, never repaired.
            attempts+=event.get('event_type')=='http_attempt'
    for path in Path(run_root).rglob('manifest.json'):
        if not verify(path.parent):
            raise ValueError('Corrupt sealed attempt; inspect before resume')
        manifest=json.loads(path.read_text())
        completed+=manifest['status']=='completed'
        failed+=manifest['status']!='completed'
    return {'physical_calls':attempts,'completed_runs':completed,'failed_runs':failed}


async def run(root, env_file=None, ssh_env_file=None, retry_incomplete=False):
    root=Path(root)
    campaign=json.loads((root/'campaign.json').read_text())
    content={k:v for k,v in campaign.items() if k not in {'campaign_hash','run_root'}}
    if digest(content)!=campaign['campaign_hash'] or campaign['source_hash']!=source_fingerprint() or campaign['controller_hash']!=controller_hash():
        raise ValueError('Campaign/source/controller changed; create a fresh freeze')
    run_root=Path(campaign['run_root'])
    if (ROOT/'results/studies').resolve() not in run_root.resolve().parents:
        raise ValueError('Invalid campaign run root')
    for job in campaign['jobs']:
        verify_freeze(StudyPlan(**job['plan']),root/job['freeze'])
    root.mkdir(parents=True,exist_ok=True)
    global_lock=ROOT/'results/checkpoint-gates/controller.lock'
    global_lock.parent.mkdir(parents=True,exist_ok=True)
    with global_lock.open('a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state_path=root/'state.json'
        state=json.loads(state_path.read_text()) if state_path.exists() else {'started_utc':utc(),'job_cursor':0}
        if state.get('campaign_hash',campaign['campaign_hash'])!=campaign['campaign_hash']:
            raise ValueError('Campaign state mismatch')
        state.update(recover(run_root),campaign_hash=campaign['campaign_hash'],status='running',updated_utc=utc())
        interrupted=any(not (p.parent/'checksum.sha256').is_file() for p in run_root.rglob('config.snapshot.json'))
        if (interrupted or state['failed_runs']) and not retry_incomplete:
            raise ValueError('Incomplete/failed attempts require explicit --retry-incomplete; originals remain retained')
        started=datetime.fromisoformat(state['started_utc']).timestamp()
        last_capacity=0
        provider=None
        def save():state.update(updated_utc=utc());atomic(state_path,state)
        def event(kind,**extra):
            with (root/'journal.jsonl').open('a') as stream:
                stream.write(json.dumps({'timestamp_utc':utc(),'event_type':kind,**extra})+'\n');stream.flush()
        def guard(starting_call=True):
            if (root/'STOP').exists():raise CallBudgetExhausted('operator_stop')
            if time.time()-started>=campaign['max_wall_seconds']:raise CallBudgetExhausted('wall_budget')
            if starting_call and state['physical_calls']>=campaign['max_attempts']:raise CallBudgetExhausted('call_budget')
            if shutil.disk_usage(root).free<5*2**30:raise CallBudgetExhausted('disk_headroom')
            if source_fingerprint()!=campaign['source_hash']:raise CallBudgetExhausted('source_changed')
        class Provider(HTTPProvider):
            async def chat(self,messages,config):
                nonlocal last_capacity
                guard()
                if time.monotonic()-last_capacity>=10:
                    from remote_worker import execute
                    def read_capacity():
                        found=execute('secondary','capacity',ssh_env_file or ROOT/'.env')
                        return next(m['capacity'] for m in found if 'capacity' in m)
                    capacity=read_capacity();reason=resource_reason(capacity)
                    if reason or cooling_required(capacity):
                        await wait_for_cooling(read_capacity,guard,event,state,save)
                    last_capacity=time.monotonic()
                state['physical_calls']+=1;save()
                return await super().chat(messages,config)
        try:
            if campaign['provider']=='mock':
                provider=MockProvider()
            else:
                import os
                env=load_env(Path(env_file or ROOT/'.env.secondary'),dict(os.environ))
                parsed=urlsplit(env.get('CONTAGION_BASE_URL',''))
                if (parsed.scheme,parsed.hostname,parsed.port,parsed.path,parsed.query,parsed.fragment,parsed.username,parsed.password)!=('http','127.0.0.1',11834,'','','',None,None):
                    raise ValueError('Only the secondary loopback tunnel is permitted')
                provider=Provider(env['CONTAGION_BASE_URL'],api='ollama',retries=0,timeout=60)
                installed=await provider.discover()
                if not any(m.get('name')==campaign['model'] and m.get('digest')==campaign['model_digest'] for m in installed):
                    raise ValueError('Pinned model digest mismatch')
            provider.identity.update(model=campaign['model'],worker_label='secondary')
            if campaign['model_digest']:provider.identity['digest']=campaign['model_digest']
            save();event('campaign_started',retry_incomplete=retry_incomplete)
            def on_run(path):
                if not verify(path):raise ValueError('Run integrity gate failed')
                manifest=json.loads((path/'manifest.json').read_text());outcome=json.loads((path/'outcome.json').read_text())
                state.update(recover(run_root));save()
                event('run_sealed',run_id=path.name,status=manifest['status'],parse_failures=manifest['parse_failures'])
                if manifest['status']!='completed' or manifest['parse_failures']:
                    raise RuntimeError('run_validity_gate')
                # Valid task failures and intervention-induced violations are scientific observations.
                print(json.dumps({'run_status':manifest['status'],'responses':manifest['completed_model_calls'],
                    'parse_failures':manifest['parse_failures'],'task_success':outcome['task_success_rate'],
                    'observed_violation':outcome['any_violation']}),flush=True)
                guard(starting_call=False)
            for index,job in enumerate(campaign['jobs'][state['job_cursor']:],start=state['job_cursor']):
                guard();state['current_job']=index;save()
                await run_plan(StudyPlan(**job['plan']),provider,run_root/f'job-{index:03}',root/job['freeze'],on_run=on_run)
                state['job_cursor']=index+1;save()
            state['status']='completed';save();event('campaign_completed')
            # Offline analysis is distinct from inference; preserve undefined recall.
            target=root/'monitor';target.mkdir(exist_ok=True)
            results=[]
            for mask_seed in [404,505,606]:
                child=target/f'seed-{mask_seed}'
                if (child/'monitor.json').is_file():
                    results.append(json.loads((child/'monitor.json').read_text()));continue
                try:
                    results.append(evaluate_visibility(run_root,child,topology=None,seed=mask_seed))
                except ValueError as exc:
                    if str(exc)!='No matching completed catalog RQ1 runs for monitor evaluation':raise
            if results:
                combined={**results[0],'monitor_seeds':[404,505,606],
                    'observations':[r for result in results for r in result['observations']],
                    'summary':[r for result in results for r in result['summary']]}
                atomic(target/'monitor.json',combined)
                event('monitor_completed',projections=len(combined['observations']))
            return state
        except BaseException as exc:
            state.update(status='stopped',stop_reason=type(exc).__name__);save();event('campaign_stopped',reason=type(exc).__name__)
            raise
        finally:
            if provider is not None and hasattr(provider,'close'):await provider.close()


def validate_readiness(path):
    proof=json.loads(Path(path).read_text())
    if digest({k:v for k,v in proof.items() if k!='readiness_hash'})!=proof['readiness_hash'] or proof['source_hash']!=source_fingerprint():
        raise ValueError('Readiness/source changed')
    for filename,want in proof['evidence_hashes'].items():
        file=Path(filename).resolve()
        if (ROOT/'results').resolve() not in file.parents or file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest()!=want:
            raise ValueError('Readiness evidence changed')
    return proof


def promote(campaign_root,development_root,neural_roots,output):
    from checkpoint_gate import check_run
    from contagion.neural import validate_numeric_capture
    root=Path(campaign_root);campaign=json.loads((root/'campaign.json').read_text());state=json.loads((root/'state.json').read_text())
    if state['status']!='completed' or state['campaign_hash']!=campaign['campaign_hash'] or campaign['source_hash']!=source_fingerprint():
        raise ValueError('Compact campaign is not complete under current source')
    if campaign['provider']!='ollama' or campaign['planned_calls']<150 or not (root/'monitor/monitor.json').is_file():
        raise ValueError('Live compact RQ1 and offline monitor evidence required')
    evidence=[root/'campaign.json',root/'state.json',root/'monitor/monitor.json']
    from campaign_evidence import compact_evidence
    compact_files,reliability=compact_evidence(campaign)
    evidence.extend(compact_files)
    development_root=Path(development_root);development=json.loads((development_root/'status.json').read_text())
    if development['status']!='completed' or len(development['completed_batches'])!=5:
        raise ValueError('All five development checkpoints are required')
    evidence.append(development_root/'status.json')
    for batch in development['completed_batches']:
        study=ROOT/'results/studies'/('gated-'+development_root.name+'-'+batch['batch'])
        paths=list(study.rglob('manifest.json'))
        if len(paths)!=batch['runs']:raise ValueError('Development evidence missing')
        for path in paths:
            check_run(path.parent)
            evidence.extend(path.parent/n for n in ['manifest.json','config.snapshot.json','events.jsonl','outcome.json','checksum.sha256'])
    trained=0;usable=False
    for neural in map(Path,neural_roots):
        checks=json.loads((neural/'checksums.json').read_text())
        if set(checks)!={'capture.json','private_inputs.json','activations.safetensors'}:raise ValueError('Neural seal incomplete')
        for name,want in checks.items():
            if hashlib.sha256((neural/name).read_bytes()).hexdigest()!=want:raise ValueError('Neural evidence corrupted')
        data=validate_numeric_capture(json.loads((neural/'capture.json').read_text()));p=data['patch']
        if data['evidence_type']!='instrumented_checkpoint_replay' or not data.get('validation',{}).get('raw_bridge_parity_passed'):
            raise ValueError('Trained checkpoint parity evidence required')
        if abs(p['noop_target_logit']-p['corrupt_target_logit'])>1e-5 or abs(p['position_control_logit']-p['corrupt_target_logit'])>1e-5:
            raise ValueError('Neural control failed')
        usable|=abs(p['clean_target_logit']-p['corrupt_target_logit'])>=1e-4
        trained+=1;evidence.extend(neural/n for n in [*checks,'checksums.json'])
    if trained<2 or not usable:raise ValueError('Replicated trained controls with a usable gap are required')
    output=Path(output)
    if output.exists():raise ValueError('Use a fresh readiness proof path')
    output.parent.mkdir(parents=True,exist_ok=True)
    with (output.parent/'readiness-tests.private.log').open('w') as log:
        subprocess.run([sys.executable,'-m','pytest','-q'],cwd=ROOT,stdout=log,stderr=log,check=True)
        subprocess.run([sys.executable,'scripts/check_all.py'],cwd=ROOT,stdout=log,stderr=log,check=True)
    evidence.append(output.parent/'readiness-tests.private.log')
    proof={'schema_version':'1.1','source_hash':source_fingerprint(),'model':campaign['model'],'model_digest':campaign['model_digest'],
        'compact_campaign_hash':campaign['campaign_hash'],'trained_captures':trained,'created_utc':utc(),
        'reliability':reliability,
        'scope':'Operational readiness for this pinned model/source; not alignment or mechanistic certification.',
        'evidence_hashes':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence}}
    proof['readiness_hash']=digest(proof);atomic(output,proof)
    return proof


def amend_thermal_controller(root):
    root=Path(root);campaign=json.loads((root/'campaign.json').read_text());state=json.loads((root/'state.json').read_text())
    if state['status']!='stopped' or campaign['source_hash']!=source_fingerprint():raise ValueError('Only a stopped unchanged study can be amended')
    content={k:v for k,v in campaign.items() if k not in {'campaign_hash','run_root'}}
    if digest(content)!=campaign['campaign_hash']:raise ValueError('Original campaign changed')
    for job in campaign['jobs']:verify_freeze(StudyPlan(**job['plan']),root/job['freeze'])
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    shutil.copyfile(root/'campaign.json',root/f'campaign.before-thermal-{stamp}.json')
    shutil.copyfile(root/'state.json',root/f'state.before-thermal-{stamp}.json')
    previous=campaign['campaign_hash'];campaign['controller_hash']=controller_hash()
    campaign.setdefault('controller_amendments',[]).append({'previous_campaign_hash':previous,'reason':'thermal-duty-cycle',
        'created_utc':utc(),'policy':'Read sensors every10s; no inference during cooling; resume after two samples CPU<80 and GPU<75; stop after600s. No safety limit raised.'})
    campaign['campaign_hash']=digest({k:v for k,v in campaign.items() if k not in {'campaign_hash','run_root'}})
    state['campaign_hash']=campaign['campaign_hash'];atomic(root/'campaign.json',campaign);atomic(root/'state.json',state)
    with (root/'journal.jsonl').open('a') as stream:stream.write(json.dumps({'timestamp_utc':utc(),'event_type':'controller_amended','previous_campaign_hash':previous,'campaign_hash':campaign['campaign_hash']})+'\n')
    return campaign


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    prepare_cli=commands.add_parser('prepare')
    prepare_cli.add_argument('--root',type=Path,required=True)
    prepare_cli.add_argument('--config',type=Path,action='append',required=True)
    prepare_cli.add_argument('--provider',choices=['mock','ollama'],default='mock')
    prepare_cli.add_argument('--expected-digest')
    prepare_cli.add_argument('--max-attempts',type=int,default=1000)
    prepare_cli.add_argument('--max-seconds',type=int,default=7200)
    prepare_cli.add_argument('--readiness',type=Path)
    promote_cli=commands.add_parser('promote');promote_cli.add_argument('--root',type=Path,required=True)
    promote_cli.add_argument('--development',type=Path,required=True);promote_cli.add_argument('--neural',type=Path,action='append',required=True)
    promote_cli.add_argument('--out',type=Path,required=True)
    amend_cli=commands.add_parser('amend-thermal');amend_cli.add_argument('--root',type=Path,required=True)
    run_cli=commands.add_parser('run');run_cli.add_argument('--root',type=Path,required=True)
    run_cli.add_argument('--env-file',type=Path);run_cli.add_argument('--ssh-env-file',type=Path)
    run_cli.add_argument('--retry-incomplete',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='prepare':
            result=prepare(args.root,[load_plan(p) for p in args.config],args.provider,args.expected_digest,args.max_attempts,args.max_seconds,args.readiness)
            print(f'Frozen campaign: {len(result["jobs"])} study blocks, {result["planned_calls"]} scheduled responses.')
        elif args.command=='amend-thermal':
            use_archived_source(args.root)
            amend_thermal_controller(args.root);print('Archived thermal pacing amendment; study prompts, seeds, scores and original attempts unchanged.')
        elif args.command=='promote':
            proof=promote(args.root,args.development,args.neural,args.out)
            print('Readiness promotion sealed for one pinned model/source.')
        else:
            use_archived_source(args.root)
            result=asyncio.run(run(args.root,args.env_file,args.ssh_env_file,args.retry_incomplete))
            print('Campaign status:',result['status'])
    except Exception as exc:
        parser.exit(1,f'Campaign stopped ({type(exc).__name__}); inspect private state/journal. No private values printed.\n')


if __name__=='__main__':main()
