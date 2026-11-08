"""Closed, metadata-only repository-review export; source code and oracles stay private."""
import hashlib
import json
from pathlib import Path
from statistics import median
from typing import Literal

from pydantic import BaseModel,ConfigDict,Field

from contagion.events import read_events,utc
from contagion.publication import Redactor,sensitive_values
from contagion.storage import verify

_ROW_CACHE={}


def row_signature(directory,policy):
    names=('manifest.json','config.snapshot.json','outcome.json','events.jsonl','checksum.sha256')
    if any((directory/name).is_symlink() for name in names):raise ValueError('Repository source symlink rejected')
    stats=tuple((name,(directory/name).stat().st_size,(directory/name).stat().st_mtime_ns) for name in names)
    return (str(directory.resolve()),policy,hashlib.sha256((directory/'checksum.sha256').read_bytes()).hexdigest(),stats)


class Closed(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)


class Agent(Closed):
    agent_id:str=Field(pattern=r'^agent_[0-9]{1,3}$')
    task_success:None=None
    violation:bool
    marker_adoption:bool|None=None
    unsupported_execution_claim:bool|None=None
    behavior:Literal['violation','ambiguous']
    messages_received:int=Field(ge=0)


class RepositoryRun(Closed):
    id:str=Field(pattern=r'^[a-f0-9]{16}$')
    source_kind:Literal['repository_review']='repository_review'
    protocol:Literal['3.0-repository','3.1-repository','3.3-repository-safeguard','3.4-benchmark-static']='3.0-repository'
    task_family:Literal['code_review','issue_diagnosis']='code_review'
    task_kind:Literal['code_review','issue_diagnosis']='code_review'
    source_dataset:Literal['legacy_unspecified','withmartian/code-review-benchmark','princeton-nlp/SWE-bench_Verified']='legacy_unspecified'
    memory_policy:Literal['full_history','original_task_plus_last_two_own_rounds']='full_history'
    context_selection:Literal['legacy_unspecified','complete_pinned_pr_diff','reference_localized_base_windows']='legacy_unspecified'
    official_benchmark_score:Literal[False]=False
    model:str
    backend:Literal['mock','ollama']
    model_digest:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    worker_label:Literal['primary','secondary','local','unspecified']='unspecified'
    split:Literal['development','evaluation']='development'
    defense:Literal['not_applicable','plain','source_attribution']='not_applicable'
    phase:Literal['development','integration_precheck','evaluation']='development'
    final_any_violation:bool|None=None
    downstream_final_boundary_violation_rate:float|None=Field(default=None,ge=0,le=1)
    agent_count:int=Field(ge=5,le=5)
    topology:Literal['ring','star','complete']
    intervention:Literal['none','benign_override']
    seed:int
    status:Literal['completed','failed','budget_exhausted']
    rounds:int=Field(ge=1,le=30)
    input_length:Literal['short','medium','long']
    input_characters:int=Field(ge=0,le=70000)
    repository:str=Field(pattern=r'^(?:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+|\[REDACTED\])$')
    dataset_revision:str=Field(pattern=r'^[a-f0-9]{40}$')
    case_id:str=Field(pattern=r'^[a-f0-9]{20}$')
    freeze_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    source_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    started_utc:str
    ended_utc:str|None=None
    calls:int=Field(ge=0)
    attempted_calls:int=Field(ge=0)
    http_attempts:int=Field(ge=0)
    runtime:float=Field(ge=0)
    parse_failures:int=Field(ge=0)
    median_call_seconds:float|None=Field(default=None,ge=0)
    generated_tokens:int|None=Field(default=None,ge=0)
    generation_tokens_per_second:None=None
    messages_delivered:int=Field(ge=0)
    violation:bool
    violation_status:Literal['observed','not_observed','indeterminate']
    task_success_rate:None=None
    attempted_forbidden:bool=False
    state_violation:Literal[False]=False
    executor:Literal['deny']='deny'
    detail_file:None=None
    downstream_adoption_rate:float|None=Field(default=None,ge=0,le=1)
    downstream_clean_rate:None=None
    agents:list[Agent]=Field(max_length=5)
    benchmark_quality_status:Literal['not_scored']='not_scored'
    collusion_status:Literal['not_adjudicated']='not_adjudicated'


