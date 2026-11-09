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
    return importlib.import_module('primary_output_recovery')


def test_primary_runner_logs_schema_output_and_attribution(module, tmp_path):
    runner = importlib.import_module('primary_review_v36')
    class Provider:
        identity = {'backend': 'mock', 'model': 'fixture'}
        requests = []
        async def chat(self, messages, config):
            self.requests.append((messages, config))
            return ModelResponse(content='{"answer":{"findings":[]},"message":"No execution","refusal":false}', metadata={})
    provider = Provider()
    plan = {'plan_hash': 'a' * 64, 'source_hash': source_fingerprint(),
            'dependencies': {'primary_review_v36.py': 'b' * 64}, 'max_run_seconds': 20}
    job = {'rounds': 2, 'topology': 'ring', 'seed': 21001, 'phase': 'evaluation',
           'intervention': 'none', 'defense': 'source_attribution'}
    path = asyncio.run(runner.run_case({'id': 'fixture', 'input_length': 'long'}, {}, plan, job, provider, tmp_path / 'runs'))
    config = json.loads((path / 'config.snapshot.json').read_text())
    manifest = json.loads((path / 'manifest.json').read_text())
    assert verify(path) and manifest['status'] == 'completed' and len(provider.requests) == 10
    assert config['protocol_version'] == '3.6-repository-output-budget' and config['max_output_tokens'] == 3072
    assert all(c.max_output_tokens == 3072 for _, c in provider.requests)
    schema = config['response_schema']['properties']['answer']
    assert schema['additionalProperties'] is False and schema['properties']['audit_marker']['maxLength'] == 80
    assert runner.ATTRIBUTION_RULE in provider.requests[0][0][0]['content']
    assert runner.OUTPUT_CONTRACT in provider.requests[0][0][0]['content']
    assert len(provider.requests[5][0]) == 5  # Full own history, no eviction amendment.


def test_primary_runner_rejects_extra_fields_and_uses_new_context_margin(module, tmp_path):
    runner = importlib.import_module('primary_review_v36')
    with pytest.raises(ValueError, match='Additional answer'):
        runner.parse_artifact('{"answer":{"findings":[],"invented":"long"},"message":"","refusal":false}')
    class Provider:
        identity = {'backend': 'mock', 'model': 'fixture'}
        async def chat(self, messages, config):
            return ModelResponse(content='{}', metadata={'prompt_eval_count': 32768 - 3072, 'done_reason': 'stop'})
    plan = {'plan_hash': 'a' * 64, 'source_hash': source_fingerprint(),
            'dependencies': {'primary_review_v36.py': 'b' * 64}, 'max_run_seconds': 20}
    job = {'rounds': 1, 'topology': 'ring', 'seed': 21001, 'phase': 'evaluation', 'intervention': 'none', 'defense': 'plain'}
    path = asyncio.run(runner.run_case({'id': 'fixture', 'input_length': 'long'}, {}, plan, job, Provider(), tmp_path / 'runs'))
    manifest = json.loads((path / 'manifest.json').read_text())
    assert manifest['status'] == 'budget_exhausted' and manifest['failure_code'] == 'context_or_output_truncation_risk'
    assert manifest['parse_failures'] == 0


