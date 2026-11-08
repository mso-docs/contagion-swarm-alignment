"""Pinned private static benchmark adaptations; never executes upstream code or calls models."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote,urlsplit

import httpx

ROOT=Path(__file__).resolve().parents[1]
MARTIAN='withmartian/code-review-benchmark'
SWE='princeton-nlp/SWE-bench_Verified'
SWE_REVISION='c104f840cc67f8b6eec6f759ebc8b2693d585d4a'
MIN_CHARACTERS=16001
MAX_CHARACTERS=52000
MAX_INPUT_BYTES=70000
SPLIT_SEED=20261108
PROJECT_ALIASES={'ai-code-review-evaluation/discourse-graphite':'discourse/discourse',
                 'ai-code-review-evaluation/sentry-greptile':'getsentry/sentry',
                 'ai-code-review-evaluation/keycloak-greptile':'keycloak/keycloak'}
DOMAINS={'getsentry/sentry':'observability','grafana/grafana':'observability','keycloak/keycloak':'identity','calcom/cal.com':'scheduling','discourse/discourse':'community',
         'astropy/astropy':'scientific_computing','django/django':'web_framework','matplotlib/matplotlib':'visualization','mwaskom/seaborn':'visualization',
         'pallets/flask':'web_framework','psf/requests':'http_client','pydata/xarray':'scientific_computing','pylint-dev/pylint':'static_analysis',
         'scikit-learn/scikit-learn':'machine_learning','sphinx-doc/sphinx':'documentation','sympy/sympy':'symbolic_math','pytest-dev/pytest':'testing'}


def sha(blob):return hashlib.sha256(blob).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False).encode()
def catalog_hash(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError('Immutable materials output already exists')
    path.write_bytes(canonical(value));path.chmod(0o600)


def safe_name(value):
    return isinstance(value,str) and Path(value).name==value and value not in {'.','..'}


def safe_repo(value):return isinstance(value,str) and bool(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',value)) and all(x not in {'.','..'} for x in value.split('/'))


def canonical_project(value):
    value=value.removesuffix('.git').lower()
    if value.startswith('ai-code-review-evaluation/') and value not in PROJECT_ALIASES:raise ValueError('Unreviewed benchmark project alias')
    return PROJECT_ALIASES.get(value,value)


def audit_project_aliases(private):
    expected={'sentry':'getsentry/sentry','grafana':'grafana/grafana','keycloak':'keycloak/keycloak','discourse':'discourse/discourse','cal_dot_com':'calcom/cal.com'}
    observations={}
    for family,project in expected.items():
        path=Path(private)/(family+'.golden.json')
        for row in json.loads(path.read_text()):
            parsed=urlsplit(row['url']);parts=parsed.path.strip('/').split('/')
            if parsed.scheme!='https' or parsed.hostname!='github.com' or len(parts)<4:raise ValueError('Invalid benchmark project reference')
            source='/'.join(parts[:2])
            if canonical_project(source)!=project:raise ValueError('Benchmark family and canonical project disagree')
            observations[source]={'source_repository':source,'project_group':project,'dataset_family':family,'family_file_sha256':sha(path.read_bytes())}
    return sorted(observations.values(),key=lambda row:row['source_repository'])


def bounded_get(client,url,max_bytes=12*1024*1024):
    for attempt in range(5):
        parsed=urlsplit(url);host=parsed.hostname or ''
        if (parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in {None,443} or
            not(host in {'api.github.com','raw.githubusercontent.com','huggingface.co','github.com'} or host.endswith('.hf.co'))):
            raise ValueError('Unapproved public import source')
        with client.stream('GET',url,follow_redirects=False) as response:
            if response.status_code in {301,302,303,307,308}:
                if attempt==4:raise ValueError('Excessive import redirects')
                from urllib.parse import urljoin
                url=urljoin(url,response.headers.get('location',''));continue
            response.raise_for_status();body=bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body)>max_bytes:raise ValueError('Import response exceeds cap')
            return bytes(body)
    raise ValueError('Import did not resolve')


def project_splits(tasks):
    """Disjoint project groups, with a train/dev project reserved per source."""
    groups=defaultdict(set)
    for task in tasks:groups[task['dataset']].add(task['project_group'])
    result={}
    for dataset,projects in sorted(groups.items()):
        ordered=sorted(projects,key=lambda name:sha(f'{SPLIT_SEED}:{name}'.encode()))
        if len(ordered)<2:raise ValueError('Each benchmark source needs development and heldout project groups')
        for index,project in enumerate(ordered):
            split=('dev' if index==0 else 'heldout') if len(ordered)==2 else ('train' if index==0 else 'dev' if index==1 else 'heldout')
            if project in result and result[project]!=split:raise ValueError('Cross-source project split conflict')
            result[project]=split
    return result


def prior_exposure_index(root=ROOT):
    """Exclude allocated/live historical cases, not just completed successful cases."""
    ids=set();projects=set();proof={}
    for path in sorted((Path(root)/'results/repository-runs').rglob('config.snapshot.json')):
        row=json.loads(path.read_text())
        if row.get('model_identity',{}).get('backend') not in {'ollama','openai'}:continue
        ids.add(row.get('task_id'));metadata=row.get('task_metadata',{});repository=metadata.get('repository')
        if repository:projects.add(canonical_project(repository))
        proof[sha(str(path.relative_to(root)).encode())]=sha(path.read_bytes())
    path=Path(root)/'results/campaigns/primary-long-safeguard-v33-20261108/primary-long-plan.json'
    if path.exists():
        rows=json.loads(path.read_text())['tasks'];ids.update(r['id'] for r in rows);projects.update(canonical_project(r['repository']) for r in rows)
        proof['primary_long_allocation']=sha(path.read_bytes())
    return ids,projects,sha(canonical(proof))


def make_task(root,dataset,revision,repository,instance,base,payload,oracle,context_selection,documents,reference_kind):
    if not safe_repo(repository) or not re.fullmatch(r'[a-f0-9]{40}',base):raise ValueError('Unpinned repository task')
    identity=sha(canonical([dataset,revision,repository,instance,base]))[:20]
    payload={'task_id':identity,**payload}
    raw=canonical(payload)
    from scan_privacy import findings
    privacy=findings(raw.decode(),public=True)
    if privacy:raise ValueError('privacy_quarantine:'+','.join(sorted(privacy)))
    if any(marker in raw.decode().casefold() for marker in ('violet lantern','propose_protected_update')):raise ValueError('reserved_intervention_marker')
    if not MIN_CHARACTERS<=len(raw.decode())<=MAX_CHARACTERS or len(raw)>MAX_INPUT_BYTES:raise ValueError('long_input_budget')
    name=identity+'.input.json';reference=identity+'.oracle.json'
    write(root/'private'/name,payload);write(root/'private'/reference,oracle)
    return {'id':identity,'dataset':dataset,'dataset_revision':revision,'repository':repository,'project_group':repository,
            'upstream_instance':str(instance),'base_revision':base,'task_kind':'code_review' if dataset==MARTIAN else 'issue_diagnosis',
            'input_file':name,'input_sha256':sha(raw),'oracle_file':reference,'oracle_sha256':sha((root/'private'/reference).read_bytes()),
            'characters':len(raw.decode()),'bytes':len(raw),'input_length':'long',
            'files':payload['code_diff'].count('diff --git ') if dataset==MARTIAN else len(documents),
            'domain':DOMAINS.get(canonical_project(repository),'software_engineering'),
            'source_documents_sha256':documents,'context_selection':context_selection,'reference_kind':reference_kind,
            'upstream_code_redistribution':'withheld_pending_license_review','official_benchmark_score':False}


def load_task(catalog_path,row):
    path=Path(catalog_path);data=json.loads(path.read_text())
    expected=next((r for r in data['tasks'] if r['id']==row['id']),None)
    if expected!=row:raise ValueError('Task metadata differs from catalog')
    if not safe_name(row['input_file']):raise ValueError('Unsafe input reference')
    source=path.parent/'private'/row['input_file']
    if source.is_symlink() or sha(source.read_bytes())!=row['input_sha256']:raise ValueError('Task input integrity failed')
    payload=json.loads(source.read_text())
    allowed={'task_id','repository','code_diff'} if row['task_kind']=='code_review' else {'task_id','repository','problem_statement','source_files','context_policy'}
    if set(payload)!=allowed or payload['task_id']!=row['id'] or payload['repository']!=row['repository']:raise ValueError('Input/reference boundary or identity mismatch')
    if row['task_kind']=='issue_diagnosis':
        for source in payload['source_files']:
            if set(source)!={'path','content','sha256','first_line','last_line'} or '..' in Path(source['path']).parts or Path(source['path']).is_absolute():raise ValueError('Unsafe source-document fields')
    return payload


def validate_catalog(path):
    path=Path(path);data=json.loads(path.read_text())
    if data.get('schema_version')!='long-benchmark-materials-1.0' or catalog_hash({k:v for k,v in data.items() if k!='catalog_hash'})!=data.get('catalog_hash'):
        raise ValueError('Materials catalog integrity failed')
    if data.get('agent_tools')!=[] or data.get('upstream_execution') is not False or data.get('official_benchmark_score') is not False:raise ValueError('Static adaptation boundary changed')
    sources={r['dataset']:r for r in data['sources']};ids=set();projects={}
    if 'project_aliases' in data and data['project_aliases']!=PROJECT_ALIASES:raise ValueError('Declared project aliases differ from reviewed mapping')
    if set(sources)!={MARTIAN,SWE}:raise ValueError('Both declared benchmark sources are required')
    for source in sources.values():
        if source['license_spdx']!='MIT' or not re.fullmatch(r'[a-f0-9]{40}',source['revision']):raise ValueError('Source license or revision missing')
        license_path=path.parent/'private'/source['license_file']
        if not safe_name(source['license_file']) or license_path.is_symlink() or sha(license_path.read_bytes())!=source['license_sha256']:raise ValueError('Source license changed')
    for row in data['tasks']:
        if row['id'] in ids or not re.fullmatch(r'[a-f0-9]{20}',row['id']) or row['dataset'] not in sources:raise ValueError('Duplicate or unknown task')
        ids.add(row['id'])
        if row['dataset_revision']!=sources[row['dataset']]['revision'] or row['official_benchmark_score'] is not False:raise ValueError('Task source mismatch')
        if row['task_kind'] not in {'code_review','issue_diagnosis'} or row['split'] not in {'train','dev','heldout'}:raise ValueError('Unknown task kind/split')
        if row.get('prior_exposure') is True and row['split']=='heldout':raise ValueError('Previously allocated task is not unseen heldout')
        if row['task_kind']!=('code_review' if row['dataset']==MARTIAN else 'issue_diagnosis'):raise ValueError('Task kind differs from source adaptation')
        if row['project_group']!=row['repository'] or not safe_repo(row['repository']):raise ValueError('Project group must be canonical repository')
        if 'project_aliases' in data and canonical_project(row.get('source_repository',row['repository']))!=row['project_group']:raise ValueError('Source fork inflated or changed canonical project')
        if row['project_group'] in projects and projects[row['project_group']]!=row['split']:raise ValueError('Project leaked across splits')
        projects[row['project_group']]=row['split']
        payload=load_task(path,row);raw=canonical(payload)
        if (row['input_length']!='long' or len(raw.decode())!=row['characters'] or len(raw)!=row['bytes'] or
            not MIN_CHARACTERS<=row['characters']<=MAX_CHARACTERS or row['bytes']>MAX_INPUT_BYTES):raise ValueError('Invalid long task budget')
        oracle=path.parent/'private'/row['oracle_file']
        if not safe_name(row['oracle_file']) or oracle.is_symlink() or sha(oracle.read_bytes())!=row['oracle_sha256']:raise ValueError('Hidden reference changed')
    expected_splits=project_splits(data['tasks'])
    if any(row['split']!=expected_splits[row['project_group']] for row in data['tasks']):raise ValueError('Declared deterministic split differs')
    return data


def assemble(output,base_catalog,martian_catalog):
    """Build a fresh catalog from private imports and exclude previously allocated cases."""
    output=Path(output)
    if output.exists():raise ValueError('Use a fresh immutable material directory')
    output.mkdir(parents=True,mode=0o700);(output/'private').mkdir(mode=0o700)
    base_catalog=Path(base_catalog);base=validate_catalog(base_catalog)
    martian_catalog=Path(martian_catalog);martian=json.loads(martian_catalog.read_text())
    if catalog_hash({k:v for k,v in martian.items() if k!='catalog_hash'})!=martian['catalog_hash']:raise ValueError('Martian import changed')
    import shutil
    aliases=audit_project_aliases(martian_catalog.parent/'private')
    ids,projects,exposure_hash=prior_exposure_index();tasks=[];excluded=[r for r in base['excluded'] if r['dataset']==SWE]
    for row in base['tasks']:
        if row['dataset']!=SWE:continue
        row={**row,'prior_exposure':False,'prior_project_exposure':row['repository'] in projects,
             'source_repository':row['repository'],'domain':DOMAINS.get(row['repository'],'software_engineering')}
        for field in ('input_file','oracle_file'):shutil.copyfile(base_catalog.parent/'private'/row[field],output/'private'/row[field])
        tasks.append(row)
    for row in sorted(martian['tasks'],key=lambda r:r['id']):
        if row['input_length']!='long':continue
        if row['id'] in ids:
            excluded.append({'dataset':MARTIAN,'instance':str(row['pr']),'reason':'prior_live_or_allocated_case'});continue
        try:
            if not safe_name(row['diff_file']) or not safe_name(row['oracle_file']):raise ValueError('unsafe_source_reference')
            diff=(martian_catalog.parent/'private'/row['diff_file']).read_bytes()
            if sha(diff)!=row['diff_sha256']:raise ValueError('diff_integrity')
            oracle=json.loads((martian_catalog.parent/'private'/row['oracle_file']).read_text())
            repository=canonical_project(row['repository'])
            selected=make_task(output,MARTIAN,martian['dataset_revision'],repository,row['pr'],row['base_revision'],
                {'repository':repository,'code_diff':diff.decode()},oracle,'complete_pinned_pr_diff',
                {row['diff_file']:row['diff_sha256']},'curated_human_golden_comments')
            selected.update(source_repository=row['repository'],prior_exposure=False,prior_project_exposure=repository in projects);tasks.append(selected)
        except (ValueError,UnicodeError) as exc:excluded.append({'dataset':MARTIAN,'instance':str(row['pr']),'reason':str(exc).split(':')[0]})
    sources=[]
    for source in base['sources']:
        source=dict(source)
        original=martian_catalog.parent/'private/DATASET-LICENSE' if source['dataset']==MARTIAN else base_catalog.parent/'private'/source['license_file']
        shutil.copyfile(original,output/'private'/source['license_file'])
        source['license_sha256']=sha(original.read_bytes())
        if source['dataset']==MARTIAN:source['source_artifact_sha256']=sha(martian_catalog.read_bytes())
        sources.append(source)
    splits=project_splits(tasks)
    for row in tasks:row['split']=splits[row['project_group']]
    catalog={**{k:v for k,v in base.items() if k not in {'catalog_hash','tasks','sources','excluded'}},'tasks':sorted(tasks,key=lambda r:r['id']),
             'sources':sources,'excluded':excluded,'prior_exposure_index_sha256':exposure_hash,
             'project_aliases':PROJECT_ALIASES,'project_alias_audit':aliases,
             'prior_exposure_policy':'Exclude previously live or allocated source cases; project splits are new-study-disjoint, not historically unseen projects.'}
    catalog['catalog_hash']=catalog_hash(catalog);write(output/'catalog.json',catalog);return validate_catalog(output/'catalog.json')


def source_window(text,first_line,budget):
    lines=text.splitlines(keepends=True);center=max(0,first_line-1);start=max(0,center-80)
    selected=[];size=0
    for line in lines[start:]:
        if size+len(line)>budget:break
        selected.append(line);size+=len(line)
    return ''.join(selected),start+1,start+len(selected)


def import_materials(output,martian_catalog,swe_limit=96):
    """Import bounded source artifacts. Import-only pyarrow dependency; no model execution."""
    output=Path(output)
    if output.exists():raise ValueError('Use a fresh immutable material directory')
    output.mkdir(parents=True,mode=0o700);(output/'private').mkdir(mode=0o700)
    tasks=[];excluded=[];sources=[];martian_path=Path(martian_catalog)
    martian=json.loads(martian_path.read_text())
    if catalog_hash({k:v for k,v in martian.items() if k!='catalog_hash'})!=martian['catalog_hash']:raise ValueError('Existing Martian catalog changed')
    license_blob=(martian_path.parent/'private/DATASET-LICENSE').read_bytes();(output/'private/martian.LICENSE').write_bytes(license_blob)
    sources.append({'dataset':MARTIAN,'revision':martian['dataset_revision'],'license_spdx':'MIT','license_file':'martian.LICENSE','license_sha256':sha(license_blob),'source_url':'https://github.com/withmartian/code-review-benchmark','source_artifact_sha256':sha(martian_path.read_bytes())})
    for row in sorted(martian['tasks'],key=lambda r:r['id']):
        if row['input_length']!='long':continue
        try:
            if not safe_name(row['diff_file']) or not safe_name(row['oracle_file']):raise ValueError('unsafe_source_reference')
            diff=(martian_path.parent/'private'/row['diff_file']).read_bytes()
            if sha(diff)!=row['diff_sha256']:raise ValueError('diff_integrity')
            oracle=json.loads((martian_path.parent/'private'/row['oracle_file']).read_text())
            tasks.append(make_task(output,MARTIAN,martian['dataset_revision'],row['repository'],row['pr'],row['base_revision'],
                {'repository':row['repository'],'code_diff':diff.decode()},oracle,'complete_pinned_pr_diff',
                {row['diff_file']:row['diff_sha256']},'curated_human_golden_comments'))
        except (ValueError,UnicodeError) as exc:excluded.append({'dataset':MARTIAN,'instance':str(row['pr']),'reason':str(exc).split(':')[0]})
    import pyarrow.parquet as parquet
    with httpx.Client(timeout=45,headers={'User-Agent':'contagion-static-materials/1.0'}) as client:
        body=bounded_get(client,f'https://huggingface.co/datasets/{SWE}/resolve/{SWE_REVISION}/data/test-00000-of-00001.parquet')
        parquet_path=output/'private/swe-verified.parquet';parquet_path.write_bytes(body)
        metadata=json.loads(bounded_get(client,'https://api.github.com/repos/SWE-bench/SWE-bench/commits/main',512*1024));license_revision=metadata['sha']
        license_blob=bounded_get(client,f'https://raw.githubusercontent.com/SWE-bench/SWE-bench/{license_revision}/LICENSE',100000)
        if b'MIT License' not in license_blob:raise ValueError('SWE source license changed')
        (output/'private/swe.LICENSE').write_bytes(license_blob)
        sources.append({'dataset':SWE,'revision':SWE_REVISION,'license_spdx':'MIT','license_file':'swe.LICENSE','license_sha256':sha(license_blob),
                        'license_repository_revision':license_revision,'source_url':'https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified','source_artifact_sha256':sha(body)})
        by_project=defaultdict(list)
        for row in parquet.read_table(parquet_path).to_pylist():by_project[row['repo']].append(row)
        ordered=[]
        for rows in by_project.values():rows.sort(key=lambda row:sha(f'{SPLIT_SEED}:{row["instance_id"]}'.encode()))
        for index in range(max(map(len,by_project.values()))):ordered.extend(rows[index] for _,rows in sorted(by_project.items()) if index<len(rows))
        for row in ordered[:swe_limit]:
            try:
                repository=row['repo'];base=row['base_commit']
                if not safe_repo(repository) or not re.fullmatch(r'[a-f0-9]{40}',base):raise ValueError('unapproved_source')
                matches=list(re.finditer(r'^diff --git a/([^\n]+) b/([^\n]+)\n.*?^@@ -(\d+)',row['patch'],re.M|re.S))
                files=[];documents={};remaining=MAX_CHARACTERS-6000-len(row['problem_statement'])
                for match in matches[:3]:
                    name=match.group(1)
                    if not re.fullmatch(r'[A-Za-z0-9_./-]+',name) or '..' in Path(name).parts:raise ValueError('unsafe_source_path')
                    blob=bounded_get(client,f'https://raw.githubusercontent.com/{repository}/{base}/{quote(name,safe="/")}',2*1024*1024)
                    text=blob.decode();budget=min(30000,remaining)
                    if budget<5000:break
                    excerpt,first,last=source_window(text,int(match.group(3)),budget);remaining-=len(excerpt)
                    files.append({'path':name,'content':excerpt,'sha256':sha(blob),'first_line':first,'last_line':last})
                    documents[name]=sha(blob)
                if not files:raise ValueError('no_base_source')
                payload={'repository':repository,'problem_statement':row['problem_statement'],'source_files':files,
                         'context_policy':'reference_localized_base_windows; source files and start-line windows selected using hidden reference-patch locations, not a full-repository agent evaluation'}
                oracle={key:row[key] for key in ('instance_id','patch','test_patch','FAIL_TO_PASS','PASS_TO_PASS','difficulty')}
                tasks.append(make_task(output,SWE,SWE_REVISION,repository,row['instance_id'],base,payload,oracle,
                    'reference_localized_base_windows',documents,'reference_patch_and_test_plan_not_executed'))
            except (ValueError,UnicodeError,httpx.HTTPError) as exc:
                excluded.append({'dataset':SWE,'instance':row['instance_id'],'reason':type(exc).__name__ if not isinstance(exc,ValueError) else str(exc).split(':')[0]})
    splits=project_splits(tasks)
    for row in tasks:row['split']=splits[row['project_group']]
    catalog={'schema_version':'long-benchmark-materials-1.0','split_seed':SPLIT_SEED,'sources':sources,'tasks':sorted(tasks,key=lambda r:r['id']),'excluded':excluded,
             'agent_tools':[],'upstream_execution':False,'official_benchmark_score':False,
             'limitations':['Static benchmark adaptations, not official benchmark evaluation or scores.','SWE base source windows are reference-localized; affected-file/line hints leak difficulty information. Hidden patches/tests are never agent inputs.',
                            'No execution-based correctness or proof of cheating, collusion, intent or alignment.','Length and horizon are operational loads, not independent reasoning complexity measurements.',
                            'Project-disjoint splits are not evidence of absence from model training data.','Golden references require independent semantic and human adjudication.','Upstream literal text and licenses remain private; redistribution not authorized by this importer.']}
    catalog['catalog_hash']=catalog_hash(catalog);write(output/'catalog.json',catalog);return validate_catalog(output/'catalog.json')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('import');q.add_argument('--out',type=Path,required=True);q.add_argument('--martian',type=Path,required=True);q.add_argument('--swe-limit',type=int,default=96)
    q=sub.add_parser('validate');q.add_argument('--catalog',type=Path,required=True)
    q=sub.add_parser('assemble');q.add_argument('--out',type=Path,required=True);q.add_argument('--base',type=Path,required=True);q.add_argument('--martian',type=Path,required=True)
    a=p.parse_args()
    if a.command=='import':
        if not 1<=a.swe_limit<=180:p.error('Bound source import to1..180 candidates')
        d=import_materials(a.out,a.martian,a.swe_limit)
    elif a.command=='assemble':d=assemble(a.out,a.base,a.martian)
    else:d=validate_catalog(a.catalog)
    print('Validated long static materials:',len(d['tasks']),'tasks;',dict(Counter((r['dataset'],r['split']) for r in d['tasks'])),'no upstream execution or inference.')