class RepositorySnapshot(Closed):
    schema_version:Literal['repository-public-1.0']='repository-public-1.0'
    generated_utc:str
    runs:list[RepositoryRun]
    text_included:Literal[False]=False
    limitations:list[str]


def export_repository_runs(source,output,env):
    redact=Redactor(sensitive_values(env));rows=[]
    policy=hashlib.sha256(json.dumps(sorted(redact.values)).encode()).hexdigest()
    for path in sorted(Path(source).rglob('manifest.json')):
        if not (path.parent/'checksum.sha256').is_file():continue
        manifest=json.loads(path.read_text())
        if manifest.get('protocol_version') not in {'3.0-repository','3.1-repository','3.3-repository-safeguard','3.4-benchmark-static'}:continue
        signature=row_signature(path.parent,policy)
        if signature in _ROW_CACHE:
            rows.append(RepositoryRun.model_validate_json(_ROW_CACHE[signature]));continue
        if not verify(path.parent):raise ValueError('Repository run checksum failed')
        config=json.loads((path.parent/'config.snapshot.json').read_text());outcome=json.loads((path.parent/'outcome.json').read_text())
        events=read_events(path.parent/'events.jsonl');responses=[e for e in events if e['event_type']=='inference_response']
        durations=[e.get('metadata',{}).get('duration_seconds') for e in responses];counts=[e.get('metadata',{}).get('eval_count') for e in responses]
        identity=manifest['model_identity'];task=config['task_metadata']
        final_agents=outcome['final_agents']
        downstream=[a for a in final_agents if a['agent_id']!='agent_0']
        marker_rate=(sum(a['marker_adoption'] for a in downstream)/4 if manifest['protocol_version']=='3.4-benchmark-static'
                     and manifest['status']=='completed' and len(downstream)==4 and all(type(a.get('marker_adoption')) is bool for a in downstream) else None)
        rows.append(RepositoryRun(id=hashlib.sha256(manifest['run_id'].encode()).hexdigest()[:16],model=redact(identity['model']),
            protocol=manifest['protocol_version'],backend=identity['backend'],model_digest=identity.get('digest'),worker_label=identity.get('worker_label','unspecified'),
            task_family=config.get('task_kind','code_review'),task_kind=config.get('task_kind','code_review'),
            source_dataset=task.get('dataset','legacy_unspecified'),memory_policy=config.get('memory_policy','full_history'),
            context_selection=task.get('context_selection','legacy_unspecified'),
            split=config.get('split','development'),defense=config.get('defense','not_applicable'),phase=config.get('phase','development'),
            final_any_violation=outcome.get('final_any_violation'),downstream_final_boundary_violation_rate=outcome.get('downstream_final_violation_rate'),
            agent_count=5,topology=config['topology'],intervention=config['intervention'],seed=config['seed'],status=manifest['status'],
            rounds=config['rounds'],input_length=config['input_length'],input_characters=task['characters'],repository=redact(task['repository']),
            dataset_revision=task['dataset_revision'],case_id=config['task_id'],freeze_hash=config['registry_freeze_hash'],source_hash=manifest['source_hash'],
            started_utc=manifest['started_utc'],ended_utc=manifest.get('ended_utc'),calls=manifest['completed_model_calls'],attempted_calls=manifest['completed_model_calls'],
            http_attempts=manifest['http_attempts'],runtime=manifest['duration_seconds'],parse_failures=manifest['parse_failures'],
            median_call_seconds=median(durations) if durations and all(v is not None for v in durations) else None,
            generated_tokens=sum(counts) if counts and all(v is not None for v in counts) else None,
            messages_delivered=sum(e['event_type']=='message_delivered' for e in events),violation=outcome['any_violation'],
            downstream_adoption_rate=marker_rate,
            violation_status='observed' if outcome['any_violation'] else 'not_observed' if manifest['status']=='completed' and not manifest['parse_failures'] else 'indeterminate',
            agents=[Agent(agent_id=a['agent_id'],violation=a['violation'],marker_adoption=a.get('marker_adoption'),
                unsupported_execution_claim=a.get('unsupported_execution_claim'),behavior='violation' if a['violation'] else 'ambiguous',
                messages_received=sum(e['event_type']=='message_delivered' and e.get('receiver_id')==a['agent_id'] for e in events)) for a in outcome['final_agents']]))
        _ROW_CACHE[signature]=rows[-1].model_dump_json()
    if len(_ROW_CACHE)>20000:
        for key in list(_ROW_CACHE)[:len(_ROW_CACHE)-10000]:del _ROW_CACHE[key]
    snapshot=RepositorySnapshot(generated_utc=utc(),runs=rows,limitations=[
        'External static benchmark adaptations; not official benchmark scores. No upstream code or tests executed.',
        'Issue diagnosis uses reference-localized base windows; affected-file and line hints change task difficulty.',
        'Golden comments/source diffs remain private; model review quality is not scored without independent matching.',
        'Boundary failures are not proof of intent or collusion. Coordination requires evidence and adjudication.',
        'Longer horizon and larger input are recorded separately; static training-data contamination is possible.'])
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists() and validate_repository_snapshot(output,env).runs==snapshot.runs:return snapshot
    temporary=output.with_suffix('.tmp');temporary.write_text(snapshot.model_dump_json(indent=2)+'\n');validate_repository_snapshot(temporary,env);temporary.replace(output)
    return snapshot


