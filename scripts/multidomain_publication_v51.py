"""Closed numeric protocol5.1 summaries and bounded loopback-only trace data."""
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import Field, model_validator

from contagion.config import digest
from contagion.events import read_events
from contagion.publication import Redactor, sensitive_values
from contagion.research_publication import Closed
from contagion.storage import verify
from multidomain_docket import RULES, load
from multidomain_live_v51 import PROTOCOL
from multidomain_pilot import parse, score

Domain = Literal['psychology', 'science', 'mathematics', 'humanities', 'defensive_cybersecurity']
_CACHE = {}


class MultidomainRun(Closed):
    protocol: Literal['5.1-multidomain-question-coverage'] = PROTOCOL
    id: str = Field(pattern=r'^[a-f0-9]{16}$')
    task_id: str = Field(pattern=r'^[a-f0-9]{16}$')
    cohort: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    backend: Literal['mock', 'ollama']
    model: str = Field(max_length=160)
    model_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    worker: Literal['primary'] = 'primary'
    domain: Domain
    phase: Literal['integration_precheck', 'evaluation']
    split: Literal['development', 'evaluation']
    arm: Literal['clean', 'marker_override', 'reporting_pressure']
    status: Literal['completed', 'failed', 'budget_exhausted']
    scientific_status: Literal['mock_only', 'recorded_real_inference']
    rounds: int = Field(ge=3, le=20)
    agent_count: Literal[5] = 5
    topology: Literal['ring'] = 'ring'
    calls: int = Field(ge=0, le=100)
    http_attempts: int = Field(ge=0, le=100)
    runtime_seconds: float = Field(ge=0, le=172800)
    retained_failed_attempts: int = Field(ge=0, le=1000)
    final_questions: int | None = Field(default=None, ge=1, le=80)
    final_correct: int | None = Field(default=None, ge=0, le=80)
    final_answer_when_unknown: int | None = Field(default=None, ge=0, le=80)
    final_missing_citations: int | None = Field(default=None, ge=0, le=80)
    final_unsupported_citations: int | None = Field(default=None, ge=0, le=960)
    final_verification_claims: int | None = Field(default=None, ge=0, le=5)
    downstream_final_marker_adoptions: int | None = Field(default=None, ge=0, le=4)
    confidence_brier_mean: float | None = Field(default=None, ge=0, le=1)
    semantic_support: Literal['not_adjudicated'] = 'not_adjudicated'
    deceptive_intent: Literal['not_adjudicated'] = 'not_adjudicated'
    text_included: Literal[False] = False

    @model_validator(mode='after')
    def denominators(self):
        metrics = [self.final_questions, self.final_correct, self.final_answer_when_unknown,
                   self.final_missing_citations, self.final_unsupported_citations,
                   self.final_verification_claims, self.downstream_final_marker_adoptions, self.confidence_brier_mean]
        if self.status != 'completed' and any(v is not None for v in metrics):
            raise ValueError('Incomplete run endpoints are unknown')
        if self.status == 'completed':
            if any(v is None for v in metrics) or self.calls != 5 * self.rounds:
                raise ValueError('Completed run needs full final coverage')
            if max(self.final_correct, self.final_answer_when_unknown, self.final_missing_citations) > self.final_questions:
                raise ValueError('Question denominator mismatch')
        if (self.phase == 'integration_precheck') != (self.split == 'development'):
            raise ValueError('Split/phase mismatch')
        if (self.backend == 'mock') != (self.scientific_status == 'mock_only'):
            raise ValueError('Mock evidence must remain explicit')
        return self


def identifier(path):
    return digest(str(Path(path).resolve()))[:16]


def paths(source):
    """Only the dedicated live layout, never unrelated JSON or raw external files."""
    return [p for p in sorted(Path(source).glob('*/runs/job-*/attempt-*/manifest.json'))
            if json.loads(p.read_text()).get('protocol_version') == PROTOCOL]


def _plan(root):
    path = Path(root) / 'multidomain-live-plan.json'
    plan = json.loads(path.read_text())
    if (plan.get('protocol_version') != PROTOCOL
            or plan.get('plan_hash') != digest({k: v for k, v in plan.items() if k != 'plan_hash'})):
        raise ValueError('Multidisciplinary plan changed')
    manifest, payloads, oracles = load(plan['catalog'])
    if manifest['catalog_hash'] != plan['catalog_hash']:
        raise ValueError('Multidisciplinary catalog changed')
    return plan, payloads, oracles


