"""Closed metadata/numeric protocol6.0 export and bounded private output traces."""
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import Field, model_validator

from contagion.config import digest
from contagion.events import read_events
from contagion.publication import Redactor, sensitive_values
from contagion.research_publication import Closed
from contagion.storage import FILES, verify
from contagion.topology import study_adjacency
from diversity_calibration import PROTOCOL, ROLES, assignments, agent_identities, cohort_identity
from multidomain_docket import load
from multidomain_live_v51 import parse
from multidomain_pilot import score

AgentId = Literal['agent_0', 'agent_1', 'agent_2', 'agent_3', 'agent_4']
ModelGroup = Literal['qwen', 'lfm', 'nemotron']
Role = Literal['identical', 'proposer', 'critic', 'evidence_auditor', 'checker', 'synthesizer']
_CACHE = {}


class AssignedModel(Closed):
    model: str = Field(min_length=1, max_length=160)
    digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    model_group: ModelGroup
    family_label: str = Field(max_length=80)


class AgentEndpoint(Closed):
    questions: int | None = Field(default=None, ge=1, le=16)
    correct: int | None = Field(default=None, ge=0, le=16)
    answer_when_unknown: int | None = Field(default=None, ge=0, le=16)
    missing_citations: int | None = Field(default=None, ge=0, le=16)
    unsupported_citations: int | None = Field(default=None, ge=0, le=192)
    verification_claim: bool | None = None
    marker_adoption: bool | None = None
    confidence_brier_mean: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode='after')
    def denominator(self):
        if self.questions is not None:
            if any(v is not None and v > self.questions for v in (self.correct, self.answer_when_unknown, self.missing_citations)):
                raise ValueError('Per-agent question denominator mismatch')
            if self.unsupported_citations is not None and self.unsupported_citations > self.questions * 12:
                raise ValueError('Per-agent citation denominator mismatch')
        return self


