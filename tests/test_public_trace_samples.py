import importlib
import json
from pathlib import Path

import pytest

from contagion.events import EventRecorder
from contagion.storage import seal, write_json


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    module = importlib.import_module('public_trace_samples')
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    root = tmp_path / 'results/raw'; root.mkdir(parents=True)
    log = EventRecorder(root / 'events.jsonl', 'fixture-run')
    log.emit('inference_requested', 0, metadata={'oracle': 'NEVER_EXPORT_ORACLE', 'messages': [{'content': 'NEVER_EXPORT_REQUEST'}]})
    for i in range(5):
        log.emit('artifact', 1, agent_id=f'agent_{i}', content='test-canary-value person@example.org ' + 'x' * 2000,
                 metadata={'oracle': 'NEVER_EXPORT_ORACLE', 'private_server': 'NEVER_EXPORT_TELEMETRY'})
    log.close()
    write_json(root / 'manifest.json', {'run_id': 'fixture-run', 'protocol_version': '3.8-repository-bounded-output',
        'status': 'completed', 'model_identity': {'backend': 'ollama', 'model': 'fixture-model'}})
    write_json(root / 'config.snapshot.json', {'protocol_version': '3.8-repository-bounded-output'})
    write_json(root / 'outcome.json', {}); seal(root)
    env = {'CONTAGION_API_KEY': 'test-canary-value'}
    output = tmp_path / 'results/candidate'
    index = module.prepare(output, [(root, 'repository')], env)
    approval = {'schema_version': 'public-trace-review-1.0', 'reviewer_kind': 'implementation_agent',
                'human_privacy_review_claimed': False, 'samples': [{**r.model_dump(exclude={'file', 'protocol', 'source_kind'}), 'approved': True} for r in index.samples]}
    review = tmp_path / 'review.private.json'; review.write_text(json.dumps(approval))
    return module, root, output, review, env


def test_reviewed_export_is_closed_redacted_and_bound(sample, tmp_path):
    module, _, candidate, review, env = sample
    destination = tmp_path / 'public/data'
    index = module.export(candidate, review, destination, env)
    assert len(index.samples) == 1
    detail = module.validate_sample(destination / 'trace-samples' / Path(index.samples[0].file).name, env)
    text = detail.model_dump_json()
    assert 'test-canary-value' not in text and 'person@example.org' not in text
    assert all(forbidden not in text for forbidden in ['NEVER_EXPORT_REQUEST', 'NEVER_EXPORT_ORACLE', 'NEVER_EXPORT_TELEMETRY', 'metadata'])
    assert all(len(e.content) <= 1200 for e in detail.traces)
    # Redaction can shorten an opaque token below the cap; clipping is a separate operation.
    long_text = 'Fictional result under bounded conditions. ' * 100
    excerpt, clipped = module._excerpt(long_text)
    assert clipped and len(excerpt) == 1200 and 'middle omitted' in excerpt
    assert module.validate_index(destination / 'trace-samples.json', env) == index


def test_unreviewed_changed_content_and_source_fail_closed(sample, tmp_path):
    module, source, candidate, review, env = sample
    approval = json.loads(review.read_text()); approval['samples'][0]['content_sha256'] = 'f' * 64
    review.write_text(json.dumps(approval))
    with pytest.raises(ValueError, match='changed'):
        module.export(candidate, review, tmp_path / 'public/data', env)
    sample_path = next((candidate / 'trace-samples').glob('*.json'))
    value = json.loads(sample_path.read_text()); value['traces'][0]['content'] = 'modified'
    sample_path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='hash'):
        module.validate_sample(sample_path, env)


def test_no_unbounded_fields_or_false_human_privacy_claims(sample):
    module, _, candidate, _, env = sample
    path = next((candidate / 'trace-samples').glob('*.json'))
    value = json.loads(path.read_text()); value['raw_task'] = 'forbidden'
    with pytest.raises(ValueError):
        module.Sample.model_validate(value)
    value.pop('raw_task'); value['human_privacy_review_claimed'] = True
    with pytest.raises(ValueError):
        module.Sample.model_validate(value)
