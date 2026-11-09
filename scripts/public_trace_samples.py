"""Explicit reviewed public excerpts; source logs, tasks and oracle metadata stay private."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from contagion.config import digest
from contagion.events import read_events, utc
from contagion.publication import Redactor, sensitive_values
from contagion.research_publication import Closed
from contagion.storage import verify, write_json
from run_pilot import ROOT

Protocols = Literal['2.6', '3.8-repository-bounded-output', '4.0-confirmatory',
                    '5.0-multidomain-evidence', '5.1-multidomain-question-coverage', '6.0-model-topology-calibration']


class TraceEvent(Closed):
    event_id: str = Field(pattern=r'^[a-f0-9]{16}$')
    round: int = Field(ge=0, le=30)
    event_type: Literal['artifact', 'message_delivered']
    agent_id: str | None = Field(default=None, pattern=r'^agent_[0-9]{1,3}$')
    sender_id: str | None = Field(default=None, pattern=r'^agent_[0-9]{1,3}$')
    receiver_id: str | None = Field(default=None, pattern=r'^agent_[0-9]{1,3}$')
    content: str = Field(max_length=1200)
    content_truncated: bool


class Sample(Closed):
    schema_version: Literal['public-trace-sample-1.0'] = 'public-trace-sample-1.0'
    id: str = Field(pattern=r'^[a-f0-9]{16}$')
    protocol: Protocols
    source_kind: Literal['study', 'repository', 'followup', 'multidomain', 'diversity']
    backend: Literal['ollama'] = 'ollama'
    model: str = Field(max_length=160)
    status: Literal['completed'] = 'completed'
    source_seal_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    content_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    traces: list[TraceEvent] = Field(min_length=1, max_length=32)
    eligible_events: int = Field(ge=1)
    omitted_events: int = Field(ge=0)
    text_included: Literal[True] = True
    reviewer_kind: Literal['implementation_agent'] = 'implementation_agent'
    human_privacy_review_claimed: Literal[False] = False
    limitations: Literal['Selected bounded redacted model-output excerpts; not full logs, private thinking or neural evidence.'] = 'Selected bounded redacted model-output excerpts; not full logs, private thinking or neural evidence.'

    @model_validator(mode='after')
    def content_binding(self):
        expected = 'study' if self.protocol == '2.6' else 'repository' if self.protocol.startswith('3.') else 'followup' if self.protocol.startswith('4.') else 'multidomain' if self.protocol.startswith('5.') else 'diversity'
        if self.source_kind != expected:
            raise ValueError('Trace source/protocol mismatch')
        if self.content_sha256 != digest(self.model_dump(exclude={'content_sha256'})):
            raise ValueError('Public sample content hash changed')
        if self.eligible_events != len(self.traces) + self.omitted_events:
            raise ValueError('Sample event denominator changed')
        return self


class Entry(Closed):
    id: str = Field(pattern=r'^[a-f0-9]{16}$')
    file: str = Field(pattern=r'^data/trace-samples/[a-f0-9]{16}\.json$')
    protocol: Protocols
    source_kind: Literal['study', 'repository', 'followup', 'multidomain', 'diversity']
    source_seal_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    content_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class Index(Closed):
    schema_version: Literal['public-trace-samples-1.0'] = 'public-trace-samples-1.0'
    generated_utc: str
    samples: list[Entry] = Field(max_length=32)
    raw_logs_included: Literal[False] = False
    request_histories_included: Literal[False] = False
    human_privacy_review_claimed: Literal[False] = False
    release_scope: Literal['explicit_user_opt_in_agent_reviewed_excerpts'] = 'explicit_user_opt_in_agent_reviewed_excerpts'

    @model_validator(mode='after')
    def identities(self):
        if len({r.id for r in self.samples}) != len(self.samples) or any(r.file != f'data/trace-samples/{r.id}.json' for r in self.samples):
            raise ValueError('Duplicate or inconsistent sample IDs')
        return self


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _privacy(path, env):
    from scan_privacy import scan_blob
    if scan_blob(Path(path).read_bytes(), public=True, known=sensitive_values(env or {})):
        raise ValueError('Public sample privacy lint failed')


def validate_sample(path, env=None):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Sample symlink rejected')
    sample = Sample.model_validate_json(path.read_text())
    _privacy(path, env)
    redact = Redactor(sensitive_values(env or {}))
    if redact(sample.model) != sample.model or any(redact(e.content) != e.content for e in sample.traces):
        raise ValueError('Unredacted sample content')
    return sample


def validate_index(path, env=None):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Index symlink rejected')
    data = Index.model_validate_json(path.read_text()); _privacy(path, env)
    for row in data.samples:
        sample = validate_sample(path.parent / 'trace-samples' / Path(row.file).name, env)
        if any(getattr(row, key) != getattr(sample, key) for key in ('id', 'protocol', 'source_kind', 'source_seal_sha256', 'content_sha256')):
            raise ValueError('Index/sample binding changed')
    return data


def _excerpt(text):
    if len(text) <= 1200:
        return text, False
    marker = '\n[...bounded public excerpt; middle omitted...]\n'
    return text[:800] + marker + text[-(1200 - 800 - len(marker)):], True


def candidate(directory, source_kind, env):
    directory = Path(directory)
    if directory.is_symlink() or not verify(directory):
        raise ValueError('Only sealed completed attempts can supply public excerpts')
    m = json.loads((directory / 'manifest.json').read_text())
    c = json.loads((directory / 'config.snapshot.json').read_text())
    identity = m['model_identity']
    if m['status'] != 'completed' or identity['backend'] != 'ollama':
        raise ValueError('Only completed actual local inference selected here')
    protocol = m.get('protocol_version', c.get('protocol_version'))
    if source_kind == 'repository':
        ident = hashlib.sha256(m['run_id'].encode()).hexdigest()[:16]
    elif source_kind == 'study':
        from contagion.research_publication import make_research_snapshot
        ident = make_research_snapshot([directory], env=env).studies[0].id
    else:
        ident = digest(str(directory.resolve()))[:16]
    redact = Redactor(sensitive_values(env)); events = read_events(directory / 'events.jsonl')
    eligible = [e for e in events if e['event_type'] in {'artifact', 'message_delivered'}]
    final_round = max((e['round'] for e in eligible if e['event_type'] == 'artifact'), default=-1)
    delivered = [e for e in eligible if e['event_type'] == 'message_delivered'][:2]
    final = [e for e in eligible if e['event_type'] == 'artifact' and e['round'] == final_round][-5:]
    selected = sorted(delivered + final, key=lambda e: e['sequence_no'])
    traces = []
    for event in selected:
        text, truncated = _excerpt(redact(event.get('content', '')))
        fields = {k: event[k] for k in ('round', 'event_type', 'agent_id', 'sender_id', 'receiver_id') if k in event}
        traces.append(TraceEvent(event_id=digest([ident, event['event_id']])[:16], content=text, content_truncated=truncated, **fields))
    fields = {'id': ident, 'protocol': protocol, 'source_kind': source_kind, 'model': redact(identity.get('model') or 'unspecified')[:160],
              'source_seal_sha256': sha(directory / 'checksum.sha256'), 'traces': traces,
              'eligible_events': len(eligible), 'omitted_events': len(eligible) - len(traces)}
    value = Sample.model_construct(content_sha256='0' * 64, **fields)
    value.content_sha256 = digest(value.model_dump(exclude={'content_sha256'}))
    return Sample.model_validate(value.model_dump())


def prepare(output, selected, env):
    output = Path(output)
    if output.exists() or (ROOT / 'results').resolve() not in output.resolve().parents:
        raise ValueError('Use a fresh private candidate directory under results')
    output.mkdir(parents=True)
    entries = []; sources = {}
    for root, kind in selected:
        sample = candidate(root, kind, env)
        path = output / 'trace-samples' / f'{sample.id}.json'; path.parent.mkdir(exist_ok=True)
        write_json(path, sample.model_dump()); validate_sample(path, env)
        entries.append(Entry(**{k: getattr(sample, k) for k in ('id', 'protocol', 'source_kind', 'source_seal_sha256', 'content_sha256')}, file=f'data/trace-samples/{sample.id}.json'))
        sources[sample.id] = str(Path(root).resolve())
    index = Index(generated_utc=utc(), samples=entries)
    write_json(output / 'trace-samples.json', index.model_dump())
    write_json(output / 'candidate-sources.private.json', sources)
    validate_index(output / 'trace-samples.json', env)
    return index


def export(candidates, review, destination, env):
    candidates = Path(candidates); destination = Path(destination)
    index = validate_index(candidates / 'trace-samples.json', env)
    review = json.loads(Path(review).read_text())
    if (review.get('schema_version') != 'public-trace-review-1.0' or review.get('reviewer_kind') != 'implementation_agent'
            or review.get('human_privacy_review_claimed') is not False):
        raise ValueError('Explicit concrete agent review required; human labels are not privacy approval')
    reviewed = {r['id']: r for r in review['samples']}
    if len(reviewed) != len(review['samples']) or set(reviewed) != {r.id for r in index.samples}:
        raise ValueError('Review must name exactly the selected samples')
    sources = json.loads((candidates / 'candidate-sources.private.json').read_text())
    for row in index.samples:
        approval = reviewed[row.id]
        if (approval.get('approved') is not True or approval.get('content_sha256') != row.content_sha256
                or approval.get('source_seal_sha256') != row.source_seal_sha256
                or not verify(Path(sources[row.id])) or sha(Path(sources[row.id]) / 'checksum.sha256') != row.source_seal_sha256):
            raise ValueError('Reviewed source/content changed')
    destination.mkdir(parents=True, exist_ok=True)
    for row in index.samples:
        target = destination / 'trace-samples' / Path(row.file).name; target.parent.mkdir(exist_ok=True)
        if target.exists():
            if target.read_bytes() != (candidates / 'trace-samples' / target.name).read_bytes():
                raise ValueError('Do not replace a different previously reviewed public sample')
        else:
            with target.open('xb') as stream:
                stream.write((candidates / 'trace-samples' / target.name).read_bytes())
    temporary = destination / 'trace-samples.tmp'
    temporary.write_text(index.model_dump_json(indent=2) + '\n')
    validate_index(temporary, env); temporary.replace(destination / 'trace-samples.json')
    return index


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True); parser.add_argument('--out', type=Path, default=ROOT / 'dashboard/data')
    args = parser.parse_args()
    from security_guard import private_values
    _, env = private_values(ROOT, dict(os.environ))
    result = export(args.candidates, args.review, args.out, env)
    print('Exported', len(result.samples), 'explicitly reviewed bounded public trace samples; raw logs unchanged.')