@pytest.fixture
def ancestors(module, monkeypatch, tmp_path):
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    original_root = tmp_path / 'results/campaigns/original'; original_root.mkdir(parents=True)
    (original_root / 'primary-long-state.json').write_text('{"status":"stopped"}')
    continuation = tmp_path / 'results/campaigns/continuation'; continuation.mkdir(parents=True)
    source = tmp_path / 'results/repository-runs/continuation'
    jobs = [{'task_id': str(i), 'rounds': 1, 'topology': 'ring', 'seed': 21001, 'phase': 'evaluation',
             'defense': 'plain', 'intervention': 'none', 'calls': 5} for i in range(2)]
    plan = {'plan_hash': 'a' * 64, 'source_hash': source_fingerprint(), 'model': 'fixture', 'model_digest': 'd' * 64,
            'jobs': jobs, 'recovery_lineage': {'parent_queue': str(original_root), 'continuation_to_parent_index': [1, 2]},
            'limitations': [], 'readiness': 'fixture', 'readiness_hash': 'r', 'max_run_seconds': 20}
    (continuation / 'primary-long-plan.json').write_text(json.dumps(plan))
    state = {'status': 'stopped', 'plan_hash': plan['plan_hash'], 'completed_runs': 1, 'failed_runs': 1,
             'physical_calls': 6, 'returned_calls': 6, 'execution_seconds': 12}
    (continuation / 'primary-long-state.json').write_text(json.dumps(state))
    original = {'parent_completed_runs': 1, 'parent_failed_attempts': 1, 'parent_http_attempts': 6,
                'original_max_http_attempts': 20, 'parent_execution_seconds': 3,
                'parent_state_sha256': module.sha(original_root / 'primary-long-state.json')}
    monkeypatch.setattr(module, 'ancestor', lambda _: (copy.deepcopy(plan), copy.deepcopy(original)))
    queue = importlib.import_module('primary_long_queue')
    monkeypatch.setattr(queue, 'load_payload', lambda p, j: ({'id': j['task_id'], 'input_length': 'long'}, {'code_diff': 'inert'}))
    def attempt(index, count, status):
        root = source / f'job-{index:03}' / 'attempt-001'; root.mkdir(parents=True)
        log = EventRecorder(root / 'events.jsonl', root.name)
        for i in range(count):
            log.emit('http_attempt')
            log.emit('inference_response', metadata={'done_reason': 'length' if status != 'completed' and i == count - 1 else 'stop'})
            if status == 'completed' or i != count - 1:
                log.emit('artifact', 0, agent_id=f'agent_{i}')
        log.emit('run_finished', metadata={'status': status}); log.close()
        config = {**jobs[index], 'protocol_version': '3.3-repository-safeguard', 'registry_freeze_hash': plan['plan_hash'],
                  'source_hash': plan['source_hash'], 'max_output_tokens': 1536}
        manifest = {'plan_hash': plan['plan_hash'], 'source_hash': plan['source_hash'], 'protocol_version': '3.3-repository-safeguard',
                    'source_unchanged_on_exit': True, 'status': status, 'http_attempts': count, 'completed_model_calls': count,
                    'parse_failures': 0, 'model_identity': {'backend': 'ollama', 'worker_label': 'primary', 'model': 'fixture', 'digest': 'd' * 64}}
        for name, data in [('config.snapshot.json', config), ('manifest.json', manifest), ('outcome.json', {})]:
            (root / name).write_text(json.dumps(data))
        seal(root)
        return root
    complete = attempt(0, 5, 'completed'); failed = attempt(1, 1, 'budget_exhausted')
    scripts = tmp_path / 'scripts'; scripts.mkdir()
    actual = Path(__file__).resolve().parents[1] / 'scripts'
    for name in module.DEPENDENCIES:
        (scripts / name).write_bytes((actual / name).read_bytes())
    return module, continuation, source, complete, failed, tmp_path


def test_composite_counts_debit_both_allocations_and_skip_both_completions(ancestors):
    module, continuation, source, complete, failed, tmp = ancestors
    result = module.inspect(continuation, source)
    assert result['completed_original_runs'] == 2 and result['cumulative_prior_http_attempts'] == 12
    assert result['remaining_runs'] == 1 and result['remaining_scheduled_calls'] == 5
    assert result['remaining_original_call_authorization'] == 8 and result['remaining_original_indexes'] == [2]


def test_fresh_output_continuation_mock_and_unique_reservation(ancestors):
    module, continuation, source, complete, failed, tmp = ancestors
    before = (continuation / 'primary-long-state.json').read_bytes()
    output = tmp / 'results/campaigns/output-continuation'
    plan = module.prepare(continuation, output, source=source)
    assert plan['max_output_tokens'] == 3072 and plan['planned_runs'] == 1 and plan['max_http_attempts'] == 8
    result = asyncio.run(module.run(output, 'mock'))
    assert result['status'] == 'completed' and result['completed_runs'] == 1 and result['returned_calls'] == 5
    assert (continuation / 'primary-long-state.json').read_bytes() == before
    with pytest.raises(ValueError, match='already reserved'):
        module.prepare(continuation, tmp / 'results/campaigns/fork', source=source)


def test_stopped_registered_prerequisite_prevents_model_calls(ancestors):
    module, continuation, source, complete, failed, tmp = ancestors
    after = tmp / 'results/prior-state.json'; after.write_text('{"status":"stopped"}')
    output = tmp / 'results/campaigns/output-continuation'
    plan = module.prepare(continuation, output, source=source, after=after)
    assert plan['after'] == str(after.resolve()) and plan['max_wait_seconds'] == 96 * 3600
    with pytest.raises(RuntimeError, match='preceding'):
        asyncio.run(module.run(output, 'mock'))
    state = json.loads((output / 'primary-output-state.json').read_text())
    assert state['status'] == 'stopped' and state['returned_calls'] == 0


def test_changed_ancestor_seal_blocks_recovery(ancestors):
    module, continuation, source, complete, failed, tmp = ancestors
    (failed / 'outcome.json').write_text('{"changed":true}')
    with pytest.raises(ValueError, match='corrupt'):
        module.inspect(continuation, source)


def test_registration_does_not_take_primary_inference_lease(ancestors):
    import fcntl
    module, continuation, source, complete, failed, tmp = ancestors
    lock = tmp / 'results/checkpoint-gates/controller-primary.lock'; lock.parent.mkdir(parents=True)
    with lock.open('a') as active_allocation:
        fcntl.flock(active_allocation, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = module.prepare(continuation, tmp / 'results/campaigns/output-continuation', source=source)
    assert plan['planned_runs'] == 1
