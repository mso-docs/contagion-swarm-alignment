import copy
import asyncio
import importlib
import json
from pathlib import Path

import pytest

from contagion.events import EventRecorder
from contagion.storage import seal
from contagion.storage import source_fingerprint


@pytest.fixture
def recovery(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    module = importlib.import_module('primary_recovery_registration')
    queue_module = importlib.import_module('primary_long_queue')
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(queue_module, 'ROOT', tmp_path)
    parent = tmp_path / 'results/campaigns/parent'; parent.mkdir(parents=True)
    source = tmp_path / 'results/repository-runs/parent'
    jobs = [{'task_id': str(i), 'rounds': 1, 'topology': 'ring', 'seed': 10001, 'phase': 'evaluation',
             'defense': 'plain', 'intervention': 'none', 'calls': 5, 'id': f'job{i}'} for i in range(3)]
    plan = {'plan_hash': 'a' * 64, 'protocol_version': '3.3-repository-safeguard', 'source_hash': source_fingerprint(),
            'model': 'fixture', 'model_digest': 'c' * 64, 'jobs': jobs, 'planned_runs': 3, 'planned_calls': 15,
            'max_http_attempts': 20, 'max_wall_seconds': 20, 'dependencies': {'fixture.py': 'd' * 64},
            'limitations': [], 'tasks': [], 'after': 'old-prerequisite', 'readiness': None,
            'max_wait_seconds': 60, 'max_run_seconds': 60}
    (parent / 'controller').mkdir(); (parent / 'controller/fixture.py').write_text('fixture')
    runner = Path(__file__).resolve().parents[1] / 'scripts/primary_repository_runner.py'
    (parent / 'controller/primary_repository_runner.py').write_bytes(runner.read_bytes())
    plan['dependencies']['primary_repository_runner.py'] = module.sha(runner)
    (parent / 'primary-long-plan.json').write_text(json.dumps(plan))
    state = {'status': 'stopped', 'plan_hash': plan['plan_hash'], 'completed_runs': 1,
             'failed_runs': 1, 'physical_calls': 8, 'returned_calls': 7, 'execution_seconds': 19}
    (parent / 'primary-long-state.json').write_text(json.dumps(state))
    monkeypatch.setattr(module, '_parent_plan', lambda root: copy.deepcopy(plan))
    monkeypatch.setattr(queue_module, 'validate_plan', lambda root: json.loads((Path(root) / 'primary-long-plan.json').read_text()))
    monkeypatch.setattr(queue_module, 'load_payload', lambda plan, job: ({'id': job['task_id'], 'input_length': 'short'}, {'task_id': job['task_id'], 'code_diff': ''}))

    def attempt(index, response_count, http_count, status, failure=None):
        root = source / f'job-{index:03}' / 'attempt-001'; root.mkdir(parents=True)
        log = EventRecorder(root / 'events.jsonl', root.name)
        for i in range(response_count):
            log.emit('http_attempt'); log.emit('inference_response')
            log.emit('artifact', 0, agent_id=f'agent_{i}')
        for _ in range(http_count - response_count): log.emit('http_attempt')
        log.emit('run_finished', metadata={'status': status}); log.close()
        config = {**jobs[index], 'protocol_version': plan['protocol_version'],
                  'registry_freeze_hash': plan['plan_hash'], 'source_hash': plan['source_hash']}
        manifest = {'protocol_version': plan['protocol_version'], 'source_hash': plan['source_hash'],
                    'source_unchanged_on_exit': True, 'plan_hash': plan['plan_hash'], 'status': status,
                    'failure': failure, 'http_attempts': http_count, 'completed_model_calls': response_count,
                    'parse_failures': 0, 'model_identity': {'backend': 'ollama', 'worker_label': 'primary',
                    'model': plan['model'], 'digest': plan['model_digest']}}
        for name, data in [('config.snapshot.json', config), ('manifest.json', manifest), ('outcome.json', {})]:
            (root / name).write_text(json.dumps(data))
        seal(root)
        return root
    completed = attempt(0, 5, 5, 'completed')
    failed = attempt(1, 2, 3, 'failed', 'RemoteProtocolError')
    return module, parent, source, plan, state, completed, failed, tmp_path


def test_continuation_skips_completed_and_preserves_lost_call_debit(recovery):
    module, parent, source, plan, state, complete, failed, tmp = recovery
    before = {str(p): p.read_bytes() for p in parent.rglob('*') if p.is_file()}
    result = module.inspect(parent, source)
    assert result['remaining_parent_indexes'] == [1, 2]
    assert result['parent_http_attempts'] == 8 and result['parent_returned_calls'] == 7
    assert result['remaining_original_call_authorization'] == 12
    output = tmp / 'results/campaigns/continuation'
    frozen = module.prepare(parent, output, 8, source)
    assert frozen['jobs'] == plan['jobs'][1:] and frozen['planned_runs'] == 2
    assert frozen['max_http_attempts'] == 12 and frozen['max_wall_seconds'] == 8 * 3600
    assert frozen['recovery_lineage']['parent_failed_attempts'] == 1
    assert frozen['recovery_lineage']['parent_study_complete'] is False
    assert module.validate(output) == frozen
    assert all(Path(path).read_bytes() == value for path, value in before.items())
    with pytest.raises(ValueError, match='fork'):
        module.prepare(parent, tmp / 'results/campaigns/duplicate', 8, source)


def test_unsealed_or_changed_parent_blocks_registration(recovery):
    module, parent, source, plan, state, complete, failed, tmp = recovery
    (failed / 'checksum.sha256').unlink()
    with pytest.raises(ValueError, match='unsealed'):
        module.inspect(parent, source)


def test_active_or_insufficient_budget_cannot_be_continued(recovery):
    module, parent, source, plan, state, complete, failed, tmp = recovery
    state['status'] = 'running'; (parent / 'primary-long-state.json').write_text(json.dumps(state))
    with pytest.raises(ValueError, match='stopped'):
        module.inspect(parent, source)
    state['status'] = 'stopped'; (parent / 'primary-long-state.json').write_text(json.dumps(state))
    plan['max_http_attempts'] = 17
    with pytest.raises(ValueError, match='budget'):
        module.inspect(parent, source)


def test_semantic_or_parse_failure_not_treated_as_transport(recovery):
    module, parent, source, plan, state, complete, failed, tmp = recovery
    data = json.loads((failed / 'manifest.json').read_text()); data['failure'] = 'ValueError'
    (failed / 'manifest.json').write_text(json.dumps(data)); seal(failed)
    with pytest.raises(ValueError, match='transport'):
        module.inspect(parent, source)


def test_parent_change_after_freeze_blocks_run(recovery):
    module, parent, source, plan, state, complete, failed, tmp = recovery
    output = tmp / 'results/campaigns/continuation'
    module.prepare(parent, output, 8, source)
    state['execution_seconds'] = 20
    (parent / 'primary-long-state.json').write_text(json.dumps(state))
    with pytest.raises(ValueError, match='changed after'):
        module.validate(output)


def test_mock_continuation_runs_only_unfinished_assignments(recovery):
    module, parent, source, plan, state, complete, failed, tmp = recovery
    output = tmp / 'results/campaigns/continuation'
    module.prepare(parent, output, 8, source)
    from primary_long_queue import run
    result = asyncio.run(run(output, 'mock'))
    assert result['status'] == 'completed' and result['completed_runs'] == 2
    manifests = list((tmp / 'results/repository-runs/continuation').rglob('manifest.json'))
    assert len(manifests) == 2
    assert sum(json.loads(p.read_text())['completed_model_calls'] for p in manifests) == 10
    assert json.loads((parent / 'primary-long-state.json').read_text())['status'] == 'stopped'
