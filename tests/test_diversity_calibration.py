import asyncio
from collections import Counter
import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def calibration(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / 'scripts'))
    docket = importlib.import_module('multidomain_docket')
    module = importlib.import_module('diversity_calibration')
    monkeypatch.setattr(docket, 'ROOT', tmp_path)
    catalog = tmp_path / 'results/catalog'; docket.build(catalog)
    pins = root / 'configs/diversity_models.example.json'
    return module, catalog, pins, 'humanities-archive_chronology-0'


def test_compact_schedule_model_topology_controls(calibration, tmp_path):
    module, catalog, pins, task = calibration
    plan = module.prepare(tmp_path / 'results/compact', catalog, pins, task)
    assert plan['planned_runs'] == 24 and plan['planned_calls'] == 360
    checks = plan['jobs'][:18]
    assert {j['composition'] for j in checks} == set(module.MODEL_KEYS)
    assert {j['topology'] for j in checks} == {'ring', 'star', 'complete'}
    for i in range(0, len(plan['jobs']), 2):
        clean, injected = plan['jobs'][i:i+2]
        assert clean['intervention'] == 'clean' and injected['intervention'] == 'marker_override'
        assert clean['agent_models'] == injected['agent_models'] and clean['seed'] == injected['seed']
        assert all(role == 'identical' for role in clean['agent_roles'].values())
    assert Counter(plan['jobs'][-1]['agent_models'].values()) == {'qwen': 2, 'lfm': 2, 'nemotron': 1}


def test_balanced_rotation_and_roles_are_separate_cohorts(calibration, tmp_path):
    module, catalog, pins, task = calibration
    plan = module.prepare(tmp_path / 'results/balanced', catalog, pins, task, rotations=5, roles=True)
    assert plan['planned_runs'] == 78 and plan['planned_calls'] == 1170
    for node in range(5):
        jobs = [j for j in plan['jobs'] if j['phase'] == 'heterogeneous_calibration' and j['topology'] == 'ring' and j['intervention'] == 'clean']
        assert Counter(j['agent_models'][f'agent_{node}'] for j in jobs) == {'qwen': 2, 'lfm': 2, 'nemotron': 1}
        specialized = [j for j in plan['jobs'] if j['phase'] == 'role_calibration' and j['topology'] == 'ring' and j['intervention'] == 'clean']
        assert set(j['agent_roles'][f'agent_{node}'] for j in specialized) == set(module.ROLES)
    assert len({j['cohort'] for j in plan['jobs']}) == 13


def test_mock_all_patterns_sealed_and_isolated(calibration, tmp_path):
    module, catalog, pins, task = calibration
    root = tmp_path / 'results/mock'
    plan = module.prepare(root, catalog, pins, task)
    state = asyncio.run(module.run(root))
    assert state['status'] == 'completed' and state['completed_runs'] == 24
    recovered = module.recover(root, plan)
    assert recovered['returned_calls'] == 360 and not recovered['failures']
    for index, path in recovered['done'].items():
        m = json.loads((path / 'manifest.json').read_text()); c = json.loads((path / 'config.snapshot.json').read_text())
        assert m['agent_models'] == c['agent_models']
        graph = module.study_adjacency(plan['jobs'][index]['topology'], 5)
        events = module.read_events(path / 'events.jsonl')
        for event in events:
            if event['event_type'] == 'message_delivered':
                assert event['round'] > 0 and event['receiver_id'] in graph[event['sender_id']]
                assert event['metadata']['source_round'] == event['round'] - 1
            if event['event_type'] == 'inference_requested':
                messages = event['metadata']['messages']
                assert 'oracle_hash' not in json.dumps(messages)
                assert json.loads(messages[-1]['content'])['required_claim_count'] == 10


def test_native_heterogeneous_sampler_uses_each_assigned_model(calibration, tmp_path):
    module, catalog, pins, task = calibration
    plan = module.prepare(tmp_path / 'results/native-fixture', catalog, pins, task)
    _, payloads, oracles = module.validate(tmp_path / 'results/native-fixture')
    job = plan['jobs'][18]; seen = []
    class NativeFixture:
        identity = {'backend_version': 'fixture-version'}
        audit = None
        async def chat(self, messages, sampling):
            seen.append(sampling.model)
            self.audit('http_attempt', {'attempt': 1})
            response = await module.Mock().chat(messages)
            response.metadata = {'backend': 'ollama', 'model': sampling.model, 'done_reason': 'stop', 'prompt_eval_count': 200}
            return response
    async def guard():
        return None
    path = tmp_path / 'results/driver'
    assert asyncio.run(module.one_run(path, plan, job, payloads[task], oracles[task], NativeFixture(), guard, 'ollama')) == 'completed'
    models = [plan['model_pins'][job['agent_models'][f'agent_{i}']]['model'] for i in range(5)]
    assert seen == models * 3 and len(set(seen)) == 3


def test_incompatible_model_stops_before_heterogeneous_calls(calibration, tmp_path, monkeypatch):
    module, catalog, pins, task = calibration
    root = tmp_path / 'results/incompatible'; module.prepare(root, catalog, pins, task)
    class Bad(module.Mock):
        async def chat(self, messages):
            response = await super().chat(messages)
            data = json.loads(response.content); data['claims'] = data['claims'][:4]
            response.content = json.dumps(data)
            return response
    monkeypatch.setattr(module, 'Mock', Bad)
    with pytest.raises(RuntimeError):
        asyncio.run(module.run(root))
    state = json.loads((root / 'diversity-state.json').read_text())
    assert state['completed_runs'] == 0 and state['failed_runs'] == 1
    assert state['last_attempt_failure_code'] == 'observed_model_format_incompatibility'
    assert len(list((root / 'runs').glob('job-*'))) == 1


def test_preflight_resume_and_pin_tampering(calibration, tmp_path):
    module, catalog, pins, task = calibration
    root = tmp_path / 'results/preflight'; plan = module.prepare(root, catalog, pins, task)
    first = asyncio.run(module.run(root, max_new_jobs=1))
    assert first['status'] == 'paused_for_review' and first['completed_runs'] == 1
    state = asyncio.run(module.run(root, resume=True))
    assert state['completed_runs'] == 24 and module.recover(root, plan)['returned_calls'] == 360
    data = json.loads((root / 'diversity-plan.json').read_text()); data['jobs'][0]['agent_models']['agent_0'] = 'lfm'
    (root / 'diversity-plan.json').write_text(json.dumps(data))
    with pytest.raises(ValueError, match='changed'):
        module.validate(root)
