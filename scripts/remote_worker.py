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
release=base/('neural-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+request['sha256'][:8])
release.mkdir(parents=True,exist_ok=False)
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


def execute(server,action,env_file,bundle=None):
    import hashlib
    target,project=configuration(env_file,server)
    payload={'action':action,'project':project}
    if action=='install':
        if not bundle:raise ValueError('Installation needs a reviewed source bundle')
        blob=Path(bundle).read_bytes()
        if len(blob)>20*1024*1024:raise ValueError('Bundle exceeds fixed transfer cap')
        payload.update(bundle=base64.b64encode(blob).decode(),sha256=hashlib.sha256(blob).hexdigest())
    if action=='smoke':
        source=(ROOT/'src/contagion/neural.py').read_text()
        payload.update(module_source=source,module_sha256=hashlib.sha256(source.encode()).hexdigest())
    command=['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10',
             target,'python3 -c '+shlex.quote(REMOTE)]
    result=subprocess.run(command,input=json.dumps(payload),capture_output=True,text=True,timeout=1800 if action=='install' else 210 if action=='smoke' else 30)
    # Never echo SSH banners, authentication errors or package installer diagnostics.
    messages=[]
    allowed={'system','architecture','python','free_disk_gib','project_exists','docker_available','nvidia_smi_available',
             'memory_gib','ollama_explicit_settings','diagnostic','capture_name','phase','evidence_type','release_name','neural_captures'}
    for line in result.stdout.splitlines():
        try:value=json.loads(line)
        except ValueError:continue
        if isinstance(value,dict) and set(value)=={'capture_name','capture_bundle'}:
            name=value['capture_name']
            if not re.fullmatch(r'neural-smoke-[0-9TZ]+',name):raise ValueError('Unexpected capture name')
            files=value['capture_bundle']
            if set(files)!={'capture.json','private_inputs.json','activations.safetensors','checksums.json'}:raise ValueError('Unapproved capture files')
            decoded={k:base64.b64decode(v,validate=True) for k,v in files.items()}
            if sum(map(len,decoded.values()))>8*1024*1024:raise ValueError('Capture transfer exceeds cap')
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
    p.add_argument('action',choices=['preflight','install','diagnose','smoke','api','fetch']);p.add_argument('--server',choices=['primary','secondary'],required=True)
    p.add_argument('--env-file',type=Path,default=ROOT/'.env');p.add_argument('--bundle',type=Path)
    args=p.parse_args()
    try:
        for value in execute(args.server,args.action,args.env_file,args.bundle):print(json.dumps(value))
    except RuntimeError as exc:p.exit(1,f'Worker operation stopped: {exc}. No private target values printed.\n')
    except Exception as exc:p.exit(1,f'Worker operation stopped ({type(exc).__name__}); check private configuration. No target values printed.\n')
