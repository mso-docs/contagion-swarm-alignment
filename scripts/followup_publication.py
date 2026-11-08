"""Closed protocol4 summary export and loopback-only bounded trace inspection."""
import json
from pathlib import Path
from typing import Literal
from pydantic import Field

from contagion.config import digest
from contagion.events import read_events,utc
from contagion.publication import Redactor,sensitive_values
from contagion.research_publication import Closed,StudyRow,StudyAgent
from contagion.storage import verify


class FollowupRun(StudyRow):
    protocol:Literal['4.0-confirmatory']='4.0-confirmatory'
    source_kind:Literal['confirmatory']='confirmatory'
    source_agent:Literal['agent_0','agent_1']
    context_policy:Literal['not_applicable','matched_reset','natural_history']
    detail_file:None=None
    id:str=Field(pattern=r'^[a-f0-9]{16}$')


class Snapshot(Closed):
    schema_version:Literal['confirmatory-public-1.0']='confirmatory-public-1.0'
    generated_utc:str
    runs:list[FollowupRun]
    text_included:Literal[False]=False


def paths(source):return sorted(Path(source).glob('*/rq*/run-*/manifest.json'))


def identifier(root):return digest(str(Path(root).resolve()))[:16]


def export(source,output,env):
    redact=Redactor(sensitive_values(env));rows=[]
    for path in paths(source):
        root=path.parent
        if not (root/'checksum.sha256').is_file():continue
        if not verify(root):raise ValueError('Follow-up integrity failure')
        m=json.loads(path.read_text());config=json.loads((root/'config.snapshot.json').read_text());o=json.loads((root/'outcome.json').read_text());j=config['job'];identity=m['model_identity'];events=read_events(root/'events.jsonl')
        completed=m['status']=='completed';final=o.get('final_agents',[])
        rows.append(FollowupRun(id=identifier(root),model=redact(identity.get('model') or 'unspecified'),backend=identity['backend'],
            worker_label=identity.get('worker_label','local'),model_digest=identity.get('digest'),source_agent=j['source'],context_policy=j.get('context','not_applicable'),
            freeze_hash=m['freeze_hash'],split='development' if config.get('phase')=='integration_precheck' else 'evaluation',task_family=j['family'],case_id=config['case']['case_id'],seed=j['seed'],topology=j['topology'],intervention=j['condition'],
            status=m['status'],calls=m['completed_model_calls'],runtime=m['duration_seconds'],violation=o['any_round_violation'],
            violation_status='observed' if o['any_round_violation'] else 'not_observed' if completed else 'indeterminate',
            parse_failures=sum(e['event_type']=='parse_failure' for e in events),task_success_rate=o['task_success_rate'] if completed else None,
            attempted_forbidden=o['attempted_forbidden'],state_violation=o['actual_state_violation'],executor=j['executor'],
            agents=[StudyAgent(agent_id=a['agent_id'],task_success=a['task_success'],violation=a['violation'],behavior=a['behavior'],messages_received=sum(e['event_type']=='message_delivered' and e.get('receiver_id')==a['agent_id'] for e in events)) for a in final],
            started_utc=m['started_utc'],source_hash=m['source_hash'],http_attempts=m['http_attempts'],rounds=5,
            agent_count=1 if j['topology']=='single' else 5,thinking='disabled',temperature=.2,max_output_tokens=1024,
            messages_delivered=sum(e['event_type']=='message_delivered' for e in events),downstream_adoption_rate=o['final_downstream_violation_rate'] if completed and j['family']=='patch' else None))
    snapshot=Snapshot(generated_utc=utc(),runs=rows);output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.tmp');temporary.write_text(snapshot.model_dump_json(indent=2)+'\n');validate(temporary,env);temporary.replace(output);return snapshot


def validate(path,env=None):
    from scan_privacy import scan_blob
    data=Snapshot.model_validate_json(Path(path).read_text());known=sensitive_values(env or {})
    if scan_blob(Path(path).read_bytes(),public=True,known=known):raise ValueError('Follow-up privacy check')
    redact=Redactor(known)
    if any(redact(r.model)!=r.model for r in data.runs):raise ValueError('Private model label')
    return data


def private_detail(source,ident,env):
    redact=Redactor(sensitive_values(env))
    for path in paths(source):
        root=path.parent
        if identifier(root)!=ident:continue
        if not verify(root):raise ValueError('Unsealed follow-up')
        m=json.loads(path.read_text());config=json.loads((root/'config.snapshot.json').read_text());events=read_events(root/'events.jsonl')
        eligible=[e for e in events if e['event_type'] in {'artifact','message_delivered','inference_response'}];selected=eligible[-128:]
        traces=[{k:(redact(v[:2000]) if k=='content' else v) for k,v in e.items() if k in {'event_id','round','event_type','agent_id','sender_id','receiver_id','content'}} for e in selected]
        return {'schema_version':'1.0','id':ident,'graph':m['graph'],'traces':traces,'text_included':True,'eligible_events':len(eligible),'omitted_events':len(eligible)-len(selected),
                'task_instruction':redact(config['case']['instruction']),'task_input':redact(json.dumps(config['case']['payload']))}
    raise ValueError('Unknown follow-up')
