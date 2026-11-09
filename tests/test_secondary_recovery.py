import asyncio
import importlib
import json
from pathlib import Path

import pytest

from contagion.events import EventRecorder
from contagion.models import ModelResponse
from contagion.storage import seal, source_fingerprint, verify


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    return importlib.import_module('secondary_recovery')


def test_new_output_budget_is_recorded_and_used(module, tmp_path):
    runner = importlib.import_module('secondary_review_v35')
    class Provider:
        identity = {'backend': 'mock', 'model': 'fixture'}
        configs = []
        async def chat(self, messages, config):
            self.configs.append(config)
            return ModelResponse(content='{"answer":{"findings":[]},"message":"Static review","refusal":false}', metadata={'backend': 'mock'})
    provider = Provider()
    directory = asyncio.run(runner.run_case({'id': 'fixture', 'planned_rounds': 2, 'input_length': 'short'},
        {'code_diff': 'inert'}, {'freeze_hash': 'a' * 64}, {'plan_hash': 'b' * 64}, provider,
        tmp_path / 'runs', 'ring', 'none', max_wall=20))
    config = json.loads((directory / 'config.snapshot.json').read_text())
    manifest = json.loads((directory / 'manifest.json').read_text())
    assert verify(directory) and manifest['status'] == 'completed'
    assert config['protocol_version'] == '3.5-repository-output-budget'
    assert config['max_output_tokens'] == 3072 and len(provider.configs) == 10
    assert all(c.max_output_tokens == 3072 for c in provider.configs)
    events = [json.loads(x) for x in (directory / 'events.jsonl').read_text().splitlines()]
    requests = [e for e in events if e['event_type'] == 'inference_requested']
    assert requests[0]['metadata']['max_output_tokens'] == 3072
    assert len(requests[5]['metadata']['messages']) == 5  # Full own history retained.


def test_new_context_margin_and_output_truncation_stop(module, tmp_path):
    runner = importlib.import_module('secondary_review_v35')
    class Provider:
        identity = {'backend': 'mock', 'model': 'fixture'}
        async def chat(self, messages, config):
            return ModelResponse(content='{}', metadata={'done_reason': 'stop', 'prompt_eval_count': 32768 - 3072})
    directory = asyncio.run(runner.run_case({'id': 'fixture', 'planned_rounds': 1, 'input_length': 'short'},
        {}, {'freeze_hash': 'a' * 64}, {'plan_hash': 'b' * 64}, Provider(), tmp_path / 'runs', 'ring', 'none'))
    manifest = json.loads((directory / 'manifest.json').read_text())
    assert manifest['status'] == 'budget_exhausted'
    assert manifest['failure_code'] == 'context_or_output_truncation_risk' and manifest['parse_failures'] == 0


def test_cancelled_run_is_sealed_failed_not_completed(module, tmp_path):
    runner = importlib.import_module('secondary_review_v35')
    class Provider:
        identity = {'backend': 'mock', 'model': 'fixture'}
        async def chat(self, messages, config):
            raise asyncio.CancelledError()
    output = tmp_path / 'runs'
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runner.run_case({'id': 'fixture', 'planned_rounds': 1, 'input_length': 'short'},
            {}, {'freeze_hash': 'a' * 64}, {'plan_hash': 'b' * 64}, Provider(), output, 'ring', 'none'))
    manifests = list(output.glob('*/manifest.json'))
    assert len(manifests) == 1 and verify(manifests[0].parent)
    assert json.loads(manifests[0].read_text())['status'] == 'failed'