def validate_repository_snapshot(path,env):
    from scan_privacy import scan_blob
    data=Path(path).read_bytes();snapshot=RepositorySnapshot.model_validate_json(data)
    redact=Redactor(sensitive_values(env))
    if any(redact(r.model)!=r.model or redact(r.repository)!=r.repository for r in snapshot.runs) or scan_blob(data,public=True):
        raise ValueError('Repository snapshot privacy lint failed')
    if len({r.id for r in snapshot.runs})!=len(snapshot.runs):raise ValueError('Duplicate repository run IDs')
    return snapshot


def private_detail(source,ident,env):
    if len(ident)!=16 or any(c not in '0123456789abcdef' for c in ident):raise ValueError('Invalid run reference')
    redact=Redactor(sensitive_values(env))
    for path in Path(source).rglob('manifest.json'):
        manifest=json.loads(path.read_text())
        if hashlib.sha256(manifest['run_id'].encode()).hexdigest()[:16]!=ident:continue
        if not verify(path.parent):raise ValueError('Repository trace integrity failed')
        config=json.loads((path.parent/'config.snapshot.json').read_text())
        allowed={'artifact','message_delivered','message_generated','intervention_applied','inference_response','parse_failure','run_failure'}
        events=[e for e in read_events(path.parent/'events.jsonl') if e['event_type'] in allowed];traces=[]
        for e in events[-2000:]:
            text=redact(e.get('content',''));item={k:e[k] for k in ['event_id','round','event_type','agent_id','sender_id','receiver_id'] if k in e}
            limit=8192 if config.get('protocol_version')=='3.4-benchmark-static' else 1200
            item.update(content=text[:limit],content_truncated=len(text)>limit);traces.append(item)
        task='Pinned software issue with base source windows' if config.get('task_kind')=='issue_diagnosis' else 'Pinned static code-review diff'
        return {'schema_version':'1.0','id':ident,'task_instruction':redact(config['instruction']),
            'task_input':task+'; source text and hidden references stay outside this redacted trace view.',
            'traces':traces,'eligible_events':len(events),'omitted_events':max(0,len(events)-len(traces)),
            'text_included':True,'graph':manifest['graph']}
    raise FileNotFoundError('Unknown repository run')
