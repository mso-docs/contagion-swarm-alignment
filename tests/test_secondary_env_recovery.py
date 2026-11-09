import asyncio
import copy
import importlib
import json
from pathlib import Path

import pytest

from contagion.events import EventRecorder
from contagion.storage import seal, source_fingerprint


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    monkeypatch.delenv('SECONDARY_SERVER_ID', raising=False)
    monkeypatch.delenv('SECONDARY_PROJECT_DIR', raising=False)
    return importlib.import_module('secondary_env_recovery')


def test_only_selected_fields_are_parsed_and_cloud_values_are_not_copied(module, tmp_path):
    source = tmp_path / '.env'
    source.write_text("SECONDARY_SERVER_ID=fixture-secondary\nSECONDARY_PROJECT_DIR='~/contagion'\n"
                      "OPENROUTER_API_KEY='unparsed-fixture\nIGNORED=value with unquoted spaces\n")
    before = source.read_bytes()
    settings = module.telemetry_settings(source, {})
    assert set(settings) == set(module.TELEMETRY_KEYS)
    rendered = module.telemetry_bytes(settings)
    assert b'OPENROUTER' not in rendered and b'unparsed' not in rendered and b'IGNORED' not in rendered
    assert source.read_bytes() == before


def test_inherited_ssh_settings_only_and_frozen_override_drift(module, tmp_path, monkeypatch):
    source = tmp_path / '.env'; source.write_text('SECONDARY_SERVER_ID=file-alias\nSECONDARY_PROJECT_DIR=~/contagion\n')
    settings = module.telemetry_settings(source, {'SECONDARY_SERVER_ID': 'inherited-alias', 'OPENROUTER_API_KEY': 'fixture'})
    assert settings['SECONDARY_SERVER_ID'] == 'inherited-alias' and len(settings) == 2
    isolated = tmp_path / 'telemetry.env'; isolated.write_bytes(module.telemetry_bytes(settings))
    plan = {'telemetry_env_file': str(isolated), 'telemetry_env_sha256': module.sha(isolated)}
    monkeypatch.setenv('SECONDARY_SERVER_ID', 'changed-alias')
    with pytest.raises(ValueError, match='Inherited telemetry'):
        module.verify_telemetry(plan)


def test_capacity_probe_uses_only_isolated_frozen_file(module, tmp_path):
    isolated = tmp_path / 'telemetry.env'
    isolated.write_bytes(module.telemetry_bytes({'SECONDARY_SERVER_ID': 'fixture-secondary', 'SECONDARY_PROJECT_DIR': '~/contagion'}))
    plan = {'telemetry_env_file': str(isolated), 'telemetry_env_sha256': module.sha(isolated)}
    calls = []
    def execute(server, action, path):
        calls.append((server, action, path))
        return [{'capacity': {'ollama_reachable': True}}]
    assert module.telemetry_capacity(plan, execute) == {'ollama_reachable': True}
    assert calls == [('secondary', 'capacity', isolated)]
    isolated.write_text('changed')
    with pytest.raises(ValueError, match='Frozen telemetry'):
        module.telemetry_capacity(plan, execute)


