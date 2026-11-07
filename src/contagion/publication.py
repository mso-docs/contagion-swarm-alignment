"""Allowlisted, redacted public snapshots; private oracle logs never enter the site."""
import hashlib
import ipaddress
import json
import os
from datetime import datetime
from pathlib import Path
import re
from statistics import median
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from .config import RunConfig
from .events import read_events, utc
from .scoring import score
from .storage import verify
from .topology import adjacency

AgentID = Literal['agent_0', 'agent_1', 'agent_2', 'agent_3', 'agent_4']


class PublicModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class PublicAgent(PublicModel):
    agent_id: AgentID
    exposed: bool
    adopted_instruction: bool
    legitimate_task_success: bool
    quoted_only: bool
    stated_agreement: bool
    first_adoption_round: int | None
    messages_received: int
    distance_from_source: int
    reason_code: str


class PublicEvent(PublicModel):
    event_id: str
    round: int
    event_type: Literal['inference_response', 'artifact', 'message_generated', 'message_delivered',
                        'intervention_applied', 'parse_failure', 'inference_failure', 'http_failure', 'run_failure']
    agent_id: AgentID | None = None
    sender_id: AgentID | None = None
    receiver_id: AgentID | None = None
    content: str | None = None
    thinking: str | None = None
    duration_seconds: float | None = Field(default=None, ge=0)


class PublicRound(PublicModel):
    round: int
    adoption_rate: float = Field(ge=0, le=1)
    agents: list[PublicAgent]


class PublicRun(PublicModel):
    id: str = Field(pattern=r"^[0-9a-f]{16}$")
    cohort: str = Field(pattern=r"^[0-9a-f]{12}$")
    model: str
    model_digest: str | None
    backend: Literal['mock', 'ollama', 'openai']
    protocol_version: str
    protocol_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    topology: Literal['ring', 'star', 'complete']
    intervention: Literal['none', 'benign_override']
    initial_agent_id: AgentID
    seed: int
    rounds: int
    temperature: float
    max_output_tokens: int
    thinking: str
    started_utc: str
    status: Literal['completed', 'failed', 'budget_exhausted']
    duration_seconds: float = Field(ge=0)
    completed_calls: int = Field(ge=0)
    attempted_calls: int = Field(ge=0)
    http_attempts: int = Field(ge=0)
    parse_failures: int = Field(ge=0)
    median_call_seconds: float | None
    generated_tokens: int | None
    generation_tokens_per_second: float | None
    downstream_adoption_rate: float | None
    downstream_clean_rate: float | None
    legitimate_task_success_rate: float | None
    first_downstream_adoption: int | None
    maximum_propagation_distance: int | None
    messages_delivered: int
    graph: dict[AgentID, list[AgentID]]
    agents: list[PublicAgent]
    timeline: list[PublicRound]
    traces: list[PublicEvent]


class PublicSnapshot(PublicModel):
    schema_version: Literal['1.0'] = '1.0'
    generated_utc: str
    traces_included: bool
    thinking_included: bool
    redaction_replacements: int
    skipped_unsealed: int
    limitations: list[str]
    runs: list[PublicRun]


class Redactor:
    """Defense in depth, not a proof that arbitrary free text is anonymous."""
    def __init__(self, values=()):
        self.values = sorted({str(v) for v in values if v and len(str(v)) >= 3}, key=len, reverse=True)
        self.count = 0

    def __call__(self, value):
        text = str(value)
        def replacement(match):
            self.count += 1
            return '[REDACTED]'
        # Full PEM blocks before line-based patterns.
        text = re.sub(r'-----BEGIN [^-\n]*(?:KEY|CERTIFICATE)-----[\s\S]*?-----END [^-\n]+-----', replacement, text)
        for secret in self.values:
            text = re.sub(re.escape(secret), replacement, text, flags=re.I)
        patterns = [
            r'(?im)\b(?:authorization|api[_ -]?key|access[_ -]?token|password|secret|cookie|set-cookie)\b["\s]*[:=][^\n,}]*',
            r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+',
            r'\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{10,}|github_pat_[A-Za-z0-9_]{10,}|AKIA[A-Z0-9]{16})\b',
            r'(?i)\b(?:https?|wss?|ssh|ftp)://[^\s<>"\']+',
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
            r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?(?![\w.])',
            r'(?i)\b(?:[a-z0-9-]+\.)+(?:com|org|net|io|ai|dev|local|internal|lan|ts\.net)\b',
            r'(?i)\b[a-z0-9_-]+@(?:[a-z0-9_-]+)(?::[^\s]*)?',
            r'(?i)(?:[A-Z]:\\[^\n"<>]+|/(?:Users|home|root|private|tmp|etc|var|mnt|opt|workspace)/[^\s"<>]*)',
            r'(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)',
            r'(?<!\d)(?:\+?\d[\d ().-]{8,}\d)(?!\d)',
            r'\b[A-Za-z0-9_+/=-]{40,}\b',
        ]
        for pattern in patterns:
            text = re.sub(pattern, replacement, text)
        # IPv6 candidates are validated to avoid treating ordinary prose as addresses.
        def ipv6(match):
            candidate = match.group(0)
            try:
                ipaddress.IPv6Address(candidate.strip('[]'))
            except ValueError:
                return candidate
            return replacement(match)
        text = re.sub(r'(?<![\w:])\[?[0-9a-fA-F]*:[0-9a-fA-F:]+(?:%[\w]+)?\]?(?![\w:])', ipv6, text)
        return text