def _read(root, plan, payloads, oracles):
    root = Path(root)
    if root.is_symlink() or root.parent.is_symlink() or any(p.is_symlink() for p in root.iterdir()):
        raise ValueError('Unsafe multidisciplinary attempt')
    if not verify(root):
        raise ValueError('Multidisciplinary seal failed')
    m = json.loads((root / 'manifest.json').read_text())
    c = json.loads((root / 'config.snapshot.json').read_text())
    index = int(root.parent.name.removeprefix('job-'))
    if index < 0 or index >= len(plan['jobs']):
        raise ValueError('Unexpected task assignment')
    job = plan['jobs'][index]; task = job['task_id']
    if (m['protocol_version'] != PROTOCOL or c['protocol_version'] != PROTOCOL
            or c['job'] != job or m['plan_hash'] != plan['plan_hash'] or c['plan_hash'] != plan['plan_hash']
            or m['source_hash'] != plan['source_hash'] or c['source_hash'] != plan['source_hash']
            or c['payload_hash'] != digest(payloads[task]) or c['oracle_hash'] != digest(oracles[task])
            or c.get('response_schema_hash') != digest(plan['response_schema_by_task'][task])
            or m.get('response_schema_hash') != c.get('response_schema_hash')
            or c.get('output_contract_hash') != plan['output_contract_hash_by_task'][task]
            or m.get('output_contract_hash') != c.get('output_contract_hash')
            or c['model_identity'] != m['model_identity']):
        raise ValueError('Multidisciplinary provenance mismatch')
    identity = m['model_identity']
    if identity['backend'] == 'ollama' and (identity.get('model') != plan['model'] or identity.get('digest') != plan['model_digest']
                                         or identity.get('worker_label') != 'primary'):
        raise ValueError('Pinned multidisciplinary model changed')
    return m, c, job


def _row(root, plan, payloads, oracles, redact, retained_failures):
    root = Path(root)
    names = ('checksum.sha256', 'manifest.json', 'config.snapshot.json', 'outcome.json', 'events.jsonl')
    signature = digest({'path': str(root.resolve()), 'catalog': plan['catalog_hash'], 'plan': plan['plan_hash'],
        'redaction_policy': sorted(redact.values), 'retained_failed_attempts': retained_failures,
        'seal': (root / 'checksum.sha256').read_text(),
        'files': [(name, (root / name).stat().st_size, (root / name).stat().st_mtime_ns) for name in names]})
    if signature in _CACHE:
        return MultidomainRun.model_validate(_CACHE[signature])
    m, c, job = _read(root, plan, payloads, oracles)
    final = {}
    events = read_events(root / 'events.jsonl')
    calls = sum(e['event_type'] == 'inference_response' for e in events)
    attempted = sum(e['event_type'] == 'http_attempt' for e in events)
    if m['completed_model_calls'] != calls or m['http_attempts'] != attempted:
        raise ValueError('Multidisciplinary counters changed')
    metrics = {}
    if m['status'] == 'completed':
        coverage = [(e.get('agent_id'), e['round']) for e in events if e['event_type'] == 'artifact']
        if coverage != [(f'agent_{a}', r) for r in range(job['rounds']) for a in range(5)]:
            raise ValueError('Multidisciplinary artifact coverage incomplete')
        for event in events:
            if event['event_type'] == 'artifact' and event['round'] == job['rounds'] - 1:
                final[event['agent_id']] = score(parse(event['content'], payloads[job['task_id']]),
                                                payloads[job['task_id']], oracles[job['task_id']])
        questions = sum(s['questions'] for s in final.values())
        metrics = {'final_questions': questions, 'final_correct': sum(s['exact_answers_correct'] for s in final.values()),
            'final_answer_when_unknown': sum(s['answer_when_reference_unknown_count'] for s in final.values()),
            'final_missing_citations': sum(s['uncited_answer_count'] for s in final.values()),
            'final_unsupported_citations': sum(s['unsupported_citation_count'] for s in final.values()),
            'final_verification_claims': sum(s['unsupported_verification_claim'] for s in final.values()),
            'downstream_final_marker_adoptions': sum(s['marker_adoption'] for a, s in final.items() if a != 'agent_0'),
            'confidence_brier_mean': sum(s['confidence_brier_sum'] for s in final.values()) / questions}
    identity = m['model_identity']
    row = MultidomainRun(id=identifier(root), task_id=digest(job['task_id'])[:16], cohort=plan['plan_hash'],
        source_hash=plan['source_hash'], backend=identity['backend'], model=redact(identity.get('model') or 'unspecified')[:160],
        model_digest=identity.get('digest'), domain=job['domain'], phase=job['phase'], split=job['split'],
        arm=job['intervention'], status=m['status'], scientific_status='mock_only' if identity['backend'] == 'mock' else 'recorded_real_inference',
        rounds=job['rounds'], calls=calls, http_attempts=attempted, runtime_seconds=m['duration_seconds'],
        retained_failed_attempts=retained_failures, **metrics)
    if len(_CACHE) > 2000:
        _CACHE.clear()
    _CACHE[signature] = row.model_dump()
    return row


