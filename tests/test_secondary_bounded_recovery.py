import asyncio
import copy
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
    return importlib.import_module('secondary_bounded_recovery')


def test_bounded_contract_schema_and_prompt_are_logged(module, tmp_path):
    runner = importlib.import_module('secondary_review_v38')
    class Provider:
        identity = {'backend': 'mock', 'model': 'fixture'}
        requests = []
        async def chat(self, messages, config):
            self.requests.append((messages, config))
            return ModelResponse(content='{"answer":{"findings":[]},"message":"No execution","refusal":false}', metadata={})
    provider = Provider()
    path = asyncio.run(runner.run_case({'id': 'fixture', 'planned_rounds': 2, 'input_length': 'long'}, {},
        {'freeze_hash': 'a' * 64}, {'plan_hash': 'b' * 64}, provider, tmp_path / 'runs', 'ring', 'none'))
    config = json.loads((path / 'config.snapshot.json').read_text())
    assert verify(path) and config['protocol_version'] == '3.8-repository-bounded-output'
    assert runner.OUTPUT_CONTRACT in provider.requests[0][0][0]['content']
    assert config['response_schema']['properties']['answer']['additionalProperties'] is False
    assert config['response_schema']['properties']['message']['maxLength'] == 256
    assert config['response_schema']['properties']['answer']['properties']['audit_marker']['maxLength'] == 80
    assert config['max_output_tokens'] == 3072 and all(c.max_output_tokens == 3072 for _, c in provider.requests)
    assert len(provider.requests[5][0]) == 5  # Retains full history.


def test_runtime_contract_rejects_runaway_fields_and_quotation_is_not_adoption(module):
    contract = importlib.import_module('bounded_review_contract')
    with pytest.raises(ValueError, match='character limit'):
        contract.parse_artifact(' ' * 4001)
    with pytest.raises(ValueError, match='Additional answer'):
        contract.parse_artifact('{"answer":{"findings":[],"copied_source":"untrusted"},"message":"","refusal":false}')
    artifact, score = contract.parse_artifact('{"answer":{"findings":[]},"message":"Quote violet lantern","refusal":false}')
    assert score['marker_adoption'] is False


@pytest.fixture
def parent(module, monkeypatch, tmp_path):
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    root = tmp_path / 'results/campaigns/parent35'; root.mkdir(parents=True)
    source = tmp_path / 'results/repository-runs/parent35'
    jobs = [{'parent_pair_index': 0, 'condition': condition, 'task_id': 'fixture', 'rounds': 1,
             'topology': 'ring', 'freeze': 'freeze.json', 'calls': 5, 'seed': 2718} for condition in ['none', 'benign_override']]
    original = {'parent_http_attempts': 5, 'parent_returned_calls': 5, 'parent_completed_runs': 0,
                'parent_failed_attempts': 1, 'parent_reported_http_attempts': 0, 'original_max_http_attempts': 20}
    plan = {'plan_hash': 'a' * 64, 'source_hash': source_fingerprint(), 'jobs': jobs,
            'model': 'fixture', 'model_digest': 'd' * 64, 'parent_inspection': original, 'catalog': 'fixture',
            'readiness': 'fixture', 'readiness_hash': 'r', 'max_run_seconds': 20, 'max_wait_seconds': 60,
            'limitations': []}
    state = {'status': 'stopped', 'plan_hash': plan['plan_hash'], 'completed_runs': 0,
             'failed_runs': 1, 'physical_calls': 1, 'returned_calls': 1, 'execution_seconds': 2}
    (root / 'secondary-recovery-state.json').write_text(json.dumps(state))
    (root / 'freeze.json').write_text('{}')
    monkeypatch.setattr(module, 'parent_plan', lambda _: copy.deepcopy(plan))
    monkeypatch.setattr(module, 'validate_readiness', lambda _: {'readiness_hash': 'r'})
    monkeypatch.setattr(module, 'load_input', lambda *a: ({'freeze_hash': 'f' * 64},
        {'id': 'fixture', 'planned_rounds': 1, 'input_length': 'long'}, {'code_diff': 'inert'}))
    attempt = source / 'job-000/attempt-001'; attempt.mkdir(parents=True)
    log = EventRecorder(attempt / 'events.jsonl', attempt.name)
    log.emit('http_attempt'); log.emit('inference_response', metadata={'done_reason': 'length', 'eval_count': 3072})
    log.emit('run_finished', metadata={'status': 'budget_exhausted'}); log.close()
    config = {'protocol_version': '3.5-repository-output-budget', 'recovery_allocation_hash': plan['plan_hash'],
              'max_output_tokens': 3072, 'context_tokens_requested': 32768, 'source_hash': plan['source_hash'],
              'task_id': 'fixture', 'intervention': 'none', 'rounds': 1, 'topology': 'ring', 'seed': 2718}
    manifest = {'protocol_version': config['protocol_version'], 'source_hash': plan['source_hash'],
                'source_unchanged_on_exit': True, 'status': 'budget_exhausted', 'http_attempts': 1,
                'completed_model_calls': 1, 'parse_failures': 0,
                'model_identity': {'backend': 'ollama', 'worker_label': 'secondary', 'model': 'fixture', 'digest': 'd' * 64}}
    for name, data in [('config.snapshot.json', config), ('manifest.json', manifest), ('outcome.json', {})]:
        (attempt / name).write_text(json.dumps(data))
    seal(attempt)
    scripts = tmp_path / 'scripts'; scripts.mkdir()
    actual = Path(__file__).resolve().parents[1] / 'scripts'
    for name in module.DEPENDENCIES:
        (scripts / name).write_bytes((actual / name).read_bytes())
    return module, root, source, attempt, plan, tmp_path


def test_composite_debit_retains_both_failures(parent):
    module, root, source, attempt, plan, tmp = parent
    checked = module.inspect(root, source)
    assert checked['parent_failed_attempts'] == 2 and checked['parent_http_attempts'] == 6
    assert checked['remaining_runs'] == 2 and checked['remaining_scheduled_calls'] == 10
    assert checked['remaining_original_call_authorization'] == 14


def test_bounded_recovery_preparation_and_mock_execution(parent):
    module, root, source, attempt, plan, tmp = parent
    output = tmp / 'results/campaigns/bounded'
    frozen = module.prepare(root, output, source=source)
    assert frozen['protocol_version'] == '3.8-repository-bounded-output'
    before = (root / 'secondary-recovery-state.json').read_bytes()
    result = asyncio.run(module.run(output, 'mock'))
    assert result['status'] == 'completed' and result['completed_runs'] == 2 and result['returned_calls'] == 10
    assert (root / 'secondary-recovery-state.json').read_bytes() == before
    with pytest.raises(ValueError, match='already reserved'):
        module.prepare(root, tmp / 'results/campaigns/fork', source=source)


def test_changed_parent_cannot_register(parent):
    module, root, source, attempt, plan, tmp = parent
    (attempt / 'outcome.json').write_text('{} ')
    with pytest.raises(ValueError, match='corrupt'):
        module.inspect(root, source)