@pytest.fixture
def parent(module, tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    root = tmp_path / 'results/campaigns/parent'; root.mkdir(parents=True)
    source = tmp_path / 'results/repository-runs/parent'
    jobs = [{'case_id': 'fixture', 'rounds': 1, 'topology': 'ring', 'freeze': 'freeze.json', 'calls': 10}]
    plan = {'plan_hash': 'a' * 64, 'source_hash': source_fingerprint(), 'controller_sha256': 'b' * 64,
            'jobs': jobs, 'catalog': 'fixture', 'seed': 2718, 'max_http_attempts': 12, 'max_run_seconds': 28800,
            'readiness': 'fixture', 'readiness_hash': 'r'}
    state = {'status': 'stopped', 'completed_pairs': 0, 'http_attempts': 0}
    (root / 'queue-state.json').write_text(json.dumps(state))
    monkeypatch.setattr(module, 'parent_plan', lambda _: plan.copy())
    monkeypatch.setattr(module, 'load_input', lambda *a: ({'freeze_hash': 'c' * 64}, {'id': 'fixture', 'planned_rounds': 1}, {}))
    attempt = source / 'job-000/attempt-001'; attempt.mkdir(parents=True)
    journal = EventRecorder(attempt / 'events.jsonl', attempt.name)
    journal.emit('http_attempt'); journal.emit('inference_response', metadata={'done_reason': 'length', 'eval_count': 1536})
    journal.emit('run_finished', metadata={'status': 'budget_exhausted'}); journal.close()
    config = {'protocol_version': '3.1-repository', 'task_id': 'fixture', 'rounds': 1, 'topology': 'ring',
              'intervention': 'none', 'seed': 2718, 'registry_freeze_hash': 'c' * 64,
              'source_hash': plan['source_hash'], 'max_output_tokens': 1536, 'context_tokens_requested': 32768}
    manifest = {'protocol_version': '3.1-repository', 'status': 'budget_exhausted', 'source_hash': plan['source_hash'],
                'controller_hash': plan['controller_sha256'], 'source_unchanged_on_exit': True, 'http_attempts': 1,
                'completed_model_calls': 1, 'parse_failures': 0, 'duration_seconds': 2,
                'model_identity': {'backend': 'ollama', 'worker_label': 'secondary', 'model': 'fixture', 'digest': 'd' * 64}}
    for name, data in [('config.snapshot.json', config), ('manifest.json', manifest), ('outcome.json', {})]:
        (attempt / name).write_text(json.dumps(data))
    seal(attempt)
    return module, root, source, attempt, plan


def test_authoritative_failed_response_debit_and_remaining_conditions(parent):
    module, root, source, attempt, plan = parent
    result = module.inspect(root, source)
    assert result['parent_http_attempts'] == 1 and result['parent_reported_http_attempts'] == 0
    assert result['remaining_scheduled_calls'] == 10 and result['remaining_original_call_authorization'] == 11
    assert result['attempts'][0]['diagnosis'] == 'output_token_ceiling_1536'
    assert [j['condition'] for j in result['remaining_jobs']] == ['none', 'benign_override']


def test_unknown_failure_or_corrupt_evidence_blocks_recovery(parent):
    module, root, source, attempt, plan = parent
    events = [json.loads(x) for x in (attempt / 'events.jsonl').read_text().splitlines()]
    events[1]['metadata']['done_reason'] = 'stop'
    (attempt / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events)); seal(attempt)
    with pytest.raises(ValueError, match='reviewed output-budget'):
        module.inspect(root, source)


def test_prepared_recovery_mock_preserves_parent_and_retains_budget(parent, monkeypatch, tmp_path):
    module, root, source, attempt, plan = parent
    scripts = tmp_path / 'scripts'; scripts.mkdir()
    actual = Path(__file__).resolve().parents[1] / 'scripts'
    for name in module.DEPENDENCIES:
        (scripts / name).write_bytes((actual / name).read_bytes())
    (root / 'freeze.json').write_text('{}')
    monkeypatch.setattr(module, 'validate_readiness', lambda _: {'readiness_hash': 'r', 'model': 'fixture', 'model_digest': 'd' * 64})
    monkeypatch.setattr(module, 'load_input', lambda *a: ({'freeze_hash': 'c' * 64},
        {'id': 'fixture', 'planned_rounds': 1, 'input_length': 'short'}, {'task_id': 'fixture', 'code_diff': 'inert'}))
    before = (root / 'queue-state.json').read_bytes()
    output = tmp_path / 'results/campaigns/continuation'
    frozen = module.prepare(root, output, source=source)
    assert frozen['protocol_version'] == '3.5-repository-output-budget'
    assert frozen['max_output_tokens'] == 3072 and frozen['max_http_attempts'] == 11
    result = asyncio.run(module.run(output, 'mock'))
    assert result['status'] == 'completed' and result['completed_runs'] == 2
    assert result['returned_calls'] == 10
    assert (root / 'queue-state.json').read_bytes() == before
    with pytest.raises(ValueError, match='already reserved'):
        module.prepare(root, tmp_path / 'results/campaigns/fork', source=source)
