"""Link all eligible paired swarm requests to private neural replay jobs; no inference.

A plan is not an activation measurement. Replaying a different checkpoint or
precision never recovers original Ollama hidden states.
"""
import argparse
import json
from pathlib import Path

from contagion.config import digest
from contagion.events import read_events
from contagion.storage import verify,write_json


def prepare(source,output,model_id,revision,layers=(0,5,11),max_characters=12000):
    import re
    if not model_id or not re.fullmatch(r'[a-f0-9]{40}',revision):raise ValueError('Pin a checkpoint ID and immutable revision')
    groups={};excluded=[]
    for path in sorted(Path(source).rglob('manifest.json')):
        root=path.parent;config=json.loads((root/'config.snapshot.json').read_text())
        if config.get('protocol_version')!='2.6':continue
        if not verify(root):raise ValueError('Source integrity failed')
        manifest=json.loads(path.read_text())
        if manifest['status']!='completed':excluded.append({'run_id':root.name,'reason':'not_completed'});continue
        key=digest({**config,'intervention':'paired'})
        arms=groups.setdefault(key,{})
        if config['intervention'] in arms:raise ValueError('Duplicate completed matched arm')
        arms[config['intervention']]=(root,manifest,read_events(root/'events.jsonl'))
    jobs=[]
    for pair,arms in groups.items():
        if set(arms)!={'none','benign_override'}:excluded.append({'pair':pair,'reason':'missing_matched_arm'});continue
        clean,corrupt=arms['none'],arms['benign_override']
        if clean[1]['model_identity']!=corrupt[1]['model_identity'] or clean[1]['source_hash']!=corrupt[1]['source_hash']:raise ValueError('Unmatched source/model')
        requests=[{(e['agent_id'],e['round']):e for e in arm[2] if e['event_type']=='inference_requested'} for arm in [clean,corrupt]]
        for key in sorted(set(requests[0])&set(requests[1])):
            messages=[requests[i][key]['metadata']['messages'] for i in [0,1]]
            # Exact structured histories retained; worker must apply checkpoint chat template.
            if max(sum(len(m['content']) for m in msgs) for msgs in messages)>max_characters:
                excluded.append({'pair':pair,'agent':key[0],'round':key[1],'reason':'context_character_cap_no_truncation'});continue
            if messages[0]==messages[1]:continue
            jobs.append({'id':digest([pair,*key])[:20],'agent':key[0],'round':key[1],'clean_run':clean[0].name,'corrupt_run':corrupt[0].name,
                         'clean_request_event':requests[0][key]['event_id'],'corrupt_request_event':requests[1][key]['event_id'],
                         'clean_messages':messages[0],'corrupt_messages':messages[1],'source_model':clean[1]['model_identity'],
                         'clean_seal':digest((clean[0]/'checksum.sha256').read_text()),'corrupt_seal':digest((corrupt[0]/'checksum.sha256').read_text())})
    result={'schema_version':'neural-replay-plan-1.0','checkpoint':model_id,'revision':revision,'layers':list(layers),'jobs':jobs,'excluded':excluded,
            'planned_captures':len(jobs)*len(layers),'measured_captures':0,
            'required_before_capture':['Check architecture/TransformerLens compatibility and memory.','Apply pinned checkpoint tokenizer/chat template without truncation.',
              'Predeclare target token and explicit clean/corrupt token alignment.','Validate raw/bridge parity, no-op, position and negative controls.',
              'Record quantization/dtype/backend differences; replay is not original Ollama state.'],
            'limitations':['No neural or mechanistic result is produced by planning.','This is retrospective matched replay; effects do not establish spontaneous collusion.']}
    result['plan_hash']=digest(result);Path(output).parent.mkdir(parents=True,exist_ok=True);write_json(Path(output),result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--model-id',required=True);p.add_argument('--revision',required=True);a=p.parse_args()
    result=prepare(a.source,a.out,a.model_id,a.revision);print('Planned',result['planned_captures'],'linked replays; measured captures:0. Compatibility/worker validation required.')