class DiversityRun(Closed):
    protocol: Literal['6.0-model-topology-calibration'] = PROTOCOL
    id: str = Field(pattern=r'^[a-f0-9]{16}$')
    task_id: str = Field(pattern=r'^[a-f0-9]{16}$')
    source_plan_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    response_schema_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    cohort: str = Field(pattern=r'^[a-f0-9]{16}$')
    model_cohort: str = Field(pattern=r'^[a-f0-9]{64}$')
    backend: Literal['mock', 'ollama']
    model: str = Field(min_length=1, max_length=160)
    model_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    worker: Literal['primary'] = 'primary'
    composition: Literal['qwen', 'lfm', 'nemotron', 'heterogeneous']
    rotation: int = Field(ge=0, le=4)
    role_condition: Literal['identical', 'specialized']
    agent_models: dict[AgentId, AssignedModel]
    agent_roles: dict[AgentId, Role]
    graph: dict[AgentId, list[AgentId]]
    model_identity_scope: Literal['controller_assigned_pinned_models'] = 'controller_assigned_pinned_models'
    domain: Literal['psychology', 'science', 'mathematics', 'humanities', 'defensive_cybersecurity']
    phase: Literal['homogeneous_integration', 'heterogeneous_calibration', 'role_calibration']
    split: Literal['development'] = 'development'
    arm: Literal['clean', 'marker_override']
    seed: int = Field(ge=0)
    topology: Literal['ring', 'star', 'complete']
    rounds: Literal[3] = 3
    agent_count: Literal[5] = 5
    status: Literal['completed', 'failed', 'budget_exhausted']
    scientific_status: Literal['mock_only', 'recorded_real_inference']
    calls: int = Field(ge=0, le=15)
    http_attempts: int = Field(ge=0, le=15)
    parse_failures: int = Field(ge=0, le=15)
    runtime_seconds: float = Field(ge=0, le=172800)
    retained_failed_attempts: int = Field(ge=0, le=1000)
    retained_unsealed_attempts: int = Field(ge=0, le=1000)
    final_questions: int | None = Field(default=None, ge=1, le=80)
    final_correct: int | None = Field(default=None, ge=0, le=80)
    final_answer_when_unknown: int | None = Field(default=None, ge=0, le=80)
    final_missing_citations: int | None = Field(default=None, ge=0, le=80)
    final_unsupported_citations: int | None = Field(default=None, ge=0, le=960)
    final_verification_claims: int | None = Field(default=None, ge=0, le=5)
    downstream_final_marker_adoptions: int | None = Field(default=None, ge=0, le=4)
    confidence_brier_mean: float | None = Field(default=None, ge=0, le=1)
    agents: dict[AgentId, AgentEndpoint]
    memory_policy: Literal['original_task_plus_last_two_own_rounds'] = 'original_task_plus_last_two_own_rounds'
    max_output_tokens: Literal[2048] = 2048
    semantic_support: Literal['not_adjudicated'] = 'not_adjudicated'
    deceptive_intent: Literal['not_adjudicated'] = 'not_adjudicated'
    model_superiority: Literal['not_established'] = 'not_established'
    heldout_evidence: Literal[False] = False
    text_included: Literal[False] = False

    @model_validator(mode='after')
    def invariants(self):
        expected = {f'agent_{i}' for i in range(5)}
        if set(self.agent_models) != expected or set(self.agent_roles) != expected or set(self.agents) != expected:
            raise ValueError('Five exact agent assignments required')
        if self.graph != study_adjacency(self.topology, 5):
            raise ValueError('Published graph/topology mismatch')
        if self.role_condition == 'identical' and set(self.agent_roles.values()) != {'identical'}:
            raise ValueError('Identical-role cohort mismatch')
        if self.role_condition == 'specialized' and set(self.agent_roles.values()) != set(ROLES):
            raise ValueError('Specialized-role cohort mismatch')
        groups = [m.model_group for m in self.agent_models.values()]
        if self.composition == 'heterogeneous':
            if {k: groups.count(k) for k in ('qwen', 'lfm', 'nemotron')} != {'qwen': 2, 'lfm': 2, 'nemotron': 1}:
                raise ValueError('Heterogeneous composition mismatch')
        elif set(groups) != {self.composition}:
            raise ValueError('Homogeneous composition mismatch')
        expected_phase = 'homogeneous_integration' if self.composition != 'heterogeneous' else 'role_calibration' if self.role_condition == 'specialized' else 'heterogeneous_calibration'
        if self.phase != expected_phase:
            raise ValueError('Calibration phase/composition mismatch')
        metrics = [self.final_questions, self.final_correct, self.final_answer_when_unknown,
            self.final_missing_citations, self.final_unsupported_citations, self.final_verification_claims,
            self.downstream_final_marker_adoptions, self.confidence_brier_mean]
        if self.status != 'completed':
            if any(v is not None for v in metrics) or any(any(v is not None for v in r.model_dump().values()) for r in self.agents.values()):
                raise ValueError('Incomplete endpoints remain unknown')
        else:
            if any(v is None for v in metrics) or self.calls != 15 or self.parse_failures:
                raise ValueError('Completed run needs full valid coverage')
            if self.backend == 'ollama' and self.http_attempts != 15:
                raise ValueError('Completed live call denominator mismatch')
            if any(any(v is None for v in r.model_dump().values()) for r in self.agents.values()):
                raise ValueError('Completed per-agent endpoint missing')
            if (sum(r.questions for r in self.agents.values()) != self.final_questions
                    or sum(r.correct for r in self.agents.values()) != self.final_correct
                    or max(self.final_correct, self.final_answer_when_unknown, self.final_missing_citations) > self.final_questions):
                raise ValueError('Endpoint denominator mismatch')
        if (self.backend == 'mock') != (self.scientific_status == 'mock_only'):
            raise ValueError('Mock status must be explicit')
        return self


Row = DiversityRun


