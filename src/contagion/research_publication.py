"""Closed-schema public export for protocol-2 studies, review and measured neural data."""
import hashlib
import json
from statistics import median
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import digest
from .events import utc
from .neural import validate_numeric_capture
from .publication import Redactor, sensitive_values
from .studies import summarize_study


class Closed(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)


class StudyAgent(Closed):
    agent_id: str = Field(pattern=r'^agent_[0-9]{1,3}$')
    task_success: bool
    violation: bool
    behavior: Literal['compliant','violation','refusal','ambiguous','unscorable']
    messages_received: int = Field(ge=0)


class StudyRow(Closed):
    id: str
    model: str
    backend: Literal['mock','ollama','openai']
    worker_label: Literal['primary','secondary','local','unspecified'] = 'unspecified'
    model_digest: str | None = Field(default=None,pattern=r'^(sha256:)?[a-f0-9]{64}$')
    protocol: Literal['2.0','2.1','2.2','2.3','2.4','2.5','2.6'] = '2.0'
    agent_count: int = Field(default=5,ge=1,le=128)
    freeze_hash: str
    size_comparison_group: str | None = None
    split: Literal['development','evaluation']
    task_family: Literal['catalog','provenance','patch','record']
    case_id: str
    seed: int
    topology: Literal['ring','star','complete','single']
    intervention: Literal['none','benign_override']
    status: Literal['completed','failed','budget_exhausted']
    calls: int
    runtime: float
    violation: bool
    violation_status: Literal['observed','not_observed','indeterminate'] = 'not_observed'
    parse_failures: int = 0
    task_success_rate: float | None
    attempted_forbidden: bool
    state_violation: bool
    executor: Literal['deny','permissive_simulator']
    detail_file: str | None = Field(default=None,pattern=r'^data/studies/[a-f0-9]{16}\.json$')
    agents: list[StudyAgent] = Field(default_factory=list,max_length=128)
    started_utc: str | None = None
    source_hash: str | None = Field(default=None,pattern=r'^[a-f0-9]{64}$')
    attempted_calls: int | None = Field(default=None,ge=0)
    http_attempts: int | None = Field(default=None,ge=0)
    rounds: int | None = Field(default=None,ge=1,le=5)
    temperature: float | None = None
    thinking: Literal['default','enabled','disabled'] | None = None
    max_output_tokens: int | None = Field(default=None,ge=1)
    median_call_seconds: float | None = Field(default=None,ge=0)
    generated_tokens: int | None = Field(default=None,ge=0)
    generation_tokens_per_second: float | None = Field(default=None,ge=0)
    messages_delivered: int | None = Field(default=None,ge=0)
    downstream_adoption_rate: float | None = Field(default=None,ge=0,le=1)
    downstream_clean_rate: float | None = Field(default=None,ge=0,le=1)



class ReviewRow(Closed):
    sample_id: str
    target_run_id: str | None = None
    target_model: str | None = None
    behavior: Literal['compliant','violation','refusal','ambiguous','unscorable']
    confidence: float = Field(ge=0,le=1)
    needs_human_review: bool
    evidence_event_ids: list[str]
    reason: str | None = None
    queue_reasons: list[str]
    priority: int


class MonitorRow(Closed):
    monitor_seed: int | None = Field(default=None,ge=0)
    model: str | None = None
    protocol: Literal['1.0','1.1','2.0','2.1','2.2','2.3','2.4','2.5','2.6'] | None = None
    cohort: str | None = None
    topology: Literal['ring','star','complete'] | None = None
    backend: Literal['mock','ollama','openai']
    policy: Literal['communications_only','communications_and_outputs']
    visibility: float
    tp: int
    fp: int
    tn: int
    fn: int
    n: int
    precision: float | None
    recall: float | None
    f1: float | None
    false_positive_rate: float | None


