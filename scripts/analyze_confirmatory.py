"""Exact paired run-level follow-up summaries; no independent-agent significance."""
import argparse
import json
from pathlib import Path
from collections import defaultdict
from contagion.storage import verify,write_json


def analyze(source):
    rows=[];pairs=defaultdict(dict)
    for path in sorted(Path(source).glob('run-*/manifest.json')):
        root=path.parent
        if not verify(root):raise ValueError('Unsealed follow-up')
        manifest=json.loads(path.read_text());config=json.loads((root/'config.snapshot.json').read_text());outcome=json.loads((root/'outcome.json').read_text());job=config['job']
        row={'run_id':root.name,'backend':manifest['model_identity']['backend'],'freeze_hash':manifest['freeze_hash'],**job,**outcome}
        rows.append(row)
        if manifest['status']!='completed':continue
        key=(row['freeze_hash'],row['backend'],job['family'],job['case'],job['seed'],job['topology'],job['source'],job['executor'],job.get('context'))
        if job['condition'] in pairs[key]:raise ValueError('Duplicate completed pair')
        pairs[key][job['condition']]=row
    paired=[]
    for key,arms in pairs.items():
        if set(arms)!={'none','benign_override'}:continue
        c,i=arms['none'],arms['benign_override']
        paired.append({'family':c['family'],'case':c['case'],'seed':c['seed'],'topology':c['topology'],'source':c['source'],'executor':c['executor'],'context':c.get('context'),
                       'any_round_violation_difference':int(i['any_round_violation'])-int(c['any_round_violation']),
                       'task_success_difference':i['task_success_rate']-c['task_success_rate'],
                       'state_violation_difference':int(i['actual_state_violation'])-int(c['actual_state_violation'])})
    return {'schema_version':'confirmatory-analysis-1.0','attempts':len(rows),'completed':sum(r['status']=='completed' for r in rows),'pairs':paired,'rows':rows,
            'limitations':['Exact run-level paired differences; no agent-level significance.','Cases/seeds recur across topologies and source placements.','Mock results are software validation only.','Primary endpoint and any-round deviations remain separate.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();result=analyze(a.source);write_json(a.out,result);print(result['completed'],'completed runs;',len(result['pairs']),'matched control/injection pairs')
