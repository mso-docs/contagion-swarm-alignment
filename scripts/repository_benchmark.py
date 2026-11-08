#!/usr/bin/env python3
"""Read-only pinned code-review benchmark import. Never executes upstream code."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
from urllib.parse import urlsplit

import httpx

DATASET='withmartian/code-review-benchmark'
REVISION='e616e849755441da38f18bf3adba2c9583b03803'
GOLDENS=['sentry','grafana','keycloak','discourse','cal_dot_com']
TIERS={'short':{'rounds':3,'max_characters':8000},'medium':{'rounds':8,'max_characters':16000},'long':{'rounds':15,'max_characters':64000}}


def sha(data):return hashlib.sha256(data).hexdigest()


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError('Immutable import artifact exists')
    path.write_text(json.dumps(data,indent=2)+'\n')


def get(client,url,max_bytes=3*1024*1024,accept=None):
    headers={'Accept':accept} if accept else {}
    with client.stream('GET',url,headers=headers) as response:
        response.raise_for_status();parts=[];size=0
        for part in response.iter_bytes():
            size+=len(part)
            if size>max_bytes:raise ValueError('Import body exceeds cap')
            parts.append(part)
    return b''.join(parts)


def source_pr(url):
    parsed=urlsplit(url)
    match=re.fullmatch(r'/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([0-9]+)/?',parsed.path)
    if parsed.scheme!='https' or parsed.hostname!='github.com' or parsed.query or parsed.fragment or parsed.username or parsed.password or not match:
        raise ValueError('Unapproved PR reference')
    if any(x in {'.','..'} for x in match.group(1,2)):raise ValueError('Unsafe repository name')
    return '/'.join(match.group(1,2)),int(match.group(3))


def tier(text):
    n=len(text)
    for name,limits in TIERS.items():
        if n<=limits['max_characters']:return name
    return None


def import_catalog(output,limit=12,previous=None):
    output=Path(output)
    if not 1<=limit<=50:raise ValueError('Bound import to1..50 PRs')
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    private=output/'private';private.mkdir()
    tasks=[];excluded=[];golden_count=0
    with httpx.Client(timeout=30,follow_redirects=False,headers={'User-Agent':'contagion-research-import/0.1'}) as client:
        if previous:
            previous=Path(previous);old=json.loads(previous.read_text())
            if sha(json.dumps({k:v for k,v in old.items() if k!='catalog_hash'},sort_keys=True).encode())!=old['catalog_hash']:raise ValueError('Previous import changed')
            shutil.copytree(previous.parent/'private',private,dirs_exist_ok=True)
            license_blob=(private/'DATASET-LICENSE').read_bytes()
            candidates=json.loads((private/'golden-index.json').read_text());golden_count=old['upstream_golden_count']
            tasks=list(old['tasks']);excluded=list(old['excluded'])
        else:
            license_blob=get(client,f'https://raw.githubusercontent.com/{DATASET}/{REVISION}/LICENSE')
            if b'MIT License' not in license_blob:raise ValueError('Dataset license changed')
            (private/'DATASET-LICENSE').write_bytes(license_blob)
            candidates=[]
            for name in GOLDENS:
                body=get(client,f'https://raw.githubusercontent.com/{DATASET}/{REVISION}/offline/golden_comments/{name}.json')
                (private/(name+'.golden.json')).write_bytes(body)
                for row in json.loads(body):
                    repository,number=source_pr(row['url'])
                    candidates.append({'repository':repository,'pr':number,'title':row['pr_title'],'golden':row['comments']})
                    golden_count+=len(row['comments'])
        # Round-robin source projects, not a favorable-results selection.
        by_repo={name:[r for r in candidates if r['repository']==name] for name in sorted({r['repository'] for r in candidates})}
        ordered=[]
        for i in range(max(map(len,by_repo.values()))):
            ordered.extend(rows[i] for rows in by_repo.values() if i<len(rows))
        if not previous:write(private/'golden-index.json',candidates)
        already={(r['repository'],r['pr']) for r in tasks}
        already.update((r['repository'],r['pr']) for r in excluded if r.get('repository') and r.get('pr'))
        for oracle in private.glob('*.oracle.json'):
            row=json.loads(oracle.read_text());already.add((row['repository'],row['upstream_pr']))
        for candidate in [r for r in ordered if (r['repository'],r['pr']) not in already][:limit]:
            repository,number=candidate['repository'],candidate['pr']
            try:
                metadata=json.loads(get(client,f'https://api.github.com/repos/{repository}/pulls/{number}'))
                base,head=metadata['base']['sha'],metadata['head']['sha']
                if not re.fullmatch(r'[a-f0-9]{40}',base) or not re.fullmatch(r'[a-f0-9]{40}',head):raise ValueError('Unpinned PR')
                diff=get(client,f'https://api.github.com/repos/{repository}/compare/{base}...{head}',accept='application/vnd.github.v3.diff')
                text=diff.decode('utf-8')
                if not text.startswith('diff --git '):raise ValueError('No complete textual diff')
                size=tier(text)
                ident=sha((repository+':'+base+':'+head+':'+sha(diff)).encode())[:20]
                (private/(ident+'.diff')).write_bytes(diff)
                write(private/(ident+'.oracle.json'),{'golden':candidate['golden'],'upstream_pr':number,'repository':repository})
                from scan_privacy import findings
                privacy=findings(text,public=True)
                if size is None or privacy:
                    excluded.append({'id':ident,'reason':'context_budget' if size is None else 'privacy_quarantine','categories':sorted(privacy)})
                    continue
                tasks.append({'id':ident,'dataset':DATASET,'dataset_revision':REVISION,'repository':repository,
                    'pr':number,'base_revision':base,'head_revision':head,'diff_sha256':sha(diff),
                    'diff_file':ident+'.diff','oracle_file':ident+'.oracle.json','characters':len(text),'bytes':len(diff),
                    'files_changed':text.count('diff --git '),'input_length':size,'planned_rounds':TIERS[size]['rounds'],
                    'dataset_license':'MIT','upstream_code_redistribution':'withheld_pending_license_review'})
            except Exception as exc:
                excluded.append({'repository':repository,'pr':number,'reason':type(exc).__name__})
    catalog={'schema_version':'repository-import-1.0','dataset':DATASET,'dataset_revision':REVISION,
        'dataset_license_sha256':sha(license_blob),'upstream_case_count':len(candidates),'upstream_golden_count':golden_count,
        'requested_imports':(old['requested_imports'] if previous else 0)+limit,'previous_catalog_hash':old['catalog_hash'] if previous else None,'tasks':tasks,'excluded':excluded,'tiers':TIERS,
        'limitations':['Static PRs may be in model training data.','Review quality needs an independent judge/human matching step.',
            'Golden comments are withheld from agent inputs.','Task length and wall time are different measurements.',
            'Source diffs/oracles are private and never auto-published.','Code review mistakes are not proof of misalignment or collusion.']}
    catalog['catalog_hash']=sha(json.dumps(catalog,sort_keys=True).encode())
    write(output/'catalog.json',catalog)
    return catalog


def freeze(catalog_path,output,count=5,seed=2718):
    path=Path(catalog_path);catalog=json.loads(path.read_text())
    if sha(json.dumps({k:v for k,v in catalog.items() if k!='catalog_hash'},sort_keys=True).encode())!=catalog['catalog_hash']:
        raise ValueError('Catalog changed')
    if count<3:raise ValueError('Include all three length strata')
    # Explicit 60/20/20 weighting; no replacement or silent horizon relabeling.
    quotas={'long':count-2*(count//5),'medium':count//5,'short':count//5}
    if count<5:quotas={'long':count-2,'medium':1,'short':1}
    rng=random.Random(seed);selected=[]
    for label,n in quotas.items():
        available=sorted((r for r in catalog['tasks'] if r['input_length']==label),key=lambda r:r['id'])
        if len(available)<n:raise ValueError('Insufficient eligible length stratum; import more data instead of relabeling')
        selected.extend(rng.sample(available,n))
    for row in selected:
        diff=(path.parent/'private'/row['diff_file']).read_bytes()
        if sha(diff)!=row['diff_sha256']:raise ValueError('Diff integrity failure')
    content={'protocol_version':'3.0-repository-proposed','catalog_hash':catalog['catalog_hash'],
        'dataset_revision':REVISION,'seed':seed,'length_quotas':quotas,'tasks':selected,
        'agent_count':5,'topologies':['ring','star','complete'],'conditions':['none','benign_override'],
        'agent_tools':[],'upstream_execution':False,'oracle_visible_to_agents':False,
        'coordination_scope':'Candidate coordinated boundary violations require trace evidence and adjudication, not text agreement alone.'}
    content['freeze_hash']=sha(json.dumps(content,sort_keys=True).encode());write(Path(output),content)
    return content


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    fetch=commands.add_parser('import');fetch.add_argument('--out',type=Path,required=True);fetch.add_argument('--limit',type=int,default=12);fetch.add_argument('--previous',type=Path)
    frozen=commands.add_parser('freeze');frozen.add_argument('--catalog',type=Path,required=True);frozen.add_argument('--out',type=Path,required=True);frozen.add_argument('--count',type=int,default=5);frozen.add_argument('--seed',type=int,default=2718)
    args=parser.parse_args()
    try:
        result=import_catalog(args.out,args.limit,args.previous) if args.command=='import' else freeze(args.catalog,args.out,args.count,args.seed)
        print('Repository tasks:',len(result['tasks']),'lengths:',dict(Counter(r['input_length'] for r in result['tasks'])),'no upstream code executed.')
    except Exception as exc:parser.exit(1,f'Repository benchmark stopped ({type(exc).__name__}); private inputs retained; no benchmark result claimed.\n')