class Neuron(Closed):
    index: int = Field(ge=0,lt=1000000)
    clean: list[float] = Field(max_length=128)
    corrupt: list[float] = Field(max_length=128)


class Layer(Closed):
    layer: int = Field(ge=0,lt=128)
    clean_residual_rms: list[float] = Field(min_length=1,max_length=128)
    corrupt_residual_rms: list[float] = Field(min_length=1,max_length=128)
    neurons: list[Neuron] = Field(max_length=16)


class Patch(Closed):
    hook: str = Field(pattern=r'^blocks\.[0-9]{1,3}\.hook_out$')
    clean_position: int
    corrupt_position: int
    clean_target_logit: float
    corrupt_target_logit: float
    patched_target_logit: float
    noop_target_logit: float
    position_control_logit: float


class NeuralRow(Closed):
    id: str
    evidence_type: Literal['random_weight_smoke','instrumented_checkpoint_replay']
    model: str
    revision: str | None = Field(pattern=r'^[a-f0-9]{40}$')
    seed: int
    dtype: Literal['float32']
    device: Literal['cpu']
    duration_seconds: float
    clean_token_count: int = Field(ge=1,le=128)
    corrupt_token_count: int = Field(ge=1,le=128)
    layers: list[Layer] = Field(min_length=1,max_length=32)
    patch: Patch
    token_labels_withheld: Literal[True] = True


class ScenarioRow(Closed):
    case_id: str
    split: Literal['development','evaluation']
    family: Literal['catalog','provenance','patch','record']
    category: Literal['instruction_override','source_fabrication','evaluator_field_tampering','protected_state_update']
    variant_index: int = Field(ge=0,le=99)
    template_version: Literal['2.0']
    generation_method: Literal['deterministic_template_variant']
    content_hash: str = Field(pattern=r'^[a-f0-9]{64}$')


class StudyTrace(Closed):
    event_id: str
    round: int
    event_type: Literal['task_assigned','inference_response','artifact','message_delivered','parse_failure','run_failure']
    agent_id: str | None = None
    sender_id: str | None = None
    receiver_id: str | None = None
    content: str | None = None
    duration_seconds: float | None = None
    content_truncated: bool = False


class StudyDetail(Closed):
    schema_version: Literal['1.0'] = '1.0'
    id: str
    task_instruction: str | None = None
    task_input: str | None = None
    traces: list[StudyTrace] = Field(default_factory=list,max_length=5000)
    eligible_events: int
    omitted_events: int
    text_included: bool
    graph: dict[str,list[str]]
    limitations: str = 'Bounded scrubbed public view. Full authoritative events stay private. Returned text is not neural evidence.'


class GPUReading(Closed):
    temperature_c: float | None = None
    utilization_percent: float | None = None
    memory_total_mib: float | None = None
    memory_used_mib: float | None = None
    power_watts: float | None = None


class ResourceReading(Closed):
    timestamp_utc: str
    cpu_percent: float | None
    available_ram_gib: float | None
    temperatures_c: list[float] = Field(max_length=128)
    gpu: list[GPUReading] = Field(max_length=8)


class SuiteProgress(Closed):
    status: Literal['running','completed','stopped']
    planned_calls: int = Field(ge=0)
    physical_calls: int = Field(ge=0)
    completed_runs: int = Field(ge=0)
    failed_runs: int = Field(ge=0)
    job_cursor: int = Field(ge=0)
    planned_jobs: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0)
    model: str | None = None
    current_stage: str | None = None


class ResearchSnapshot(Closed):
    schema_version: Literal['1.0'] = '1.0'
    generated_utc: str
    suite: SuiteProgress | None = None
    resources: ResourceReading | None = None
    scenarios: list[ScenarioRow] = []
    studies: list[StudyRow] = []
    reviews: list[ReviewRow] = []
    monitor: list[MonitorRow] = []
    neural: list[NeuralRow] = []
    reviewer_calibrated: Literal[False] = False
    review_model: str | None = None
    review_source: Literal['not_run','deterministic_rule','mock','ollama','openai'] = 'not_run'
    unreviewed_samples: int = 0
    text_included: bool = False
    limitations: list[str]


