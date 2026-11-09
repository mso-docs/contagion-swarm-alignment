import asyncio
import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def modules(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    docket = importlib.import_module('multidomain_docket')
    live = importlib.import_module('multidomain_live')
    monkeypatch.setattr(docket, 'ROOT', tmp_path)
    catalog = tmp_path / 'results/catalog'
    docket.build(catalog)
    return docket, live, catalog


def test_plan_dev_first_separate_domain_checks(modules, tmp_path):
    docket, live, catalog = modules
    root = tmp_path / 'results/live'
    plan = live.prepare(root, catalog, 'installed-model', 'a' * 64, rounds=5)
    assert plan['planned_runs'] == 45
    assert plan['planned_calls'] == 975
    checks = plan['jobs'][:15]
    assert {j['domain'] for j in checks} == set(docket.DOMAINS)
    assert all(j['rounds'] == 3 and j['phase'] == 'integration_precheck' for j in checks)
    assert all(j['split'] == 'evaluation' for j in plan['jobs'][15:])
    assert live.validate(root)[0] == plan


def test_full_mock_retains_sealed_requests_without_oracle(modules, tmp_path):
    _, live, catalog = modules
    root = tmp_path / 'results/mock'
    plan = live.prepare(root, catalog, 'installed-model', 'a' * 64, rounds=5)
    state = asyncio.run(live.run(root))
    assert state['status'] == 'completed' and state['completed_runs'] == 45
    recovered = live.recover(root, plan)
    assert recovered['returned_calls'] == 975 and recovered['physical_calls'] == 0
    assert not recovered['failures']
    for path in recovered['done'].values():
        events = live.read_events(path / 'events.jsonl')
        assert not any(e['event_type'] == 'message_delivered' and e['round'] == 0 for e in events)
        for event in events:
            if event['event_type'] == 'inference_requested':
                text = json.dumps(event['metadata']['messages'])
                assert 'oracle_hash' not in text and 'reference_answer' not in text
    assert json.loads((root / 'development-gate.private.json').read_text())['status'] == 'mock_shape_checks_only'


def test_explicit_retry_preserves_failed_attempt_and_receipt(modules, tmp_path, monkeypatch):
    _, live, catalog = modules
    root = tmp_path / 'results/retry'
    plan = live.prepare(root, catalog, 'installed-model', 'a' * 64, rounds=5)
    original = live.Mock
    class Failed(original):
        async def chat(self, messages):
            raise RuntimeError('not public diagnostic')
    monkeypatch.setattr(live, 'Mock', Failed)
    with pytest.raises(RuntimeError):
        asyncio.run(live.run(root))
    previous = root / 'runs/job-000/attempt-001/checksum.sha256'
    old_hash = live.sha(previous)
    with pytest.raises(ValueError, match='retry'):
        asyncio.run(live.run(root, resume=True))
    monkeypatch.setattr(live, 'Mock', original)
    state = asyncio.run(live.run(root, resume=True, retry_failed=True))
    assert state['completed_runs'] == 45 and state['failed_runs'] == 1
    assert live.sha(previous) == old_hash
    receipt = json.loads(next((root / 'recovery').glob('*.json')).read_text())
    assert receipt['retained_failures'][0]['evidence_hash'] == old_hash
    assert len(live.recover(root, plan)['failures']) == 1


def test_fail_closed_on_seal_change_and_unknown_evidence_gate(modules, tmp_path):
    _, live, catalog = modules
    root = tmp_path / 'results/seal'
    plan = live.prepare(root, catalog, 'installed-model', 'a' * 64, rounds=5)
    asyncio.run(live.run(root))
    recovered = live.recover(root, plan)
    _, payloads, _ = live.validate(root)
    with pytest.raises(ValueError, match='indeterminate'):
        live.feasibility(plan, recovered['done'], payloads, 'ollama')
    path = recovered['done'][0] / 'outcome.json'
    path.write_text('{}')
    with pytest.raises(ValueError, match='seal'):
        live.recover(root, plan)


def test_no_live_outside_primary_config_and_stop_file(modules, tmp_path):
    _, live, catalog = modules
    root = tmp_path / 'results/stopped'
    live.prepare(root, catalog, 'installed-model', 'a' * 64, rounds=5)
    (root / 'STOP').write_text('operator stop')
    with pytest.raises(Exception):
        asyncio.run(live.run(root))
    assert not list((root / 'runs').glob('*'))
    assert json.loads((root / 'multidomain-live-state.json').read_text())['failure_code'] == 'operator_stop'