def summaries(source, env=None):
    """One latest sealed attempt per job; failures stay counted, incomplete endpoints null."""
    redact = Redactor(sensitive_values(env or {})); rows = []; plans = {}; grouped = {}
    for path in paths(source):
        queue = path.parents[3]
        if queue.is_symlink() or path.parents[2].is_symlink():
            raise ValueError('Unsafe multidisciplinary queue')
        if not (queue / 'multidomain-live-plan.json').is_file():
            continue
        if json.loads((queue/'multidomain-live-plan.json').read_text()).get('protocol_version') != PROTOCOL:
            continue
        if not (path.parent / 'checksum.sha256').is_file():
            continue
        if queue not in plans:
            plans[queue] = _plan(queue)
        m = json.loads(path.read_text())
        if m.get('status') not in {'completed', 'failed', 'budget_exhausted'}:
            raise ValueError('Unexpected multidisciplinary status')
        if m['status'] != 'completed' and not verify(path.parent):
            raise ValueError('Retained multidisciplinary failure seal changed')
        grouped.setdefault(path.parent.parent, []).append((path.parent, m['status']))
    for attempts in grouped.values():
        completed = [p for p, status in attempts if status == 'completed']
        if len(completed) > 1:
            raise ValueError('Duplicate completed multidisciplinary job')
        chosen = completed[0] if completed else sorted(p for p, _ in attempts)[-1]
        plan, payloads, oracles = plans[chosen.parents[2]]
        rows.append(_row(chosen, plan, payloads, oracles, redact, sum(s != 'completed' for _, s in attempts)))
    return sorted(rows, key=lambda r: r.id)


def private_detail(source, ident, env=None):
    """Caller must expose this only on the loopback server; never part of public export."""
    if not re.fullmatch(r'[a-f0-9]{16}', ident):
        raise ValueError('Unknown multidisciplinary run')
    redact = Redactor(sensitive_values(env or {}))
    for path in paths(source):
        root = path.parent
        if identifier(root) != ident:
            continue
        plan, payloads, oracles = _plan(path.parents[3])
        _, _, job = _read(root, plan, payloads, oracles)
        allowed = {'artifact', 'inference_response', 'message_generated', 'message_delivered', 'parse_failure'}
        events = [e for e in read_events(root / 'events.jsonl') if e['event_type'] in allowed]
        traces = []
        for event in events[-200:]:
            text = redact(event.get('content', ''))
            row = {k: event[k] for k in ('event_id', 'round', 'event_type', 'agent_id', 'sender_id', 'receiver_id') if k in event}
            row.update(content=text[:4096], content_truncated=len(text) > 4096)
            traces.append(row)
        return {'schema_version': '1.0', 'id': ident, 'protocol': PROTOCOL, 'text_included': True,
                'task_instruction': RULES, 'task_input': f"{job['domain']} evidence dossier; raw sources and hidden references are withheld from this trace view.",
                'graph': {f'agent_{i}': [f'agent_{(i - 1) % 5}', f'agent_{(i + 1) % 5}'] for i in range(5)},
                'traces': traces, 'eligible_events': len(events), 'omitted_events': max(0, len(events) - len(traces))}
    raise ValueError('Unknown multidisciplinary run')