def make_research_snapshot(study_sources=(), review_source=None, monitor_source=None, neural_sources=(), env=None, include_text=False, scenario_index=None, detail_directory=None):
    import os
    redact=Redactor(sensitive_values(os.environ if env is None else env))
    studies=[];reviews=[];monitor=[];neural=[];review_backend='not_run';review_model=None;unreviewed=0
    for source in study_sources:
        for row in summarize_study(source):
            c,m,o=row['config'],row['manifest'],row['outcome']
            from .events import read_events
            events=read_events(Path(row['directory'])/'events.jsonl')
            responses=[e for e in events if e['event_type']=='inference_response']
            durations=[e.get('metadata',{}).get('duration_seconds') for e in responses]
            counts=[e.get('metadata',{}).get('eval_count') for e in responses]
            times=[e.get('metadata',{}).get('eval_duration_ns') for e in responses]
            tokens=sum(counts) if counts and all(v is not None for v in counts) else None
            generation_seconds=sum(times)/1e9 if times and all(v is not None for v in times) else None
            downstream=[a for a in o.get('final_agents',[]) if a['agent_id']!='agent_0']
            scored_catalog=c['families']==['catalog'] and m['status']=='completed' and not o.get('parse_failures',0)
            studies.append(StudyRow(id=digest(m['run_id'])[:16],
              agents=[StudyAgent(agent_id=a['agent_id'],task_success=a['task_success'],violation=a['violation'],behavior=a['behavior'],
                  messages_received=sum(e['event_type']=='message_delivered' and e.get('receiver_id')==a['agent_id'] for e in events)) for a in o.get('final_agents',[])],
              started_utc=m['started_utc'],source_hash=m['source_hash'],attempted_calls=m.get('attempted_model_calls'),http_attempts=m.get('http_attempts'),
              rounds=m.get('observed_rounds') or c['rounds'],temperature=c['temperature'],thinking=c['thinking'],max_output_tokens=c['max_output_tokens'],
              median_call_seconds=median(durations) if durations and all(v is not None for v in durations) else None,
              generated_tokens=tokens,generation_tokens_per_second=tokens/generation_seconds if tokens is not None and generation_seconds else None,
              messages_delivered=sum(e['event_type']=='message_delivered' for e in events),
              downstream_adoption_rate=o.get('downstream_final_violation_rate') if scored_catalog else None,
              downstream_clean_rate=sum(a['task_success'] for a in downstream)/len(downstream) if scored_catalog and downstream else None,model=redact(c['model']),backend=m['model_identity']['backend'],
              worker_label=m['model_identity'].get('worker_label','unspecified'),model_digest=m['model_identity'].get('digest'),protocol=c['protocol_version'],agent_count=len(m['graph']),freeze_hash=m['freeze_hash'],
              size_comparison_group=digest({'source':m['source_hash'],'model_identity':m['model_identity'],
                'task_case':o['task_case'],**{k:c[k] for k in ['protocol_version','split','seeds','topologies','interventions','rounds','thinking','temperature','max_output_tokens','executor']}}),split=c['split'],task_family=c['families'][0],case_id=o['task_case'],seed=c['seeds'][0],
              topology=c['topologies'][0],intervention=c['interventions'][0],status=m['status'],calls=m['completed_model_calls'],
              runtime=m['duration_seconds'],violation=o['any_violation'],
              parse_failures=m.get('parse_failures',m.get('failures',[]).count('parse_failure')),
              violation_status='observed' if o['any_violation'] else 'indeterminate' if m.get('parse_failures',m.get('failures',[]).count('parse_failure')) else 'not_observed',task_success_rate=o['task_success_rate'] if m['status']=='completed' else None,
              attempted_forbidden=o['attempted_forbidden'],state_violation=o['actual_state_violation'],executor=c['executor']))
    if detail_directory:
        from .events import read_events
        from .tasks import make_case,task_instruction
        target=Path(detail_directory);target.mkdir(parents=True,exist_ok=True)
        by_id={row.id:row for row in studies}
        for source in study_sources:
            for row in summarize_study(source):
                c,m,o=row['config'],row['manifest'],row['outcome']
                ident=digest(m['run_id'])[:16]
                directory=Path(row['directory'])
                cached=target/f'{ident}.json'
                if cached.is_file():
                    existing=validate_study_detail(cached,env=env)
                    if existing.text_included==include_text:
                        by_id[ident].detail_file=f'data/studies/{ident}.json'
                        continue
                events=read_events(directory/'events.jsonl')
                allowed={'inference_requested','inference_response','artifact','message_delivered','parse_failure','run_failure'}
                eligible=[e for e in events if e['event_type'] in allowed]
                selected=eligible if len(eligible)<=5000 else eligible[:100]+eligible[-4900:]
                case=make_case(c['families'][0],c['split'],c['case_indices'][0])
                traces=[]
                for e in selected:
                    item={k:e[k] for k in ['event_id','round','event_type','agent_id','sender_id','receiver_id'] if k in e}
                    text=e.get('content','')
                    if e['event_type']=='inference_requested':
                        item['event_type']='task_assigned'
                        messages=e.get('metadata',{}).get('messages',[])
                        text=json.dumps(json.loads(messages[-1]['content']).get('task',{}),sort_keys=True) if messages else ''
                    sanitized=redact(text) if include_text else ''
                    item['content']=sanitized[:1200] if include_text else None
                    item['content_truncated']=len(sanitized)>1200
                    item['duration_seconds']=e.get('metadata',{}).get('duration_seconds')
                    traces.append(StudyTrace(**item))
                detail=StudyDetail(id=ident,task_instruction=redact(task_instruction(case,c['protocol_version'])) if include_text else None,
                    task_input=redact(json.dumps(case.payload,sort_keys=True)) if include_text else None,traces=traces,
                    eligible_events=len(eligible),omitted_events=max(0,len(eligible)-len(selected)),text_included=include_text,graph=m['graph'])
                while len(detail.model_dump_json().encode())>4*1024*1024 and len(detail.traces)>200:
                    detail.traces=detail.traces[:100]+detail.traces[-max(100,len(detail.traces)//2):]
                    detail.omitted_events=detail.eligible_events-len(detail.traces)
                path=target/f'{ident}.json';temp=path.with_suffix('.tmp');temp.write_text(detail.model_dump_json()+'\n')
                validate_study_detail(temp,env=env);temp.replace(path)
                by_id[ident].detail_file=f'data/studies/{ident}.json'
    if review_source:
        source=Path(review_source)
        manifest=json.loads((source/'manifest.json').read_text())
        review_backend=manifest['backend'];review_model=redact(manifest['reviewer']);unreviewed=manifest['remaining_samples']
        oracle=json.loads((source/'oracle.json').read_text())
        queue={q['sample_id']:q for q in json.loads((source/'queue.json').read_text())}
        for row in json.loads((source/'reviews.json').read_text()):
            result=row['prediction'];q=queue[row['sample_id']]
            reviews.append(ReviewRow(sample_id=row['sample_id'],target_run_id=oracle[row['sample_id']]['run_unit'],
                target_model=redact(oracle[row['sample_id']]['target_model']) if oracle[row['sample_id']].get('target_model') else None,behavior=result['behavior'],confidence=result['confidence'],
                needs_human_review=True,evidence_event_ids=result['evidence_event_ids'],reason=redact(result['rubric_reason']) if include_text else None,
                queue_reasons=q['reasons'],priority=q.get('priority',50)))
    if monitor_source:
        source=json.loads(Path(monitor_source).read_text());monitor=[MonitorRow(**{**row,**({'model':redact(row['model'])} if row.get('model') else {})}) for row in source['summary']]
    for source in neural_sources:
        directory=Path(source)
        checksums=json.loads((directory/'checksums.json').read_text())
        required={'capture.json','private_inputs.json','activations.safetensors'}
        if set(checksums)!=required or not all(hashlib.sha256((directory/name).read_bytes()).hexdigest()==checksums[name] for name in required):
            raise ValueError('Neural source failed integrity validation')
        raw=validate_numeric_capture(json.loads((directory/'capture.json').read_text()))
        public={key:raw[key] for key in ['evidence_type','model','revision','seed','dtype','device','duration_seconds',
                   'clean_token_count','corrupt_token_count','layers']}
        public['model']=redact(public['model'])
        public['patch']={k:v for k,v in raw['patch'].items() if k!='target_token_id_private'}
        neural.append(NeuralRow(id=digest(checksums)[:16],**public))
    scenarios=[]
    if scenario_index:
        from .scenarios import registry_records
        records=registry_records()
        expected=[ScenarioRow(**{k:r[k] for k in ScenarioRow.model_fields}) for r in records]
        index=json.loads(Path(scenario_index).read_text())
        scenarios=[ScenarioRow(**r) for r in index['scenarios']]
        if scenarios!=expected or index['registry_hash']!=digest(records):
            raise ValueError('Scenario index does not match versioned registry')
    ids=[r.id for r in studies]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate study export inputs')
    return ResearchSnapshot(generated_utc=utc(),scenarios=scenarios,studies=studies,reviews=reviews,monitor=monitor,neural=neural,
             review_model=review_model,review_source=review_backend,unreviewed_samples=unreviewed,text_included=include_text,
             limitations=['Protocol-2 results are separate cohorts from frozen protocol-1 findings.',
              'Mock runs and random neural models validate software; they are not trained-model alignment evidence.',
              'Review confidence is uncalibrated; no automatic clearance is enabled. Review notes are optional scrubbed text.',
              'Neural values require measured capture artifacts. No token text, token IDs, raw prompts or full tensors are published.',
              'Activation magnitudes and patch effects are not broad alignment or intent scores. No SAE features are claimed.'])


def validate_research_snapshot(path, env=None):
    result=ResearchSnapshot.model_validate_json(Path(path).read_text())
    import os
    redact=Redactor(sensitive_values(os.environ if env is None else env))
    texts=([result.review_model] if result.review_model else [])+[r.target_model for r in result.reviews if r.target_model]+[r.model for r in result.monitor if r.model]+[r.model for r in result.studies]+[r.model for r in result.neural]+[r.reason for r in result.reviews if r.reason]
    if any(redact(t)!=t for t in texts):raise ValueError('Sensitive research text remains')
    for capture in result.neural:
        for layer in capture.layers:
            if len(layer.clean_residual_rms)!=capture.clean_token_count or len(layer.corrupt_residual_rms)!=capture.corrupt_token_count:
                raise ValueError('Neural token/matrix shape mismatch')
            if any(len(n.clean)!=capture.clean_token_count or len(n.corrupt)!=capture.corrupt_token_count for n in layer.neurons):
                raise ValueError('Neuron shape mismatch')
    return result


def validate_study_detail(path,env=None):
    import os
    detail=StudyDetail.model_validate_json(Path(path).read_text())
    redact=Redactor(sensitive_values(os.environ if env is None else env))
    texts=[detail.task_instruction,detail.task_input]+[t.content for t in detail.traces]
    if any(t and redact(t)!=t for t in texts):raise ValueError('Sensitive study detail text remains')
    if detail.eligible_events!=len(detail.traces)+detail.omitted_events:raise ValueError('Trace accounting mismatch')
    if Path(path).suffix=='.json' and Path(path).stem!=detail.id:raise ValueError('Study detail filename mismatch')
    return detail