@pytest.fixture
def parent(module, monkeypatch, tmp_path):
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    root = tmp_path / 'results/campaigns/parent38'; root.mkdir(parents=True)
    source = tmp_path / 'results/repository-runs/parent38'
    jobs = [{'parent_pair_index': 0, 'condition': condition, 'task_id': 'fixture', 'rounds': 1,
             'topology': 'ring', 'freeze': 'freeze.json', 'calls': 5, 'seed': 2718} for condition in ['none', 'benign_override']]
    original = {'parent_http_attempts': 5, 'parent_returned_calls': 5, 'parent_completed_runs': 0,
                'parent_failed_attempts': 2, 'parent_reported_http_attempts': 0, 'original_max_http_attempts': 20}
    plan = {'plan_hash': 'a' * 64, 'source_hash': source_fingerprint(), 'jobs': jobs,
            'model': 'fixture', 'model_digest': 'd' * 64, 'parent_inspection': original, 'catalog': 'fixture',
            'readiness': 'fixture', 'readiness_hash': 'r', 'max_run_seconds': 20, 'max_wait_seconds': 60,
            'limitations': []}
    state = {'status': 'stopped', 'plan_hash': plan['plan_hash'], 'completed_runs': 1,
             'failed_runs': 1, 'physical_calls': 7, 'returned_calls': 7, 'execution_seconds': 3}
    (root / 'secondary-bounded-state.json').write_text(json.dumps(state))
    (root / 'freeze.json').write_text('{}')
    monkeypatch.setattr(module, 'parent_plan', lambda _: copy.deepcopy(plan))
    monkeypatch.setattr(module, 'validate_readiness', lambda _: {'readiness_hash': 'r'})
    monkeypatch.setattr(module, 'load_input', lambda *a: ({'freeze_hash': 'f' * 64},
        {'id': 'fixture', 'planned_rounds': 1, 'input_length': 'long'}, {'code_diff': 'inert'}))
    def attempt(index, count, status):
        attempt_root = source / f'job-{index:03}/attempt-001'; attempt_root.mkdir(parents=True)
        log = EventRecorder(attempt_root / 'events.jsonl', attempt_root.name)
        for i in range(count):
            log.emit('inference_requested'); log.emit('http_attempt'); log.emit('inference_response')
            log.emit('artifact', 0, agent_id=f'agent_{i}')
        if status == 'failed':
            log.emit('inference_requested')
        log.emit('run_finished', metadata={'status': status}); log.close()
        config = {'protocol_version': '3.8-repository-bounded-output', 'recovery_allocation_hash': plan['plan_hash'],
                  'max_output_tokens': 3072, 'context_tokens_requested': 32768, 'source_hash': plan['source_hash'],
                  'task_id': 'fixture', 'intervention': jobs[index]['condition'], 'rounds': 1, 'topology': 'ring', 'seed': 2718}
        manifest = {'protocol_version': config['protocol_version'], 'source_hash': plan['source_hash'],
                    'source_unchanged_on_exit': True, 'status': status, 'http_attempts': count,
                    'completed_model_calls': count, 'parse_failures': 0,
                    'failure_class': 'ValueError' if status == 'failed' else None,
                    'model_identity': {'backend': 'ollama', 'worker_label': 'secondary', 'model': 'fixture', 'digest': 'd' * 64}}
        for name, data in [('config.snapshot.json', config), ('manifest.json', manifest), ('outcome.json', {})]:
            (attempt_root / name).write_text(json.dumps(data))
        seal(attempt_root)
    attempt(0, 5, 'completed'); attempt(1, 2, 'failed')
    scripts = tmp_path / 'scripts'; scripts.mkdir()
    actual = Path(__file__).resolve().parents[1] / 'scripts'
    for name in module.DEPENDENCIES:
        (scripts / name).write_bytes((actual / name).read_bytes())
    env = tmp_path / '.env'
    env.write_text("SECONDARY_SERVER_ID=fixture-secondary\nSECONDARY_PROJECT_DIR=~/contagion\nOPENROUTER_API_KEY='unparsed\n")
    return module, root, source, tmp_path, env


def test_composite_budget_skip_completed_and_real_engine_mock(parent):
    module, root, source, tmp, env = parent
    checked = module.inspect(root, source)
    assert checked['parent_http_attempts'] == 12 and checked['parent_failed_attempts'] == 3
    assert checked['remaining_runs'] == 1 and checked['remaining_original_call_authorization'] == 8
    output = tmp / 'results/campaigns/isolated'
    frozen = module.prepare(root, output, source=source, telemetry_env_source=env, inherited={})
    assert frozen['protocol_version'] == '3.8-repository-bounded-output'
    assert frozen['max_wall_seconds'] == 12 * 3600
    telemetry = output / 'telemetry.env'
    assert telemetry.stat().st_mode & 0o777 == 0o600
    assert 'OPENROUTER' not in telemetry.read_text()
    before = (root / 'secondary-bounded-state.json').read_bytes()
    result = asyncio.run(module.run(output, 'mock'))
    assert result['status'] == 'completed' and result['completed_runs'] == 1 and result['returned_calls'] == 5
    assert (root / 'secondary-bounded-state.json').read_bytes() == before
    with pytest.raises(ValueError, match='already reserved'):
        module.prepare(root, tmp / 'results/campaigns/fork', source=source, telemetry_env_source=env, inherited={})