def identifier(root):
    return digest(str(Path(root).resolve()))[:16]


def paths(source):
    result = []
    for path in sorted(Path(source).glob('*/diversity-plan.json')):
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError('Unsafe diversity plan')
        if json.loads(path.read_text()).get('protocol_version') == PROTOCOL:
            result.extend(sorted(path.parent.glob('runs/job-*/attempt-*/manifest.json')))
    return result


def _plan(root):
    root = Path(root); plan = json.loads((root / 'diversity-plan.json').read_text())
    if plan.get('protocol_version') != PROTOCOL or plan.get('plan_hash') != digest({k: v for k, v in plan.items() if k != 'plan_hash'}):
        raise ValueError('Diversity plan changed')
    manifest, payloads, oracles = load(plan['catalog'])
    if (manifest['catalog_hash'] != plan['catalog_hash'] or plan['task_id'] not in payloads
            or digest(payloads[plan['task_id']]) != plan['task_payload_hash']):
        raise ValueError('Diversity task catalog changed')
    return plan, payloads, oracles


def _read(root, plan, payloads, oracles):
    root = Path(root)
    if (root.is_symlink() or root.parent.is_symlink() or root.parents[1].is_symlink()
            or any(p.is_symlink() for p in root.iterdir()) or not verify(root)):
        raise ValueError('Diversity seal failed or unsafe attempt')
    index = int(root.parent.name.removeprefix('job-'))
    if not 0 <= index < len(plan['jobs']) or root.parent.name != f'job-{index:03}':
        raise ValueError('Unexpected diversity job index')
    job = plan['jobs'][index]; task = job['task_id']
    m = json.loads((root / 'manifest.json').read_text()); c = json.loads((root / 'config.snapshot.json').read_text())
    identity = m['model_identity']; backend = identity['backend']; version = identity.get('backend_version')
    expected_models, expected_roles = assignments(job['composition'], job['rotation'], job['role_condition'] == 'specialized')
    expected = agent_identities(plan, job, backend, version)
    if (m.get('protocol_version') != PROTOCOL or c.get('protocol_version') != PROTOCOL
            or m.get('plan_hash') != plan['plan_hash'] or c.get('plan_hash') != plan['plan_hash'] or c.get('job') != job
            or m.get('source_hash') != plan['source_hash'] or c.get('source_hash') != plan['source_hash']
            or c.get('payload_hash') != digest(payloads[task]) or c.get('oracle_hash') != digest(oracles[task])
            or c.get('response_schema_hash') != digest(plan['response_schema']) or m.get('response_schema_hash') != c['response_schema_hash']
            or identity != c.get('model_identity') or identity != cohort_identity(plan, job, backend, version)
            or c.get('agent_models') != expected or m.get('agent_models') != expected
            or job['agent_models'] != expected_models or job['agent_roles'] != expected_roles
            or c.get('agent_roles') != expected_roles or m.get('agent_roles') != expected_roles
            or m.get('graph') != study_adjacency(job['topology'], 5) or job.get('split') != 'development'
            or plan.get('max_output_tokens') != 2048 or c.get('max_output_tokens') != 2048 or m.get('max_output_tokens') != 2048
            or c.get('agent_tools') or c.get('memory_policy') != 'original_task_plus_last_two_own_rounds'):
        raise ValueError('Diversity provenance, models, roles or graph mismatch')
    events = read_events(root / 'events.jsonl')
    calls = sum(e['event_type'] == 'inference_response' for e in events)
    attempted = sum(e['event_type'] == 'http_attempt' for e in events)
    if (m.get('completed_model_calls') != calls or m.get('http_attempts') != attempted
            or m.get('parse_failures') != sum(e['event_type'] == 'parse_failure' for e in events)):
        raise ValueError('Diversity counter mismatch')
    for event in events:
        if event['event_type'] in {'inference_requested', 'inference_response', 'http_attempt'}:
            agent = event.get('agent_id')
            if agent not in expected or event.get('metadata', {}).get('assigned_model') != expected[agent]:
                raise ValueError('Per-call diversity model changed')
            if event['event_type'] == 'inference_requested' and event['metadata'].get('assigned_role') != expected_roles[agent]:
                raise ValueError('Per-call diversity role changed')
            if event['event_type'] == 'inference_response' and backend == 'ollama' and m['status'] == 'completed' and event['metadata'].get('model') != expected[agent]['model']:
                raise ValueError('Observed response model mismatch')
        if event['event_type'] == 'message_delivered':
            if (event.get('receiver_id') not in m['graph'].get(event.get('sender_id'), [])
                    or event['round'] <= 0 or event.get('metadata', {}).get('source_round') != event['round'] - 1):
                raise ValueError('Diversity message routing mismatch')
    return m, c, job, events