def sensitive_values(env):
    values = []
    for key, value in env.items():
        if value and (re.search(r'(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH)', key, re.I)
                      or key in {'USER', 'LOGNAME', 'HOME', 'HOSTNAME', 'CONTAGION_BASE_URL'}):
            values.append(value)
    endpoint = env.get('CONTAGION_BASE_URL', '')
    if endpoint:
        parsed = urlsplit(endpoint)
        values.extend([parsed.hostname, parsed.username, parsed.password])
    values.append(str(Path.cwd()))
    return values


def safe_date(value):
    return datetime.fromisoformat(value).isoformat()


def public_agents(outcome):
    return [PublicAgent(**{k: v for k, v in a.items() if k != 'run_id'}) for a in outcome['agents']]


def build_snapshot(sources, include_traces=False, include_thinking=False, env=None, extra_secrets=()):
    if include_thinking and not include_traces:
        raise ValueError('Thinking export requires --include-traces')
    redact = Redactor([*sensitive_values(os.environ if env is None else env), *extra_secrets])
    paths = set()
    skipped = 0
    for source in sources:
        source = Path(source)
        if not source.is_dir():
            raise ValueError('A source directory does not exist')
        for path in source.rglob('manifest.json'):
            # Exclude derived and unrelated manifests by requiring a raw event file.
            if (path.parent / 'events.jsonl').is_file():
                paths.add(path.parent.resolve())
        skipped += sum(not (p.parent / 'manifest.json').exists() for p in source.rglob('events.jsonl'))
    runs = []
    seen = set()
    for directory in sorted(paths):
        if not verify(directory):
            raise ValueError('A source run failed checksum validation; public export aborted')
        manifest = json.loads((directory / 'manifest.json').read_text())
        config = RunConfig(**json.loads((directory / 'config.snapshot.json').read_text()))
        events = read_events(directory / 'events.jsonl')
        graph = adjacency(config.topology)
        outcome = score(events, config, graph, directory.name)
        identity = manifest['model_identity']
        cohort = hashlib.sha256(json.dumps({
            'backend': identity['backend'], 'model': config.model, 'digest': identity.get('digest'),
            'protocol': manifest['protocol_hash'], 'source': manifest['source_hash'],
            'temperature': config.temperature, 'tokens': config.max_output_tokens,
            'thinking': getattr(config, 'thinking', 'default'), 'rounds': config.rounds,
            'source_agent': config.initial_agent_id, 'injection_round': config.injection_round,
            'call_budget': config.max_model_calls, 'wall_budget': config.max_wall_seconds,
        }, sort_keys=True).encode()).hexdigest()[:12]
        fingerprint = hashlib.sha256((directory / 'events.jsonl').read_bytes()).hexdigest()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        completed = manifest['status'] == 'completed'
        responses = [e for e in events if e['event_type'] == 'inference_response']
        durations = [e['metadata']['duration_seconds'] for e in responses if e.get('metadata', {}).get('duration_seconds') is not None]
        counts = [e.get('metadata', {}).get('eval_count') for e in responses]
        tokens = sum(counts) if counts and all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in counts) else None
        server_durations = [e.get('metadata', {}).get('eval_duration_ns') for e in responses]
        generation_seconds = sum(server_durations) / 1e9 if server_durations and all(isinstance(n, (float, int)) and n > 0 for n in server_durations) else None
        traces = []
        if include_traces:
            allowed = PublicEvent.model_fields['event_type'].annotation.__args__
            for e in events:
                if e['event_type'] not in allowed:
                    continue
                fields = {k: e[k] for k in ['round', 'event_type', 'agent_id', 'sender_id', 'receiver_id'] if k in e}
                fields['event_id'] = f"event-{e['sequence_no']}"
                if 'content' in e:
                    fields['content'] = redact(e['content'])
                if e['event_type'] == 'inference_response':
                    fields['duration_seconds'] = e.get('metadata', {}).get('duration_seconds')
                    if include_thinking and e.get('metadata', {}).get('thinking'):
                        fields['thinking'] = redact(e['metadata']['thinking'])
                traces.append(PublicEvent(**fields))
        timeline = []
        for round_no in range(config.rounds):
            if not any(e['event_type'] == 'artifact' and e['round'] == round_no for e in events):
                continue
            partial = score([e for e in events if e['round'] <= round_no], config, graph, directory.name)
            timeline.append(PublicRound(round=round_no, adoption_rate=partial['downstream_adoption_rate'], agents=public_agents(partial)))
        downstream = [a for a in outcome['agents'] if a['agent_id'] != config.initial_agent_id]
        model_digest = identity.get("digest")
        if model_digest and not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", model_digest):
            model_digest = redact(model_digest)
        # No unvalidated metadata, configs, environment dictionaries or private histories are copied.
        runs.append(PublicRun(
            id=hashlib.sha256((directory.name + fingerprint).encode()).hexdigest()[:16], cohort=cohort,
            model=redact(config.model), model_digest=model_digest,
            backend=identity['backend'], protocol_version=config.protocol_version,
            protocol_hash=manifest['protocol_hash'], source_hash=manifest['source_hash'],
            topology=config.topology, intervention=config.intervention, initial_agent_id=config.initial_agent_id,
            seed=config.seed, rounds=config.rounds, temperature=config.temperature,
            max_output_tokens=config.max_output_tokens, thinking=getattr(config, 'thinking', 'default'),
            started_utc=safe_date(manifest['started_utc']), status=manifest['status'],
            duration_seconds=manifest['duration_seconds'], completed_calls=manifest['completed_model_calls'],
            attempted_calls=manifest['attempted_model_calls'], http_attempts=manifest.get('http_attempts', 0),
            parse_failures=sum(e['event_type'] == 'parse_failure' for e in events),
            median_call_seconds=median(durations) if durations else None,
            generated_tokens=tokens, generation_tokens_per_second=tokens / generation_seconds if tokens is not None and generation_seconds else None,
            downstream_adoption_rate=outcome['downstream_adoption_rate'] if completed else None,
            downstream_clean_rate=sum(a['legitimate_task_success'] for a in downstream) / len(downstream) if completed else None,
            legitimate_task_success_rate=outcome['legitimate_task_success_rate'] if completed else None,
            first_downstream_adoption=outcome['rounds_to_first_downstream_adoption'] if completed else None,
            maximum_propagation_distance=outcome['maximum_propagation_distance'] if completed else None,
            messages_delivered=outcome['messages_delivered'], graph=graph,
            agents=public_agents(outcome), timeline=timeline, traces=traces,
        ))
    if not runs:
        raise ValueError('No sealed experiment runs found; public export aborted')
    completed_keys = [(r.cohort, r.topology, r.intervention, r.seed) for r in runs if r.status == 'completed']
    if len(completed_keys) != len(set(completed_keys)):
        raise ValueError('Duplicate completed run conditions; select one source per experiment cohort')
    return PublicSnapshot(
        generated_utc=utc(), traces_included=include_traces, thinking_included=include_thinking,
        redaction_replacements=redact.count, skipped_unsealed=skipped, runs=runs,
        limitations=[
            'Behavioral RQ1 evidence only; no general alignment or mechanistic interpretability score.',
            'Mock runs are scripted software validation and must be separated from live results.',
            'Rates use completed runs only; failed attempts remain visible and are not independent trials.',
            'Agents are nested within runs; seeds are paired; topology changes message exposure.',
            'Redaction is heuristic. Review free text before public publication; unknown PII can be missed.',
            'Public snapshots exclude private request histories, endpoints, environment and arbitrary metadata.',
            'Thinking is generated text, not a faithful account of internal computation or neuron activations.',
        ],
    )


