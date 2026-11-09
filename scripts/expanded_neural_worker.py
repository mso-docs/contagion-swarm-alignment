"""Operator-only isolated CPU reference worker and generic sealed capture sync."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import tarfile
import tempfile
import time

from run_pilot import ROOT
from remote_worker import configuration

REMOTE = r'''
import base64,hashlib,io,json,os,pathlib,subprocess,sys,tarfile,time
request=json.load(sys.stdin)
base=pathlib.Path(request['project']).expanduser()
if not base.is_absolute() or base==pathlib.Path('/') or '..' in base.parts:raise ValueError('Invalid worker base')
revision='607a30d783dfa663caf39e06633721c8d4cfcd7e'
def discover():
    interpreters=[p/'contagion-worker/.venv-interp/bin/python' for p in sorted(base.glob('neural-*'))]
    interpreters=[p for p in interpreters if p.is_file()]
    caches=[];reuse=[]
    for release in sorted(base.glob('trained-*')):
        root=release/'contagion-worker'
        for cache in sorted((root/'results').glob('*/hf-cache')):
            snap=cache/'hub/models--openai-community--gpt2/snapshots'/revision
            if all((snap/n).is_file() for n in ['config.json','model.safetensors','vocab.json','merges.txt']):caches.append(cache)
        for seal in sorted((root/'results').glob('*/*/checksums.json')):reuse.append(str(seal.parent))
    return {'python':str(interpreters[-1]) if interpreters else None,'cache':str(caches[-1]) if caches else None,
            'reuse_candidates':reuse,'cpu_count':os.cpu_count(),'project_exists':base.exists()}
action=request['action']
if action=='discover':print(json.dumps(discover()));sys.exit(0)
if action=='deploy':
    found=discover()
    if not found['python'] or not found['cache']:raise ValueError('Existing trained runtime/cache required; no installs or downloads')
    blob=base64.b64decode(request['bundle'],validate=True)
    if len(blob)>4*1024*1024 or hashlib.sha256(blob).hexdigest()!=request['bundle_sha256']:raise ValueError('Bundle integrity failed')
    release=base/('interp-grid-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+request['bundle_sha256'][:8])
    release.mkdir(mode=0o700,parents=True,exist_ok=False)
    with tarfile.open(fileobj=io.BytesIO(blob),mode='r:gz') as archive:
        member_names=[m.name for m in archive.getmembers()]
        if len(member_names)!=len(set(member_names)) or len(member_names)>128:raise ValueError('Duplicate or excessive bundle members')
        for member in archive.getmembers():
            name=pathlib.PurePosixPath(member.name)
            allowed=str(name)=='worker-manifest.json' or str(name)=='scripts/expanded_trained_pilot.py' or (name.parent==pathlib.PurePosixPath('src/contagion') and name.suffix=='.py')
            if not member.isfile() or name.is_absolute() or '..' in name.parts or not allowed or member.size>1024*1024:raise ValueError('Unexpected worker archive member')
        archive.extractall(release,filter='data')
    manifest=json.loads((release/'worker-manifest.json').read_text())
    if set(manifest['files'])!=set(member_names)-{'worker-manifest.json'}:raise ValueError('Manifest closure failed')
    for name,want in manifest['files'].items():
        p=release/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=want:raise ValueError('Worker source seal failed')
    output=release/'results/expanded-reference';env=dict(os.environ,PYTHONPATH=str(release/'src'),CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    command=[found['python'],str(release/'scripts/expanded_trained_pilot.py'),'prepare','--out',str(output),'--cache-directory',found['cache']]
    for directory in found['reuse_candidates']:command.extend(['--reuse',directory])
    with (release/'prepare.private.log').open('x') as log:subprocess.run(command,cwd=release,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,check=True,timeout=180)
    plan=json.loads((output/'expanded-plan.private.json').read_text())
    result={'release_name':release.name,'root':str(release),'output':str(output),'python':found['python'],
            'plan_hash':plan['plan_hash'],'grid_cells':len(plan['jobs']),'reused_cells':sum(j['reused'] is not None for j in plan['jobs'])}
    (release/'deployment.private.json').write_text(json.dumps(result));print(json.dumps(result));sys.exit(0)
release=base/request['release_name']
if pathlib.Path(request['release_name']).name!=request['release_name'] or not request['release_name'].startswith('interp-grid-'):raise ValueError('Unsafe isolated release')
deployment=json.loads((release/'deployment.private.json').read_text());output=pathlib.Path(deployment['output'])
if output!=release/'results/expanded-reference':raise ValueError('Unexpected isolated output')
if action=='launch':
    process_file=release/'process.private.json'
    if process_file.exists() and not request.get('resume'):raise ValueError('Explicit resume required for an existing worker')
    if process_file.exists():
        old=json.loads(process_file.read_text());cmd=pathlib.Path('/proc')/str(old['pid'])/'cmdline'
        if cmd.exists() and b'expanded_trained_pilot.py' in cmd.read_bytes():raise ValueError('Reference worker already active')
    env=dict(os.environ,PYTHONPATH=str(release/'src'),CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    command=[deployment['python'],str(release/'scripts/expanded_trained_pilot.py'),'run','--out',str(output)]
    if request.get('resume'):command.append('--resume')
    if request.get('retry_failed'):command.append('--retry-failed')
    with (release/'worker.private.log').open('a') as log:
        process=subprocess.Popen(command,cwd=release,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True)
    record={'pid':process.pid,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'plan_hash':deployment['plan_hash']}
    process_file.write_text(json.dumps(record));print(json.dumps({'status':'started','pid':process.pid}));sys.exit(0)
status_file=output/'expanded-status.private.json'
state=json.loads(status_file.read_text()) if status_file.exists() else {'status':'prepared','completed':[],'new_measured_captures':0}
def diagnostic():
    known={
        'CPU reference worker RAM unavailable or low':'available_ram_below_registered_minimum',
        'CPU reference worker cooling or sensor review required':'cpu_cooling_or_sensor_guard',
        'Reference worker disk low':'free_disk_below_registered_minimum',
        'CPU capture watchdog limit':'capture_watchdog_limit',
        'CPU capture thermal or RAM limit':'capture_thermal_or_ram_guard',
        'CPU reference capture failed; private log retained':'capture_child_failed',
        'No-op or aligned-position control failed':'noop_or_position_control_failed',
        'Raw-model / instrumented-bridge logits disagree':'raw_bridge_parity_failed',
        'Capture seal failed':'capture_seal_failed',
        'Capture does not match the registered reference checkpoint':'capture_checkpoint_mismatch',
        'Capture does not match the registered grid cell':'capture_grid_cell_mismatch',
        'Frozen expanded reference plan, source or cache changed':'frozen_source_or_cache_changed',
        'Operator stop or allocation wall ceiling':'operator_stop_or_allocation_wall',
        'Capture attempt ceiling':'capture_attempt_limit',
    }
    def reason(path):
        if not path.is_file():return None
        for line in reversed(path.read_text(errors='replace')[-24000:].splitlines()):
            for text,code in known.items():
                if line.strip()=='ValueError: '+text:return code
        return None
    logs=sorted((output/'logs').glob('cell-*-attempt-*.private.log'))
    info={'error_type':state.get('error_type'),'coordinator_reason_code':reason(release/'worker.private.log'),
          'capture_reason_code':reason(logs[-1]) if logs else None,
          'attempt_log_count':len(logs),'completed_grid_cells':len(state.get('completed',[]))}
    available=None
    for line in pathlib.Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):available=int(line.split()[1])/1024
    temperatures=[]
    for p in pathlib.Path('/sys/class/hwmon').glob('hwmon*/temp*_input'):
        try:
            if (p.parent/'name').read_text().strip() in {'coretemp','k10temp','zenpower','cpu_thermal'}:
                value=int(p.read_text().strip())/1000
                if 0<value<150:temperatures.append(value)
        except (OSError,ValueError):pass
    info.update(available_ram_mib=available,cpu_temperature_max_c=max(temperatures) if temperatures else None)
    return info
if action=='diagnose':print(json.dumps(diagnostic()));sys.exit(0)
if action=='status':
    done=state.get('new_measured_captures',0);total=deployment['grid_cells']-deployment['reused_cells'];elapsed=state.get('execution_seconds',0)
    print(json.dumps({'status':state['status'],'grid_cells':deployment['grid_cells'],'completed_grid_cells':len(state.get('completed',[])),
        'reused_grid_cells':deployment['reused_cells'],'new_measured_captures':done,'execution_seconds':elapsed,
        'eta_seconds':elapsed/done*(total-done) if done else None,
        'diagnostic':diagnostic() if state['status']=='stopped' else None}));sys.exit(0)
if action=='fetch':
    known=set(request.get('known_seals',[]))
    for row in state.get('completed',[]):
        if row['origin']!='new_measurement' or row['checksums_sha256'] in known:continue
        directory=pathlib.Path(row['capture'])
        if directory.parent!=output or not directory.name.startswith('cell-'):raise ValueError('Unexpected capture path')
        names=['capture.json','private_inputs.json','activations.safetensors','checksums.json']
        if any((directory/name).is_symlink() for name in names) or sum((directory/n).stat().st_size for n in names)>32*1024*1024:raise ValueError('Capture transfer cap or unsafe file')
        checks=json.loads((directory/'checksums.json').read_text())
        if set(checks)!=set(names)-{'checksums.json'} or hashlib.sha256((directory/'checksums.json').read_bytes()).hexdigest()!=row['checksums_sha256']:raise ValueError('Capture seal changed')
        if any(hashlib.sha256((directory/n).read_bytes()).hexdigest()!=want for n,want in checks.items()):raise ValueError('Capture files changed')
        print(json.dumps({'capture_name':directory.name,'seal_sha256':row['checksums_sha256'],
            'files':{n:base64.b64encode((directory/n).read_bytes()).decode() for n in names}}));sys.exit(0)
    print(json.dumps({'status':'no_new_capture','worker_status':state['status']}));sys.exit(0)
raise ValueError('Unknown bounded operator action')
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_bundle(output):
    output = Path(output).resolve()
    if (ROOT / 'results').resolve() not in output.parents:
        raise ValueError('Keep deployment source bundles under private results')
    if any(p.is_symlink() for p in (ROOT / 'src/contagion').glob('*.py')):
        raise ValueError('Worker source symlinks are not allowed')
    files = {str(p.relative_to(ROOT)): p.read_bytes() for p in sorted((ROOT / 'src/contagion').glob('*.py'))}
    files['scripts/expanded_trained_pilot.py'] = (ROOT / 'scripts/expanded_trained_pilot.py').read_bytes()
    manifest = {'files': {n: hashlib.sha256(v).hexdigest() for n, v in files.items()}}
    files['worker-manifest.json'] = json.dumps(manifest, sort_keys=True).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name); info.size = len(content); info.mode = 0o644
            archive.addfile(info, io.BytesIO(content))
    return len(files)


def request(action, env_file, deployment=None, bundle=None, known=(), resume=False, retry_failed=False, runner=None):
    target, project = configuration(env_file, 'secondary')
    payload = {'project': project, 'action': action}
    if deployment:
        payload['release_name'] = deployment['release_name']
    if bundle:
        payload.update(bundle=base64.b64encode(Path(bundle).read_bytes()).decode(), bundle_sha256=sha(bundle))
    if action == 'fetch':
        payload['known_seals'] = list(known)
    if action == 'launch':
        payload.update(resume=resume, retry_failed=retry_failed)
    command = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
               target, 'python3 -c ' + shlex.quote(REMOTE)]
    runner = subprocess.run if runner is None else runner
    try:
        result = runner(command, input=json.dumps(payload), capture_output=True, text=True, timeout=240 if action == 'deploy' else 45)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('Isolated neural worker connection unavailable') from None
    if result.returncode != 0:
        raise ValueError('Isolated neural worker operation failed; private remote log retained')
    return json.loads(result.stdout)


def fetch_one(env_file, deployment, target=None, requester=None):
    target = Path(target) if target else ROOT / 'results/neural'
    known = [sha(path) for path in target.glob('*/checksums.json')]
    call = request if requester is None else requester
    response = call('fetch', env_file, deployment, known=known)
    if 'files' not in response:
        return False
    names = {'capture.json', 'private_inputs.json', 'activations.safetensors', 'checksums.json'}
    if set(response['files']) != names or not response['capture_name'].startswith('cell-') or Path(response['capture_name']).name != response['capture_name']:
        raise ValueError('Unexpected fetched capture bundle')
    blobs = {n: base64.b64decode(v, validate=True) for n, v in response['files'].items()}
    if sum(map(len, blobs.values())) > 32 * 1024 * 1024:
        raise ValueError('Fetched capture exceeds bound')
    if hashlib.sha256(blobs['checksums.json']).hexdigest() != response['seal_sha256']:
        raise ValueError('Fetched seal mismatch')
    hashes = json.loads(blobs['checksums.json'])
    if set(hashes) != names - {'checksums.json'} or any(hashlib.sha256(blobs[n]).hexdigest() != h for n, h in hashes.items()):
        raise ValueError('Fetched files mismatch')
    from contagion.neural import validate_numeric_capture
    validate_numeric_capture(json.loads(blobs['capture.json']))
    directory = target / ('secondary-expanded-' + response['seal_sha256'][:16] + '-' + response['capture_name'])
    if directory.exists():
        if sha(directory / 'checksums.json') != response['seal_sha256']:
            raise ValueError('Local capture collision')
        return False
    target.mkdir(parents=True, exist_ok=True)
    staging = target.parent / 'neural-transfer-staging'; staging.mkdir(parents=True, exist_ok=True)
    incoming = Path(tempfile.mkdtemp(prefix='sealed-', dir=staging))
    for name, content in blobs.items():
        with (incoming / name).open('xb') as stream: stream.write(content)
    if any(sha(incoming / n) != h for n, h in hashes.items()):
        raise ValueError('Local sealed transfer failed verification')
    incoming.rename(directory)
    return True


def sync(env_file, deployment_file, limit=2):
    deployment = json.loads(Path(deployment_file).read_text()); fetched = 0
    for _ in range(limit):
        if not fetch_one(env_file, deployment):
            break
        fetched += 1
    return fetched


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['bundle', 'discover', 'deploy', 'launch', 'status', 'diagnose', 'sync', 'watch'])
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--resume', action='store_true'); parser.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args()
    if args.action == 'bundle':
        print('Packaged', build_bundle(args.bundle), 'allowlisted CPU reference source files; no private config.')
    elif args.action == 'discover':
        data = request('discover', args.env_file)
        args.record.parent.mkdir(parents=True, exist_ok=True); args.record.write_text(json.dumps(data, indent=2) + '\n'); args.record.chmod(0o600)
        print('Existing CPU runtime:', bool(data['python']), '; cached checkpoint:', bool(data['cache']), '; reuse candidates:', len(data['reuse_candidates']))
    elif args.action == 'deploy':
        data = request('deploy', args.env_file, bundle=args.bundle)
        args.record.parent.mkdir(parents=True, exist_ok=True); args.record.write_text(json.dumps(data, indent=2) + '\n'); args.record.chmod(0o600)
        print('Prepared isolated CPU grid:', data['grid_cells'], 'cells;', data['reused_cells'], 'reused; no measurements launched.')
    elif args.action in {'launch', 'status', 'diagnose'}:
        data = request(args.action, args.env_file, json.loads(args.record.read_text()), resume=args.resume, retry_failed=args.retry_failed)
        print(json.dumps(data))
    elif args.action == 'sync':
        print('Fetched sealed reference captures:', sync(args.env_file, args.record))
    else:
        started = time.monotonic()
        while time.monotonic() - started < 2.5 * 3600:
            try:
                count = sync(args.env_file, args.record, limit=4)
                data = request('status', args.env_file, json.loads(args.record.read_text()))
                print('Reference sync:', data['status'], data.get('new_measured_captures', 0), 'new measured captures;', count, 'fetched.', flush=True)
                if data['status'] in {'completed', 'stopped'} and count == 0:
                    break
            except (ValueError, OSError, subprocess.TimeoutExpired):
                print('Reference sync temporarily unavailable; captures remain on worker.', flush=True)
            time.sleep(15)
