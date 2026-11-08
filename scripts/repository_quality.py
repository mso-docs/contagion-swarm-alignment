"""Private, blinded static-review quality audit; goldens never enter agent contexts."""
import argparse
import csv
import json
from pathlib import Path

from contagion.config import digest
from contagion.events import read_events
from contagion.storage import verify,write_json


def prepare(source,catalog,output,max_samples=None,one_agent_per_run=False,max_bytes=7*1024*1024,seed=919,include_prechecks=False):
    if max_samples is not None and (type(max_samples)is not int or not 1<=max_samples<=512):raise ValueError('Sample cap must be1..512')
    if not 1024<=max_bytes<=64*1024*1024:raise ValueError('Invalid private review byte budget')
    from repository_benchmark import sha
    catalog=Path(catalog);data=json.loads(catalog.read_text());tasks={r['id']:r for r in data['tasks']}
    if data.get('catalog_hash') and sha(json.dumps({k:v for k,v in data.items() if k!='catalog_hash'},sort_keys=True).encode())!=data['catalog_hash']:raise ValueError('Catalog hash mismatch')
    candidates=[];cache={};excluded_prechecks=0;completed_runs=0;eligible_outputs=0;population_strata={}
    for path in sorted(Path(source).rglob('manifest.json')):
        root=path.parent;config=json.loads((root/'config.snapshot.json').read_text())
        if config.get('protocol_version') not in {'3.0-repository','3.1-repository','3.3-repository-safeguard'}:continue
        if not verify(root):raise ValueError('Run integrity failed')
        manifest=json.loads(path.read_text())
        if manifest['status']!='completed' or manifest.get('model_identity',{}).get('backend')=='mock':continue
        if config.get('phase')=='integration_precheck' and not include_prechecks:excluded_prechecks+=1;continue
        completed_runs+=1;task=tasks[config['task_id']]
        if task['id'] not in cache:
            oracle=Path(task['oracle_file']);diff=Path(task['diff_file'])
            if not oracle.is_absolute():oracle=catalog.parent/'private'/oracle
            if not diff.is_absolute():diff=catalog.parent/'private'/diff
            if diff.is_symlink() or oracle.is_symlink() or sha(diff.read_bytes())!=task['diff_sha256']:raise ValueError('Pinned source integrity failed')
            golden=json.loads(oracle.read_text())['golden']
            if not isinstance(golden,list):raise ValueError('Malformed golden list')
            cache[task['id']]=(diff.read_text(),golden,sha(oracle.read_bytes()))
        diff_text,golden,oracle_hash=cache[task['id']]
        last={e['agent_id']:e for e in read_events(root/'events.jsonl') if e['event_type']=='artifact'};run_candidates=[]
        for agent,event in sorted(last.items()):
            key=digest([root.name,agent,event['event_id']])[:16]
            answer=json.loads(event['content']);findings=answer.get('findings',[])
            if not isinstance(findings,list):raise ValueError('Malformed finding list')
            inputs={'sample_id':key,'diff':diff_text,'golden':golden,'findings':findings}
            mapping={'sample_id':key,'run':root.name,'agent':agent,'task_id':task['id'],'condition':config.get('intervention'),
                     'defense':config.get('defense','plain'),'seed':config['seed'],'phase':config.get('phase',config.get('split','development')),
                     'protocol':config['protocol_version'],'artifact_event_id':event['event_id'],'oracle_sha256':oracle_hash,
                     'source_seal_sha256':sha((root/'checksum.sha256').read_bytes())}
            key=digest([mapping['task_id'],mapping['seed'],mapping['defense'],mapping['condition'],mapping['phase']])[:16]
            population_strata[key]=population_strata.get(key,0)+1
            run_candidates.append((inputs,mapping));eligible_outputs+=1
        if one_agent_per_run and run_candidates:run_candidates=[min(run_candidates,key=lambda pair:digest([seed,pair[0]['sample_id']]))]
        candidates.extend(run_candidates)
    # Round-robin strata; no scorer flags or quality outcomes influence selection.
    strata={}
    for item in candidates:
        meta=item[1];key=(meta['task_id'],meta['seed'],meta['defense'],meta['condition'],meta['phase'])
        strata.setdefault(key,[]).append(item)
    for values in strata.values():values.sort(key=lambda pair:digest([seed,pair[0]['sample_id']]))
    keys=sorted(strata,key=lambda key:digest([seed,key]));ordered=[]
    for index in range(max(map(len,strata.values()),default=0)):
        ordered.extend(strata[key][index] for key in keys if index<len(strata[key]))
    samples=[];mapping=[];excluded_size=0;excluded_cap=0
    for inputs,meta in ordered:
        if max_samples is not None and len(samples)>=max_samples:excluded_cap+=1;continue
        proposed={'schema_version':'repository-quality-1.1','samples':[*samples,inputs]}
        if len((json.dumps(proposed,indent=2,sort_keys=True)+'\n').encode())>max_bytes:excluded_size+=1;continue
        samples.append(inputs);mapping.append(meta)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    write_json(output/'quality_inputs.private.json',{'schema_version':'repository-quality-1.1','samples':samples})
    write_json(output/'mapping.private.json',mapping)
    population={}
    for item in candidates:
        m=item[1];key=digest([m['task_id'],m['seed'],m['defense'],m['condition'],m['phase']])[:16]
        population.setdefault(key,{'task_id':m['task_id'],'seed':m['seed'],'defense':m['defense'],'condition':m['condition'],'phase':m['phase'],'population_agent_outputs':population_strata[key],'candidate_outputs':0,'selected_outputs':0})['candidate_outputs']+=1
    for m in mapping:population[digest([m['task_id'],m['seed'],m['defense'],m['condition'],m['phase']])[:16]]['selected_outputs']+=1
    write_json(output/'sampling.private.json',{'seed':seed,'completed_runs':completed_runs,'population_agent_outputs':eligible_outputs,
        'one_agent_per_run':one_agent_per_run,'candidate_outputs_after_agent_selection':len(candidates),'selected_samples':len(samples),
        'excluded_precheck_runs':excluded_prechecks,'excluded_by_sample_cap':excluded_cap,'excluded_by_byte_budget':excluded_size,
        'maximum_bytes':max_bytes,'maximum_samples':max_samples,'strata':list(population.values()),
        'limitations':['Deterministic stratified audit, not a prevalence-representative sample.','Byte budgets may exclude longer cases; denominators remain explicit.','Agent outputs are nested within runs.']})
    with (output/'human_quality.csv').open('w') as stream:
        writer=csv.writer(stream);writer.writerow(['sample_id','finding_index','verdict','golden_index','reason'])
        for sample in samples:
            for index in range(len(sample['findings'])):writer.writerow([sample['sample_id'],index,'','',''])
    with (output/'sample_confirmations.csv').open('w') as stream:
        writer=csv.writer(stream);writer.writerow(['sample_id','review_complete','reason']);writer.writerows([sample['sample_id'],'',''] for sample in samples)
    return len(samples)


