"""Offline blinded human-review queue covering intermediate and final artifacts."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import random

from contagion.publication import Redactor
from contagion.storage import verify
from contagion.tasks import make_case,task_instruction
from security_guard import ROOT,private_values


def make_queue(campaign,output,limit=64,seed=919):
    if not 2<=limit<=256:raise ValueError('Review queue cap must be2..256')
    campaign=json.loads((Path(campaign)/'campaign.json').read_text());candidates=[]
    _,env=private_values(ROOT,{})
    from contagion.publication import sensitive_values
    redact=Redactor(sensitive_values(env))
    def clean(value):
        if isinstance(value,str):return redact(value)
        if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
        if isinstance(value,list):return [clean(v) for v in value]
        return value
    for path in sorted(Path(campaign['run_root']).rglob('manifest.json')):
        if not verify(path.parent):raise ValueError('Evidence integrity failure')
        manifest=json.loads(path.read_text())
        if manifest['status']!='completed':continue
        config=json.loads((path.parent/'config.snapshot.json').read_text());events=[json.loads(line) for line in (path.parent/'events.jsonl').read_text().splitlines()]
        case=make_case(config['family'],config['plan']['split'],config['case_index'])
        for event in events:
            if event['event_type']!='artifact':continue
            label=event['metadata']['score'];agent=event['agent_id']
            response=next((e for e in reversed(events[:event['sequence_no']]) if e['event_type']=='inference_response' and e.get('agent_id')==agent),None)
            inbox=[e for e in events[:event['sequence_no']] if e['event_type']=='message_delivered' and e.get('receiver_id')==agent]
            sample=hashlib.sha256((path.parent.name+':'+event['event_id']).encode()).hexdigest()[:16]
            observed=[{'event_id':e['event_id'],'round':e['round'],'content':clean(e.get('content',''))[:2000]} for e in inbox[-20:]]
            inputs={'sample_id':sample,'task_instruction':task_instruction(case,config['protocol_version']),
                'task_input':clean(case.payload),'round':event['round'],'observed_messages':observed,
                'response_event_id':response['event_id'] if response else event['event_id'],
                'response':clean(response['content'] if response else event.get('content',''))[:4000],
                'context_policy':'At most20 past delivered messages for the subject; no future events, model identity, intervention metadata or oracle labels.'}
            oracle={'sample_id':sample,'family':case.family,'condition':config['intervention'],'run_id':path.parent.name,
                'artifact_event_id':event['event_id'],'round':event['round'],'violation':label['violation'],'behavior':label['behavior']}
            candidates.append((inputs,oracle))
    rng=random.Random(seed);positive=[p for p in candidates if p[1]['violation']];other=[p for p in candidates if not p[1]['violation']]
    rng.shuffle(positive);rng.shuffle(other);selected=positive[:limit//2]+other[:limit-min(len(positive),limit//2)];rng.shuffle(selected)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'review_inputs.json').write_text(json.dumps({'schema_version':'blinded-artifact-audit-1.0','samples':[p[0] for p in selected]},indent=2)+'\n')
    (output/'oracle_labels.private.json').write_text(json.dumps({'seed':seed,'population_artifacts':len(candidates),'sampling':'Enriched any-round flag audit; not a prevalence representative sample.','labels':[p[1] for p in selected]},indent=2)+'\n')
    with (output/'human_labels.csv').open('w') as stream:
        writer=csv.writer(stream);writer.writerow(['sample_id','behavior','reason']);writer.writerows((p[0]['sample_id'],'','') for p in selected)
    return {'samples':len(selected),'flagged_samples':sum(p[1]['violation'] for p in selected),'population_artifacts':len(candidates),'human_labels_completed':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--campaign',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--limit',type=int,default=64);args=parser.parse_args()
    print(json.dumps(make_queue(args.campaign,args.out,args.limit)))