def _models(assigned, redact):
    return {agent: AssignedModel(model=redact(row['model'])[:160], digest=row['digest'],
        model_group=row['model_group'], family_label=redact(row['family_label'])[:80]) for agent, row in assigned.items()}


def _row(root, plan, payloads, oracles, redact, failed, unsealed):
    signature = digest({'path': str(Path(root).resolve()), 'plan': plan['plan_hash'], 'policy': sorted(redact.values),
        'failures': failed, 'unsealed': unsealed, 'seal': (root / 'checksum.sha256').read_text(),
        'files': [(n, (root / n).stat().st_size, (root / n).stat().st_mtime_ns) for n in FILES]})
    if signature in _CACHE:
        return DiversityRun.model_validate(_CACHE[signature])
    m, c, job, events = _read(root, plan, payloads, oracles)
    metrics = {}; final = {}; agents = {f'agent_{i}': AgentEndpoint() for i in range(5)}
    if m['status'] == 'completed':
        coverage = [(e.get('agent_id'), e['round']) for e in events if e['event_type'] == 'artifact']
        if coverage != [(f'agent_{a}', r) for r in range(3) for a in range(5)]:
            raise ValueError('Diversity final artifact coverage failed')
        for e in events:
            if e['event_type'] == 'artifact' and e['round'] == 2:
                final[e['agent_id']] = score(parse(e['content'], payloads[job['task_id']]),
                                           payloads[job['task_id']], oracles[job['task_id']])
        for agent, values in final.items():
            agents[agent] = AgentEndpoint(questions=values['questions'], correct=values['exact_answers_correct'],
                answer_when_unknown=values['answer_when_reference_unknown_count'], missing_citations=values['uncited_answer_count'],
                unsupported_citations=values['unsupported_citation_count'], verification_claim=values['unsupported_verification_claim'],
                marker_adoption=values['marker_adoption'], confidence_brier_mean=values['confidence_brier_sum'] / values['questions'])
        questions = sum(s['questions'] for s in final.values())
        metrics = {'final_questions': questions, 'final_correct': sum(s['exact_answers_correct'] for s in final.values()),
            'final_answer_when_unknown': sum(s['answer_when_reference_unknown_count'] for s in final.values()),
            'final_missing_citations': sum(s['uncited_answer_count'] for s in final.values()),
            'final_unsupported_citations': sum(s['unsupported_citation_count'] for s in final.values()),
            'final_verification_claims': sum(s['unsupported_verification_claim'] for s in final.values()),
            'downstream_final_marker_adoptions': sum(s['marker_adoption'] for a, s in final.items() if a != 'agent_0'),
            'confidence_brier_mean': sum(s['confidence_brier_sum'] for s in final.values()) / questions}
    identity = m['model_identity']
    row = DiversityRun(id=identifier(root), task_id=digest(job['task_id'])[:16], source_plan_hash=plan['plan_hash'],
        source_hash=plan['source_hash'], response_schema_hash=c['response_schema_hash'], cohort=job['cohort'],
        model_cohort=digest({'agent_models': c['agent_models'], 'agent_roles': c['agent_roles'], 'cohort': job['cohort']}),
        backend=identity['backend'], model=redact(identity['model'])[:160], model_digest=identity.get('digest'),
        composition=job['composition'], rotation=job['rotation'], role_condition=job['role_condition'],
        agent_models=_models(c['agent_models'], redact), agent_roles=c['agent_roles'], graph=m['graph'],
        domain=job['domain'], phase=job['phase'], arm=job['intervention'], seed=job['seed'], topology=job['topology'],
        status=m['status'], scientific_status='mock_only' if identity['backend'] == 'mock' else 'recorded_real_inference',
        calls=m['completed_model_calls'], http_attempts=m['http_attempts'], parse_failures=m['parse_failures'],
        runtime_seconds=m['duration_seconds'], retained_failed_attempts=failed, retained_unsealed_attempts=unsealed,
        agents=agents, **metrics)
    if len(_CACHE) > 4096:
        _CACHE.clear()
    _CACHE[signature] = row.model_dump(); return row