def export_snapshot(sources, output, **kwargs):
    output = Path(output)
    snapshot = build_snapshot(sources, **kwargs)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(snapshot.model_dump_json(indent=2) + '\n')
    temporary.replace(output)
    return snapshot


def validate_snapshot(path, env=None):
    snapshot = PublicSnapshot.model_validate_json(Path(path).read_text())
    ids = [r.id for r in snapshot.runs]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate public run identifiers')
    redact = Redactor(sensitive_values(os.environ if env is None else env))
    texts = list(snapshot.limitations)
    for run in snapshot.runs:
        safe_date(run.started_utc)
        texts.append(run.model)
        if run.model_digest and not re.fullmatch(r'(?:sha256:)?[0-9a-f]{64}', run.model_digest):
            texts.append(run.model_digest)
        if not snapshot.traces_included and run.traces:
            raise ValueError('Snapshot trace policy does not match contents')
        for event in run.traces:
            if not re.fullmatch(r'event-\d+', event.event_id):
                raise ValueError('Unexpected public event identifier')
            if event.thinking and not snapshot.thinking_included:
                raise ValueError('Snapshot reasoning policy does not match contents')
            texts.extend(t for t in [event.content, event.thinking] if t)
    if any(redact(text) != text for text in texts):
        raise ValueError('Potential sensitive text remains in public snapshot')
    return snapshot
