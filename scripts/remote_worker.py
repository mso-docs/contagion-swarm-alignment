#!/usr/bin/env python3
"""Operator-driven private SSH preflight/install, separate from model agents."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

from run_pilot import ROOT, load_env

REMOTE = r'''
import base64,hashlib,io,json,os,pathlib,platform,shlex,shutil,subprocess,sys,tarfile,time
request=json.load(sys.stdin)
base=pathlib.Path(request['project']).expanduser()
if not base.is_absolute() or base==pathlib.Path('/') or '..' in base.parts:raise ValueError('Unsafe project path')
probe=base
while not probe.exists():probe=probe.parent
result={'system':platform.system(),'architecture':platform.machine(),'python':platform.python_version(),
        'free_disk_gib':round(shutil.disk_usage(probe).free/2**30,1),
        'project_exists':base.exists(),'docker_available':shutil.which('docker') is not None,
        'nvidia_smi_available':shutil.which('nvidia-smi') is not None}
try:result['memory_gib']=round(os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')/2**30,1)
except (ValueError,OSError,AttributeError):result['memory_gib']=None
if request['action']=='preflight' and shutil.which('systemctl'):
    service=subprocess.run(['systemctl','show','ollama','--property=Environment','--value'],capture_output=True,text=True,timeout=5)
    allowed_settings={'OLLAMA_NUM_PARALLEL','OLLAMA_MAX_QUEUE','OLLAMA_MAX_LOADED_MODELS','OLLAMA_CONTEXT_LENGTH'}
    result['ollama_explicit_settings']={}
    if service.returncode==0:
        for item in shlex.split(service.stdout):
            key,separator,value=item.partition('=')
            if separator and key in allowed_settings and value.isdigit():result['ollama_explicit_settings'][key]=int(value)
print(json.dumps(result),flush=True)
if request['action']=='suite-diagnose':
    root=sorted(base.glob('suite-*'))[-1]/'contagion-worker'
    failures=[]
    for manifest in (root/'results/secondary-suite/runs').rglob('manifest.json'):
        info=json.loads(manifest.read_text())
        if info['status']=='completed':continue
        events=[json.loads(line) for line in (manifest.parent/'events.jsonl').read_text().splitlines()]
        for e in events:
            if e['event_type']!='parse_failure':continue
            content=e.get('content','');detail={'characters':len(content),'round':e['round'],
                'starts_code_fence':content.lstrip().startswith('```'),'ends_json_object':content.rstrip().endswith('}')}
            try:
                parsed=json.loads(content);detail['json_type']=type(parsed).__name__
                if isinstance(parsed,dict):detail['keys']=[str(k)[:50] for k in parsed][:10]
            except ValueError as exc:
                detail['json_error']=exc.msg;detail['error_position']=exc.pos
            response=next((r for r in reversed(events[:events.index(e)]) if r['event_type']=='inference_response'),{})
            detail['finish_reason']=response.get('metadata',{}).get('done_reason')
            failures.append(detail)
    print(json.dumps({'diagnostic':json.dumps({'parse_failures':failures})}),flush=True)
    sys.exit(0)
if request['action']=='trained-fetch':
    root=sorted(base.glob('trained-*'))[-1]/'contagion-worker'
    info=json.loads((root/'trained-process.json').read_text());directory=root/info.get('output','results/trained-pilot')
    status=json.loads((directory/'pilot-status.json').read_text())
    for row in status.get('completed',[]):
        capture=directory/row['capture'];checks=capture/'checksums.json'
        name='trained-'+hashlib.sha256(checks.read_bytes()).hexdigest()[:16]+'-'+row['capture']
        if name in request.get('known_captures',[]):continue
        names=['capture.json','private_inputs.json','activations.safetensors','checksums.json']
        if sum((capture/n).stat().st_size for n in names)>32*1024*1024:raise ValueError('Trained capture transfer cap')
        print(json.dumps({'capture_name':name,'capture_bundle':{n:base64.b64encode((capture/n).read_bytes()).decode() for n in names}}),flush=True)
        sys.exit(0)
    print(json.dumps({'phase':'trained_captures_synced','neural_captures':len(status.get('completed',[]))}),flush=True);sys.exit(0)
if request['action']=='trained-retry':
    root=sorted(base.glob('trained-*'))[-1]/'contagion-worker'
    for key,name in [('module','src/contagion/neural.py'),('pilot','scripts/trained_interp_pilot.py')]:
        source=request[key+'_source'].encode()
        if hashlib.sha256(source).hexdigest()!=request[key+'_sha256']:raise ValueError('Retry source hash mismatch')
        target=root/name;shutil.copyfile(target,target.with_suffix('.before-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())));target.write_bytes(source)
    output='results/trained-retry-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    previous=sorted(base.glob('neural-*'))[-1]/'contagion-worker/.venv-interp/bin/python'
    with (root/'trained.private.log').open('a') as log:
        process=subprocess.Popen([str(previous),'scripts/trained_interp_pilot.py','--out',output,'--cache-directory','results/trained-pilot/hf-cache'],
            cwd=root,env=dict(os.environ,PYTHONPATH=str(root/'src')),stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True)
    (root/'trained-process.json').write_text(json.dumps({'pid':process.pid,'output':output}))
    print(json.dumps({'phase':'trained_pilot_retry_started','pid':process.pid}),flush=True);sys.exit(0)
if request['action']=='trained-diagnose':
    root=sorted(base.glob('trained-*'))[-1]/'contagion-worker'
    info=json.loads((root/'trained-process.json').read_text());failure=root/info.get('output','results/trained-pilot')/'failure.private.json'
    diagnostic=failure.read_text()[-12000:] if failure.exists() else '\n'.join((root/'trained.private.log').read_text().splitlines()[-35:])
    print(json.dumps({'diagnostic':diagnostic}),flush=True)
    sys.exit(0)
if request['action']=='trained-status':
    root=sorted(base.glob('trained-*'))[-1]/'contagion-worker'
    info=json.loads((root/'trained-process.json').read_text())
    status=root/info.get('output','results/trained-pilot')/'pilot-status.json'
    running=(pathlib.Path('/proc')/str(info['pid'])/'cmdline').exists()
    completed=0;phase='running' if running else 'stopped'
    if status.exists():
        value=json.loads(status.read_text());completed=len(value.get('completed',[]));phase=value['status'] if value['status']=='completed' else phase
    print(json.dumps({'phase':phase,'neural_captures':completed}),flush=True)
    sys.exit(0)
if request['action']=='suite-pause':
    release=sorted(base.glob('suite-*'))[-1]/'contagion-worker'
    (release/'results/secondary-suite/STOP').write_text('submission_deadline_priority')
    print(json.dumps({'phase':'pause_requested_after_current_run'}),flush=True)
    sys.exit(0)
if request['action']=='suite-status':
    releases=sorted(base.glob('suite-*'))
    if not releases:raise ValueError('No secondary suite deployed')
    root=releases[-1]/'contagion-worker'
    state=json.loads((root/'results/secondary-suite/state.json').read_text())
    keys=['status','planned_calls','physical_calls','completed_runs','failed_runs','current_job','current_stage','model','elapsed_seconds','updated_utc','started_utc','stop_reason','job_cursor','planned_jobs']
    progress={k:state[k] for k in keys if k in state}
    suite_root=root/'results/secondary-suite'
    suite=json.loads((suite_root/'suite.json').read_text())
    planned_runs=0
    for job in suite['jobs']:
        plan=json.loads((root/job['plan']).read_text())
        per_run=5 if plan['research_question']=='rq3' else plan['agent_count']*plan['rounds']
        planned_runs+=job['calls']//per_run
    progress.update(planned_runs=planned_runs,recorded_run_seconds=0,measured_calls=0,unsealed_runs=0)
    for config in (suite_root/'runs').rglob('config.snapshot.json'):
        if not (config.parent/'checksum.sha256').is_file():progress['unsealed_runs']+=1
    for path in (suite_root/'runs').rglob('manifest.json'):
        if not (path.parent/'checksum.sha256').is_file():continue
        manifest=json.loads(path.read_text())
        progress['recorded_run_seconds']+=max(0,manifest.get('duration_seconds',0))
        progress['measured_calls']+=max(0,manifest.get('completed_model_calls',0))
    print(json.dumps({'suite_status':progress}),flush=True)
    sys.exit(0)
if request['action']=='suite-sync':
    releases=sorted(base.glob('suite-*'))
    if not releases:raise ValueError('No suite release')
    root=releases[-1]/'contagion-worker'
    public=root/'results/secondary-suite/public'
    if not (public/'data/research.json').is_file():
        print(json.dumps({'phase':'waiting_for_first_completed_run'}),flush=True);sys.exit(0)
    known=request.get('known_files',{})
    payload={};size=0
    paths=[public/'data/research.json']+sorted((public/'data/studies').glob('*.json'))
    import re
    for path in paths:
        name=str(path.relative_to(public))
        if name!='data/research.json' and not re.fullmatch(r'data/studies/[a-f0-9]{16}\.json',name):raise ValueError('Unapproved public path')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()==known.get(name):continue
        if len(data)>5*1024*1024:raise ValueError('Public file exceeds publication cap')
        if size+len(data)>12*1024*1024:break
        payload[name]=base64.b64encode(data).decode();size+=len(data)
    print(json.dumps({'public_files':payload}),flush=True)
    sys.exit(0)
if request['action']=='capacity':
    import urllib.request
    available={}
    for line in pathlib.Path('/proc/meminfo').read_text().splitlines():
        key,_,value=line.partition(':')
        if key=='MemAvailable':available['available_ram_gib']=round(int(value.split()[0])/2**20,1)
    available['cpu_count']=os.cpu_count()
    available['load_average']=list(os.getloadavg())
    available['cpu_temperature_c']=[]
    available['thermal_sensors']=[]
    for zone in pathlib.Path('/sys/class/hwmon').glob('hwmon*/temp*_input'):
        try:
            value=float(zone.read_text().strip())/1000
            if 0<value<150:
                available['cpu_temperature_c'].append(value)
                prefix=zone.name.removesuffix('_input')
                sensor={'chip':(zone.parent/'name').read_text().strip() if (zone.parent/'name').exists() else 'unknown','temperature_c':value}
                for suffix in ['label','max','crit']:
                    path=zone.parent/(prefix+'_'+suffix)
                    if path.exists():
                        raw=path.read_text().strip();sensor[suffix]=raw if suffix=='label' else float(raw)/1000
                available['thermal_sensors'].append(sensor)
        except (OSError,ValueError):pass
    available['gpu']=[]
    available['gpu_thermal']=[]
    if shutil.which('nvidia-smi'):
        query=subprocess.run(['nvidia-smi','--query-gpu=temperature.gpu,fan.speed,power.draw,power.limit','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10)
        if query.returncode==0:
            for line in query.stdout.splitlines():
                parts=[v.strip() for v in line.split(',')]
                if len(parts)==4:available['gpu_thermal'].append(dict(zip(['temperature_c','fan_percent','power_watts','power_limit_watts'],[float(v) if v.replace('.','',1).isdigit() else None for v in parts])))
    if shutil.which('nvidia-smi'):
        query=subprocess.run(['nvidia-smi','--query-gpu=memory.total,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10)
        if query.returncode==0:
            for line in query.stdout.splitlines():
                parts=[v.strip() for v in line.split(',')]
                if len(parts)==3:available['gpu'].append(dict(zip(['memory_total_mib','memory_used_mib','utilization_percent'],[float(v) if v.replace('.','',1).isdigit() else None for v in parts])))
    available['ollama_reachable']=False
    available['installed_models']=[];available['loaded_models']=[]
    try:
        for route,field in [('tags','installed_models'),('ps','loaded_models')]:
            with urllib.request.urlopen('http://127.0.0.1:11434/api/'+route,timeout=3) as response:
                data=json.loads(response.read(1024*1024))
            available['ollama_reachable']=True
            available[field]=[{k:m.get(k) for k in ['name','digest','size','size_vram','context_length'] if k in m} for m in data.get('models',[])][:100]
    except Exception:pass
    print(json.dumps({'capacity':available}),flush=True)
    sys.exit(0)
if request['action']=='preflight':sys.exit(0)
if request['action']=='fetch':
    root=sorted(base.glob('neural-*'))[-1]/'contagion-worker'
    captures=sorted(path.parent for path in (root/'results').glob('neural-smoke*/checksums.json'))
    if not captures:raise ValueError('No complete capture')
    directory=captures[-1]
    names=['capture.json','private_inputs.json','activations.safetensors','checksums.json']
    if sum((directory/name).stat().st_size for name in names)>8*1024*1024:raise ValueError('Capture transfer cap')
    print(json.dumps({'capture_name':directory.name,'capture_bundle':{name:base64.b64encode((directory/name).read_bytes()).decode() for name in names}}),flush=True)
    sys.exit(0)
if request['action']=='api':
    root=sorted(base.glob('neural-*'))[-1]/'contagion-worker'
    snippets=[]
    for path in (root/'.venv-interp/lib').glob('python*/site-packages/transformer_lens/**/*.py'):
        text=path.read_text()
        for name in ['def get_tokenizer_with_bos(', 'def setup_tokenizer(']:
            pos=text.find(name)
            if pos>=0:snippets.append(text[pos:pos+6500])
    print(json.dumps({'diagnostic':'\n'.join(snippets)}),flush=True)
    sys.exit(0)
if request['action']=='smoke':
    root=sorted(base.glob('neural-*'))[-1]/'contagion-worker'
    if request.get('module_source'):
        module=root/'src/contagion/neural.py'
        source=request['module_source'].encode()
        if hashlib.sha256(source).hexdigest()!=request['module_sha256']:raise ValueError('Capture source hash mismatch')
        backup=module.with_suffix('.py.before-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
        if module.read_bytes()!=source:
            shutil.copyfile(module,backup);module.write_bytes(source)
    capture_name='neural-smoke-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    with (root/'neural-install.private.log').open('a') as log:
        subprocess.run([str(root/'.venv-interp/bin/python'),'-c',
          "from contagion.neural import capture; capture("+repr('results/'+capture_name)+")"],cwd=root,stdout=log,stderr=log,check=True,timeout=180)
    print(json.dumps({'phase':'capture_complete','capture_name':capture_name}),flush=True)
    sys.exit(0)
if request['action']=='diagnose':
    releases=sorted(base.glob('neural-*'))
    if not releases:raise ValueError('No worker release')
    log=releases[-1]/'contagion-worker/neural-install.private.log'
    print(json.dumps({'diagnostic':'\n'.join(log.read_text().splitlines()[-45:])}),flush=True)
    sys.exit(0)
if sys.platform!='linux' or sys.version_info<(3,11):raise ValueError('Linux/Python>=3.11 required')
if result['free_disk_gib']<8:raise ValueError('At least 8GiB free disk required for dependency installation')
blob=base64.b64decode(request['bundle'],validate=True)
if hashlib.sha256(blob).hexdigest()!=request['sha256']:raise ValueError('Bundle digest mismatch')
release=base/(('trained-' if request['action']=='trained-pilot' else 'suite-' if request['action']=='deploy-suite' else 'neural-')+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+request['sha256'][:8])
release.mkdir(parents=True,exist_ok=False,mode=0o700)
with tarfile.open(fileobj=io.BytesIO(blob),mode='r:gz') as archive:
    for member in archive.getmembers():
        p=pathlib.PurePosixPath(member.name)
        if p.is_absolute() or '..' in p.parts or not member.isfile():raise ValueError('Unexpected archive member')
    archive.extractall(release,filter='data')
root=release/'contagion-worker'
manifest=json.loads((root/'worker-manifest.json').read_text())
for name,want in manifest['files'].items():
    p=pathlib.PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe manifest entry')
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=want:raise ValueError('Source checksum mismatch')
if request['action']=='trained-pilot':
    previous=sorted(base.glob('neural-*'))
    if not previous:raise ValueError('An isolated CPU environment is required')
    interpreter=previous[-1]/'contagion-worker/.venv-interp/bin/python'
    env=dict(os.environ,PYTHONPATH=str(root/'src'))
    with (root/'trained.private.log').open('x') as log:
        process=subprocess.Popen([str(interpreter),'scripts/trained_interp_pilot.py','--out','results/trained-pilot','--allow-download'],
            cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True)
    (root/'trained-process.json').write_text(json.dumps({'pid':process.pid}))
    print(json.dumps({'phase':'trained_pilot_started','pid':process.pid,'release_name':release.name}),flush=True)
    sys.exit(0)
if request['action']=='deploy-suite':
    previous=sorted(base.glob('neural-*'))
    if not previous:raise ValueError('A validated isolated secondary environment is required')
    interpreter=previous[-1]/'contagion-worker/.venv-interp/bin/python'
    if not interpreter.is_file():raise ValueError('Secondary interpreter missing')
    for existing in base.glob('suite-*/contagion-worker/suite-process.json'):
        info=json.loads(existing.read_text())
        cmd=pathlib.Path('/proc')/str(info['pid'])/'cmdline'
        if cmd.exists() and b'contagion.suite' in cmd.read_bytes():raise ValueError('A suite worker is already active')
    env=dict(os.environ,PYTHONPATH=str(root/'src'))
    with (root/'suite.private.log').open('x') as log:
        subprocess.run([str(interpreter),'-m','contagion.suite','prepare','--profile','deadline'],cwd=root,env=env,stdout=log,stderr=log,check=True,timeout=60)
        plan=json.loads((root/'results/secondary-suite/suite.json').read_text())
        process=subprocess.Popen([str(interpreter),'-m','contagion.suite','run'],cwd=root,env=env,
            stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True)
    (root/'suite-process.json').write_text(json.dumps({'pid':process.pid,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}))
    print(json.dumps({'phase':'suite_started','pid':process.pid,'planned_calls':plan['planned_calls'],'jobs':len(plan['jobs'])}),flush=True)
    sys.exit(0)
capture_name='neural-smoke-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
print(json.dumps({'phase':'installing_isolated_cpu_worker','release_name':release.name}),flush=True)
with (root/'neural-install.private.log').open('x') as log:
    subprocess.run([sys.executable,'scripts/setup_interpretability.py'],cwd=root,stdout=log,stderr=log,check=True,timeout=1500)
    python=root/'.venv-interp/bin/python'
    print(json.dumps({'phase':'capturing_random_weight_smoke'}),flush=True)
    subprocess.run([str(python),'scripts/capture_neural.py','--mode','random-smoke','--out','results/'+capture_name],
                   cwd=root,stdout=log,stderr=log,check=True,timeout=180)
    subprocess.run([str(python),'scripts/export_research.py','--neural','results/'+capture_name,'--out','results/neural-public.json'],
                   cwd=root,stdout=log,stderr=log,check=True,timeout=60)
print(json.dumps({'phase':'completed','evidence_type':'random_weight_smoke',
                 'release_name':release.name,'capture_name':capture_name,'neural_captures':1}),flush=True)
'''


def configuration(env_file, server):
    env=load_env(env_file,os.environ)
    prefix=server.upper()
    target=env.get(prefix+'_SERVER_ID','')
    project=env.get(prefix+'_PROJECT_DIR','')
    if not target or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.@:-]*',target):
        raise ValueError('Set a valid SSH alias/user@host in the private server ID field')
    if not project or not(project.startswith('/') or project.startswith('~/')) or '..' in Path(project).parts or project=='/':
        raise ValueError('Set an absolute or ~/ project directory in private configuration')
    return target,project


def execute(server,action,env_file,bundle=None,public_target=None):
    import hashlib
    if action in {'deploy-suite','suite-status','suite-sync','suite-pause','suite-diagnose','trained-pilot','trained-status','trained-diagnose','trained-retry','trained-fetch'} and server!='secondary':
        raise ValueError('Suite operations are restricted to the secondary server')
    public_root=Path(public_target).resolve() if public_target else ROOT/'dashboard'
    if public_target and (action!='suite-sync' or (ROOT/'results').resolve() not in public_root.parents):
        raise ValueError('Alternate sync targets must be private results subdirectories')
    target,project=configuration(env_file,server)
    payload={'action':action,'project':project}
    if action in {'install','deploy-suite','trained-pilot'}:
        if not bundle:raise ValueError('Installation needs a reviewed source bundle')
        blob=Path(bundle).read_bytes()
        if len(blob)>20*1024*1024:raise ValueError('Bundle exceeds fixed transfer cap')
        payload.update(bundle=base64.b64encode(blob).decode(),sha256=hashlib.sha256(blob).hexdigest())
    if action=='trained-fetch':
        payload['known_captures']=[p.name.removeprefix('secondary-') for p in (ROOT/'results/neural').glob('secondary-trained-*') if p.is_dir()]
    if action=='trained-retry':
        for key,name in [('module','src/contagion/neural.py'),('pilot','scripts/trained_interp_pilot.py')]:
            source=(ROOT/name).read_text();payload[key+'_source']=source;payload[key+'_sha256']=hashlib.sha256(source.encode()).hexdigest()
    if action=='smoke':
        source=(ROOT/'src/contagion/neural.py').read_text()
        payload.update(module_source=source,module_sha256=hashlib.sha256(source.encode()).hexdigest())
    if action=='suite-sync':
        payload['known_files']={str(p.relative_to(public_root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (public_root/'data/studies').glob('*.json')}
    command=['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10',
             target,'python3 -c '+shlex.quote(REMOTE)]
    result=subprocess.run(command,input=json.dumps(payload),capture_output=True,text=True,timeout=1800 if action in {'install','deploy-suite','trained-pilot'} else 210 if action=='smoke' else 30)
    # Never echo SSH banners, authentication errors or package installer diagnostics.
    messages=[]
    allowed={'system','architecture','python','free_disk_gib','project_exists','docker_available','nvidia_smi_available',
             'memory_gib','pid','planned_calls','jobs','suite_status','capacity','ollama_explicit_settings','diagnostic','capture_name','phase','evidence_type','release_name','neural_captures'}
    for line in result.stdout.splitlines():
        try:value=json.loads(line)
        except ValueError:continue
        if isinstance(value,dict) and set(value)=={'public_files'}:
            from contagion.research_publication import validate_research_snapshot,validate_study_detail
            files=value['public_files'];decoded={k:base64.b64decode(v,validate=True) for k,v in files.items()}
            if sum(map(len,decoded.values()))>12*1024*1024:raise ValueError('Public transfer exceeds cap')
            staged=[]
            for name,data in decoded.items():
                if name!='data/research.json' and not re.fullmatch(r'data/studies/[a-f0-9]{16}\.json',name):raise ValueError('Unapproved public filename')
                if name=='data/research.json':
                    public=json.loads(data);public['suite']=None;public['resources']=None
                    data=json.dumps(public).encode()
                path=public_root/name;path.parent.mkdir(parents=True,exist_ok=True)
                temp=path.with_suffix('.tmp');temp.write_bytes(data)
                if name=='data/research.json':validate_research_snapshot(temp,env=load_env(env_file,os.environ))
                else:validate_study_detail(temp,env=load_env(env_file,os.environ))
                staged.append((temp,path))
            for temp,path in sorted(staged,key=lambda p:p[1].name=='research.json'):
                if path.name=='research.json':
                    index=validate_research_snapshot(temp,env=load_env(env_file,os.environ))
                    if any(r.detail_file and not (public_root/r.detail_file).is_file() for r in index.studies):
                        continue # Fetch remaining shards before exposing an index with missing details.
                temp.replace(path)
            messages.append({'phase':'public_snapshot_synced','jobs':len(staged)})
            continue
        if isinstance(value,dict) and set(value)=={'capture_name','capture_bundle'}:
            name=value['capture_name']
            if not re.fullmatch(r'(?:neural-smoke-[0-9TZ]+|trained-[a-f0-9]{16}-[a-z0-9-]+)',name):raise ValueError('Unexpected capture name')
            files=value['capture_bundle']
            if set(files)!={'capture.json','private_inputs.json','activations.safetensors','checksums.json'}:raise ValueError('Unapproved capture files')
            decoded={k:base64.b64decode(v,validate=True) for k,v in files.items()}
            if sum(map(len,decoded.values()))>(32 if action=='trained-fetch' else 8)*1024*1024:raise ValueError('Capture transfer exceeds cap')
            hashes=json.loads(decoded['checksums.json'])
            if set(hashes)!=set(files)-{'checksums.json'} or not all(hashlib.sha256(decoded[k]).hexdigest()==v for k,v in hashes.items()):raise ValueError('Downloaded capture failed integrity')
            directory=ROOT/'results/neural'/f'{server}-{name}'
            directory.mkdir(parents=True,exist_ok=False)
            for key,data in decoded.items():(directory/key).write_bytes(data)
            messages.append({'phase':'capture_fetched','capture_name':name,'neural_captures':1})
            continue
        if isinstance(value,dict) and set(value)<=allowed:
            if 'diagnostic' in value:
                from contagion.publication import Redactor,sensitive_values
                value['diagnostic']=Redactor(sensitive_values(load_env(env_file,os.environ)))(value['diagnostic'])
            messages.append(value)
    import datetime
    directory=ROOT/'results/remote-setup'
    directory.mkdir(parents=True,exist_ok=True)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    (directory/f'{server}-{action}-{stamp}.json').write_text(json.dumps({'messages':messages,'returncode':result.returncode},indent=2))
    if result.returncode:
        reason='remote_operation_failed'
        if 'Host key verification failed' in result.stderr:reason='host_key_not_trusted'
        elif 'Permission denied' in result.stderr:reason='ssh_authentication_failed'
        elif result.returncode==255:reason='ssh_connection_failed'
        raise RuntimeError(reason)
    return messages


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['preflight','install','diagnose','smoke','api','fetch','capacity','deploy-suite','suite-status','suite-sync','suite-pause','suite-diagnose','trained-pilot','trained-status','trained-diagnose','trained-retry','trained-fetch']);p.add_argument('--server',choices=['primary','secondary'],required=True)
    p.add_argument('--env-file',type=Path,default=ROOT/'.env');p.add_argument('--bundle',type=Path)
    args=p.parse_args()
    try:
        for value in execute(args.server,args.action,args.env_file,args.bundle):print(json.dumps(value))
    except RuntimeError as exc:p.exit(1,f'Worker operation stopped: {exc}. No private target values printed.\n')
    except Exception as exc:p.exit(1,f'Worker operation stopped ({type(exc).__name__}); check private configuration. No target values printed.\n')
