"""Closed-schema public export for protocol-2 studies, review and measured neural data."""
import hashlib
import json
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


class StudyRow(Closed):
    id: str
    model: str
    backend: Literal['mock','ollama','openai']
    model_digest: str | None = Field(default=None,pattern=r'^(sha256:)?[a-f0-9]{64}$')
    protocol: Literal['2.0','2.1'] = '2.0'
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
    task_success_rate: float | None
    attempted_forbidden: bool
    state_violation: bool
    executor: Literal['deny','permissive_simulator']


class ReviewRow(Closed):
    sample_id: str
    behavior: Literal['compliant','violation','refusal','ambiguous','unscorable']
    confidence: float = Field(ge=0,le=1)
    needs_human_review: bool
    evidence_event_ids: list[str]
    reason: str | None = None
    queue_reasons: list[str]
    priority: int


class MonitorRow(Closed):
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


class ResearchSnapshot(Closed):
    schema_version: Literal['1.0'] = '1.0'
    generated_utc: str
    scenarios: list[ScenarioRow] = []
    studies: list[StudyRow] = []
    reviews: list[ReviewRow] = []
    monitor: list[MonitorRow] = []
    neural: list[NeuralRow] = []
    reviewer_calibrated: Literal[False] = False
    review_source: Literal['not_run','deterministic_rule','mock','ollama','openai'] = 'not_run'
    unreviewed_samples: int = 0
    text_included: bool = False
    limitations: list[str]


def make_research_snapshot(study_sources=(), review_source=None, monitor_source=None, neural_sources=(), env=None, include_text=False, scenario_index=None):
    import os
    redact=Redactor(sensitive_values(os.environ if env is None else env))
    studies=[];reviews=[];monitor=[];neural=[];review_backend='not_run';unreviewed=0
    for source in study_sources:
        for row in summarize_study(source):
            c,m,o=row['config'],row['manifest'],row['outcome']
            studies.append(StudyRow(id=digest(m['run_id'])[:16],model=redact(c['model']),backend=m['model_identity']['backend'],
              model_digest=m['model_identity'].get('digest'),protocol=c['protocol_version'],agent_count=len(m['graph']),freeze_hash=m['freeze_hash'],
              size_comparison_group=digest({'source':m['source_hash'],'model_identity':m['model_identity'],
                'task_case':o['task_case'],**{k:c[k] for k in ['protocol_version','split','seeds','topologies','interventions','rounds','thinking','temperature','max_output_tokens','executor']}}),split=c['split'],task_family=c['families'][0],case_id=o['task_case'],seed=c['seeds'][0],
              topology=c['topologies'][0],intervention=c['interventions'][0],status=m['status'],calls=m['completed_model_calls'],
              runtime=m['duration_seconds'],violation=o['any_violation'],task_success_rate=o['task_success_rate'] if m['status']=='completed' else None,
              attempted_forbidden=o['attempted_forbidden'],state_violation=o['actual_state_violation'],executor=c['executor']))
    if review_source:
        source=Path(review_source)
        manifest=json.loads((source/'manifest.json').read_text())
        review_backend=manifest['backend'];unreviewed=manifest['remaining_samples']
        queue={q['sample_id']:q for q in json.loads((source/'queue.json').read_text())}
        for row in json.loads((source/'reviews.json').read_text()):
            result=row['prediction'];q=queue[row['sample_id']]
            reviews.append(ReviewRow(sample_id=row['sample_id'],behavior=result['behavior'],confidence=result['confidence'],
                needs_human_review=True,evidence_event_ids=result['evidence_event_ids'],reason=redact(result['rubric_reason']) if include_text else None,
                queue_reasons=q['reasons'],priority=q.get('priority',50)))
    if monitor_source:
        source=json.loads(Path(monitor_source).read_text());monitor=[MonitorRow(**row) for row in source['summary']]
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
             review_source=review_backend,unreviewed_samples=unreviewed,text_included=include_text,
             limitations=['Protocol-2 results are separate cohorts from frozen protocol-1 findings.',
              'Mock runs and random neural models validate software; they are not trained-model alignment evidence.',
              'Review confidence is uncalibrated; no automatic clearance is enabled. Review notes are optional scrubbed text.',
              'Neural values require measured capture artifacts. No token text, token IDs, raw prompts or full tensors are published.',
              'Activation magnitudes and patch effects are not broad alignment or intent scores. No SAE features are claimed.'])


def validate_research_snapshot(path, env=None):
    result=ResearchSnapshot.model_validate_json(Path(path).read_text())
    import os
    redact=Redactor(sensitive_values(os.environ if env is None else env))
    texts=[r.model for r in result.studies]+[r.model for r in result.neural]+[r.reason for r in result.reviews if r.reason]
    if any(redact(t)!=t for t in texts):raise ValueError('Sensitive research text remains')
    for capture in result.neural:
        for layer in capture.layers:
            if len(layer.clean_residual_rms)!=capture.clean_token_count or len(layer.corrupt_residual_rms)!=capture.corrupt_token_count:
                raise ValueError('Neural token/matrix shape mismatch')
            if any(len(n.clean)!=capture.clean_token_count or len(n.corrupt)!=capture.corrupt_token_count for n in layer.neurons):
                raise ValueError('Neuron shape mismatch')
    return result