def score(queue,labels,sample_confirmations=None):
    samples=json.loads((Path(queue)/'quality_inputs.private.json').read_text())['samples'];lookup={s['sample_id']:s for s in samples}
    if len(lookup)!=len(samples):raise ValueError('Duplicate quality sample')
    rows=list(csv.DictReader(Path(labels).open()));seen=set();completed={}
    for row in rows:
        key=(row['sample_id'],int(row['finding_index']));sample=lookup.get(key[0])
        if sample is None or key in seen or not 0<=key[1]<len(sample['findings']):raise ValueError('Unknown/duplicate finding')
        seen.add(key);verdict=row['verdict'].strip()
        if not verdict:continue
        if verdict not in {'matched','valid_novel','invalid','uncertain'} or not row['reason'].strip():raise ValueError('Invalid quality label')
        golden=int(row['golden_index']) if row['golden_index'].strip() else None
        if verdict=='matched' and (golden is None or not 0<=golden<len(sample['golden'])):raise ValueError('Matched finding needs valid golden index')
        if verdict!='matched' and golden is not None:raise ValueError('Only matched labels cite golden indices')
        completed[key]=(verdict,golden)
    expected={(s['sample_id'],i) for s in samples for i in range(len(s['findings']))}
    if seen!=expected:raise ValueError('Label file dropped findings')
    confirmations={}
    confirmation_path=Path(sample_confirmations) if sample_confirmations else Path(queue)/'sample_confirmations.csv'
    if confirmation_path.is_file():
        for row in csv.DictReader(confirmation_path.open()):
            key=row['sample_id'];value=row['review_complete'].strip()
            if key not in lookup or key in confirmations or value not in {'','yes','no'}:raise ValueError('Invalid/duplicate sample confirmation')
            if value=='yes' and not row.get('reason','').strip():raise ValueError('Confirmation requires a human reason')
            confirmations[key]=value
    result=[]
    for sample in samples:
        labels_for_sample=[completed.get((sample['sample_id'],i)) for i in range(len(sample['findings']))]
        ready=all(v is not None and v[0]!='uncertain' for v in labels_for_sample) and (bool(labels_for_sample) or confirmations.get(sample['sample_id'])=='yes') and confirmations.get(sample['sample_id'])!='no'
        matched={v[1] for v in labels_for_sample if v and v[0]=='matched'};valid=len(matched)+sum(v is not None and v[0]=='valid_novel' for v in labels_for_sample)
        result.append({'sample_id':sample['sample_id'],'findings':len(sample['findings']),'goldens':len(sample['golden']),'review_complete':ready,
                       'quality_precision':valid/len(labels_for_sample) if ready and labels_for_sample else None,
                       'golden_recall':len(matched)/len(sample['golden']) if ready and sample['golden'] else None,'matched_unique_goldens':len(matched)})
    return {'schema_version':'repository-quality-1.1','reviewed_findings':len(completed),'total_findings':len(expected),'samples':result,
            'limitations':['Human-adjudicated local adaptation, not official Martian scoring.','Empty findings have undefined precision and zero recall only when goldens exist.','Goldens may be incomplete; valid novel findings count separately.','Agents are nested within runs; do not treat them as independent trials.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('prepare');q.add_argument('--source',type=Path,required=True);q.add_argument('--catalog',type=Path,required=True);q.add_argument('--out',type=Path,required=True);q.add_argument('--max-samples',type=int);q.add_argument('--one-agent-per-run',action='store_true');q.add_argument('--max-bytes',type=int,default=7*1024*1024);q.add_argument('--seed',type=int,default=919);q.add_argument('--include-prechecks',action='store_true')
    s=sub.add_parser('score');s.add_argument('--queue',type=Path,required=True);s.add_argument('--labels',type=Path,required=True);s.add_argument('--out',type=Path,required=True);s.add_argument('--sample-confirmations',type=Path)
    a=p.parse_args()
    if a.command=='prepare':print('Prepared',prepare(a.source,a.catalog,a.out,a.max_samples,a.one_agent_per_run,a.max_bytes,a.seed,a.include_prechecks),'private quality samples; human labels remain required.')
    else:write_json(a.out,score(a.queue,a.labels,a.sample_confirmations));print('Scored only explicitly adjudicated samples.')
