"""Private, blinded static-review quality audit; goldens never enter agent contexts."""
import argparse
import csv
import json
from pathlib import Path

from contagion.config import digest
from contagion.events import read_events
from contagion.storage import verify,write_json


def prepare(source,catalog,output):
    catalog=Path(catalog);data=json.loads(catalog.read_text());tasks={r['id']:r for r in data['tasks']};samples=[];mapping=[]
    for path in sorted(Path(source).rglob('manifest.json')):
        root=path.parent;config=json.loads((root/'config.snapshot.json').read_text())
        if config.get('protocol_version') not in {'3.0-repository','3.1-repository'}:continue
        if not verify(root):raise ValueError('Run integrity failed')
        manifest=json.loads(path.read_text())
        if manifest['status']!='completed' or manifest.get('model_identity',{}).get('backend')=='mock':continue
        task=tasks[config['task_id']]
        oracle=Path(task['oracle_file']);diff=Path(task['diff_file'])
        if not oracle.is_absolute():oracle=catalog.parent/'private'/oracle
        if not diff.is_absolute():diff=catalog.parent/'private'/diff
        from repository_benchmark import sha
        if sha(diff.read_bytes())!=task['diff_sha256']:raise ValueError('Diff integrity failed')
        last={e['agent_id']:e for e in read_events(root/'events.jsonl') if e['event_type']=='artifact'}
        for agent,event in sorted(last.items()):
            key=digest([root.name,agent,event['event_id']])[:16]
            answer=json.loads(event['content']);findings=answer.get('findings',[])
            if not isinstance(findings,list):raise ValueError('Malformed finding list')
            # Deliberately private: full diff and goldens are needed for quality review.
            samples.append({'sample_id':key,'diff':diff.read_text(),'golden':json.loads(oracle.read_text())['golden'],'findings':findings})
            mapping.append({'sample_id':key,'run':root.name,'agent':agent,'task_id':task['id'],'condition':config.get('intervention'),'artifact_event_id':event['event_id']})
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    write_json(output/'quality_inputs.private.json',{'schema_version':'repository-quality-1.0','samples':samples})
    write_json(output/'mapping.private.json',mapping)
    with (output/'human_quality.csv').open('w') as stream:
        writer=csv.writer(stream);writer.writerow(['sample_id','finding_index','verdict','golden_index','reason'])
        for sample in samples:
            for index in range(len(sample['findings'])):writer.writerow([sample['sample_id'],index,'','',''])
    return len(samples)


def score(queue,labels):
    samples=json.loads((Path(queue)/'quality_inputs.private.json').read_text())['samples'];lookup={s['sample_id']:s for s in samples};rows=list(csv.DictReader(Path(labels).open()));seen=set();completed={}
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
    result=[]
    for sample in samples:
        labels_for_sample=[completed.get((sample['sample_id'],i)) for i in range(len(sample['findings']))]
        ready=all(v is not None and v[0]!='uncertain' for v in labels_for_sample)
        matched={v[1] for v in labels_for_sample if v and v[0]=='matched'};valid=len(matched)+sum(v is not None and v[0]=='valid_novel' for v in labels_for_sample)
        result.append({'sample_id':sample['sample_id'],'findings':len(sample['findings']),'goldens':len(sample['golden']),'review_complete':ready,
                       'quality_precision':valid/len(labels_for_sample) if ready and labels_for_sample else None,
                       'golden_recall':len(matched)/len(sample['golden']) if ready and sample['golden'] else None,'matched_unique_goldens':len(matched)})
    return {'schema_version':'repository-quality-1.0','reviewed_findings':len(completed),'total_findings':len(expected),'samples':result,
            'limitations':['Human-adjudicated local adaptation, not official Martian scoring.','Empty findings have undefined precision and zero recall only when goldens exist.','Goldens may be incomplete; valid novel findings count separately.','Agents are nested within runs; do not treat them as independent trials.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('prepare');q.add_argument('--source',type=Path,required=True);q.add_argument('--catalog',type=Path,required=True);q.add_argument('--out',type=Path,required=True)
    s=sub.add_parser('score');s.add_argument('--queue',type=Path,required=True);s.add_argument('--labels',type=Path,required=True);s.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.command=='prepare':print('Prepared',prepare(a.source,a.catalog,a.out),'private quality samples; human labels remain required.')
    else:write_json(a.out,score(a.queue,a.labels));print('Scored only explicitly adjudicated samples.')