def summaries(source, env=None):
    redact = Redactor(sensitive_values(env or {})); rows = []; plans = {}; grouped = {}
    for manifest in paths(source):
        root = manifest.parent; queue = manifest.parents[3]
        if not (root / 'checksum.sha256').is_file():
            continue
        if queue not in plans:
            plans[queue] = _plan(queue)
        plan, payloads, oracles = plans[queue]
        m, _, _, _ = _read(root, plan, payloads, oracles)
        grouped.setdefault(root.parent, []).append((root, m['status']))
    for folder, attempts in grouped.items():
        completed = [p for p, status in attempts if status == 'completed']
        if len(completed) > 1:
            raise ValueError('Duplicate completed diversity assignment')
        chosen = completed[0] if completed else sorted(p for p, _ in attempts)[-1]
        plan, payloads, oracles = plans[chosen.parents[2]]
        unsealed = sum(not (p / 'checksum.sha256').is_file() for p in folder.glob('attempt-*') if p.is_dir())
        rows.append(_row(chosen, plan, payloads, oracles, redact, sum(s != 'completed' for _, s in attempts), unsealed))
    return sorted(rows, key=lambda r: r.id)


def private_detail(source, ident, env=None):
    if not re.fullmatch(r'[a-f0-9]{16}', ident):
        raise ValueError('Unknown diversity run')
    redact = Redactor(sensitive_values(env or {}))
    for manifest in paths(source):
        root = manifest.parent
        if identifier(root) != ident:
            continue
        plan, payloads, oracles = _plan(manifest.parents[3])
        m, c, job, events = _read(root, plan, payloads, oracles)
        eligible = [e for e in events if e['event_type'] in {'artifact', 'inference_response', 'message_generated', 'message_delivered', 'parse_failure'}]
        models = _models(c['agent_models'], redact); traces = []
        for event in eligible[-200:]:
            row = {k: event[k] for k in ('event_id', 'round', 'event_type', 'agent_id', 'sender_id', 'receiver_id') if k in event}
            agent = event.get('agent_id') or event.get('sender_id')
            if agent in models:
                row.update(assigned_model=models[agent].model_dump(), assigned_role=c['agent_roles'][agent])
            text = redact(event.get('content', ''))
            row.update(content=text[:4096], content_truncated=len(text) > 4096); traces.append(row)
        return {'schema_version': '1.0', 'id': ident, 'protocol': PROTOCOL, 'text_included': True,
            'task_input': 'Development evidence task; original sources, references and request histories are withheld.',
            'composition': job['composition'], 'rotation': job['rotation'], 'role_condition': job['role_condition'],
            'graph': m['graph'], 'topology': job['topology'],
            'agent_models': {a: v.model_dump() for a, v in models.items()}, 'agent_roles': c['agent_roles'],
            'traces': traces, 'eligible_events': len(eligible), 'omitted_events': max(0, len(eligible) - len(traces))}
    raise ValueError('Unknown diversity run')
