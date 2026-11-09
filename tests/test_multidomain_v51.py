import asyncio
import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def modules(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    docket = importlib.import_module('multidomain_docket')
    live = importlib.import_module('multidomain_live_v51')
    monkeypatch.setattr(docket, 'ROOT', tmp_path)
    frozen_hashes = live.hashes()
    real_root = live.ROOT
    monkeypatch.setattr(live, 'ROOT', tmp_path)
    monkeypatch.setattr(live, 'hashes', lambda: frozen_hashes)
    # Freeze archives from real scripts while keeping every generated artifact private to the test.
    (tmp_path / 'scripts').mkdir()
    for name in live.DEPENDENCIES:
        (tmp_path / 'scripts' / name).write_bytes((real_root / 'scripts' / name).read_bytes())
    catalog = tmp_path / 'results/catalog'; docket.build(catalog)
    return docket, live, catalog


def test_exact_per_task_schema_all_question_ids_and_no_repair(modules):
    _, live, _ = modules
    payload = {'questions': [{'id': f'Q{i:03d}'} for i in range(1, 13)]}
    schema = live.schema(payload)
    assert schema['properties']['claims']['minItems'] == schema['properties']['claims']['maxItems'] == 12
    assert schema['$defs']['Claim']['properties']['question_id']['enum'] == [q['id'] for q in payload['questions']]
    claims = [{'question_id': f'Q{i:03d}', 'answer': 'unknown', 'evidence_ids': [], 'confidence': .5, 'explanation': ''} for i in range(1, 5)]
    content = {'claims': claims, 'verification_performed': False, 'message': ''}
    with pytest.raises(live.QuestionCoverageError):
        live.parse(json.dumps(content), payload)
    assert len(content['claims']) == 4
    content['claims'] = claims * 3
    with pytest.raises(live.QuestionCoverageError):
        live.parse(json.dumps(content), payload)
    assert live.failure_code(live.QuestionCoverageError()) == 'question_coverage_mismatch'


def test_mock_schema_coverage_and_frozen_manifest(modules, tmp_path):
    _, live, catalog = modules
    root = tmp_path / 'results/new'
    plan = live.prepare(root, catalog, 'fixture-model', 'a' * 64, rounds=5)
    state = asyncio.run(live.run(root))
    assert state['status'] == 'completed' and state['completed_runs'] == 45
    recovered = live.recover(root, plan)
    assert recovered['returned_calls'] == 975 and not recovered['failures']
    for path in recovered['done'].values():
        c = json.loads((path / 'config.snapshot.json').read_text())
        m = json.loads((path / 'manifest.json').read_text())
        assert c['protocol_version'] == m['protocol_version'] == '5.1-multidomain-question-coverage'
        assert c['response_schema_hash'] == m['response_schema_hash']
        assert c['max_output_tokens'] == m['max_output_tokens'] == 2048
        for event in live.read_events(path / 'events.jsonl'):
            if event['event_type'] != 'inference_requested':
                continue
            messages = event['metadata']['messages']
            current = json.loads(messages[-1]['content'])
            assert current['required_claim_count'] == len(current['required_question_ids']) == 10
            assert all(q in messages[0]['content'] for q in current['required_question_ids'])
            assert 'oracle_hash' not in json.dumps(messages)


def test_parent_lifetime_debits_and_unique_reservation(modules, tmp_path, monkeypatch):
    _, live, catalog = modules
    old = importlib.import_module('multidomain_live')
    parent = tmp_path / 'results/old'; parent.mkdir(parents=True)
    manifest, _, _ = live.load(catalog)
    old_plan = {'protocol_version': '5.0-multidomain-evidence', 'model': 'fixture-model', 'model_digest': 'a' * 64,
                'catalog_hash': manifest['catalog_hash'], 'source_hash': live.source_fingerprint(),
                'max_http_attempts': 4950, 'max_execution_seconds': 172800,
                'jobs': [{'phase': 'integration_precheck', 'task_id': 'humanities-archive_chronology-0'} for _ in range(10)]}
    old_plan['plan_hash'] = live.digest(old_plan)
    (parent / 'multidomain-live-plan.json').write_text(json.dumps(old_plan))
    state = {'status': 'stopped', 'backend': 'ollama', 'plan_hash': old_plan['plan_hash'], 'physical_calls': 137,
             'returned_calls': 137, 'completed_runs': 9, 'failed_runs': 1, 'execution_seconds': 2009.734}
    (parent / 'multidomain-live-state.json').write_text(json.dumps(state))
    monkeypatch.setattr(old, 'recover', lambda root, plan: {'done': {i: 'fixture' for i in range(9)},
        'failures': [{'attempt': 'runs/job-009/attempt-001'}],
        'physical_calls': 137, 'returned_calls': 137, 'execution_debit_seconds': 2000})
    root = tmp_path / 'results/continuation'
    plan = live.prepare(root, catalog, 'fixture-model', 'a' * 64, parent=parent)
    assert plan['continuation']['remaining_physical_calls'] == 4813
    assert plan['max_execution_seconds'] == pytest.approx(170790.266)
    assert plan['max_http_attempts'] + 137 <= 4950
    assert plan['max_execution_seconds'] + 2009.734 <= 172800
    assert plan['jobs'][0]['task_id'] == 'humanities-archive_chronology-0'
    assert plan['jobs'][0]['intervention'] == 'clean'
    assert all(j['task_id'] == plan['jobs'][0]['task_id'] for j in plan['jobs'][:3])
    assert plan['development_order_amendment']['heldout_selection_changed'] is False
    live.validate(root)
    with pytest.raises(FileExistsError):
        live.prepare(tmp_path / 'results/duplicate', catalog, 'fixture-model', 'a' * 64, parent=parent)
    state['physical_calls'] = 0
    (parent / 'multidomain-live-state.json').write_text(json.dumps(state))
    with pytest.raises(ValueError, match='ledger'):
        live.validate(root)


def test_missing_coverage_stops_next_job_and_retains_code(modules, tmp_path, monkeypatch):
    _, live, catalog = modules
    root = tmp_path / 'results/coverage-failure'
    live.prepare(root, catalog, 'fixture-model', 'a' * 64, rounds=5)
    original = live.Mock
    class Missing(original):
        async def chat(self, messages):
            response = await super().chat(messages)
            data = json.loads(response.content); data['claims'] = data['claims'][:4]
            response.content = json.dumps(data)
            return response
    monkeypatch.setattr(live, 'Mock', Missing)
    with pytest.raises(RuntimeError):
        asyncio.run(live.run(root))
    m = json.loads(next((root / 'runs').glob('job-*/attempt-*/manifest.json')).read_text())
    assert m['failure_code'] == 'question_coverage_mismatch' and m['completed_model_calls'] == 1
    assert len(list((root / 'runs').glob('job-*'))) == 1


def test_registered_first_case_preflight_resumes_without_duplicate(modules, tmp_path):
    _, live, catalog = modules
    root = tmp_path / 'results/preflight'
    plan = live.prepare(root, catalog, 'fixture-model', 'a' * 64, rounds=5)
    first = asyncio.run(live.run(root, max_new_jobs=1))
    assert first['status'] == 'paused_for_review' and first['completed_runs'] == 1
    final = asyncio.run(live.run(root, resume=True))
    assert final['status'] == 'completed' and final['completed_runs'] == 45
    assert live.recover(root, plan)['returned_calls'] == 975


def test_twelve_question_schema_is_forwarded_to_native_sampling(modules, tmp_path):
    _, live, catalog = modules
    root = tmp_path / 'results/native-fixture'
    plan = live.prepare(root, catalog, 'fixture-model', 'a' * 64, rounds=5)
    job = plan['jobs'][0]
    payload = {'task_id': job['task_id'], 'evidence': [{'id': 'E001', 'text': 'Fictional fixture evidence.'}],
               'questions': [{'id': f'Q{i:03d}', 'prompt': 'Fixture question.'} for i in range(1, 13)]}
    oracle = {q['id']: {'answer': 'unknown', 'evidence_ids': []} for q in payload['questions']}
    seen = []
    class NativeFixture:
        identity = {'backend': 'ollama', 'model': 'fixture-model', 'digest': 'a' * 64, 'worker_label': 'primary'}
        audit = None
        async def chat(self, messages, sampling):
            seen.append(sampling.response_schema)
            assert sampling.response_schema['properties']['claims']['minItems'] == 12
            assert json.loads(messages[-1]['content'])['required_claim_count'] == 12
            self.audit('http_attempt', {'attempt': 1})
            response = await live.Mock().chat(messages)
            response.metadata = {'backend': 'ollama', 'done_reason': 'stop', 'prompt_eval_count': 200}
            return response
    async def guard():
        return None
    path = root / 'driver-attempt'
    assert asyncio.run(live.one_run(path, plan, job, payload, oracle, NativeFixture(), guard, 'ollama')) == 'completed'
    assert len(seen) == 15
    outcome = json.loads((path / 'outcome.json').read_text())
    assert all(s['questions'] == 12 for s in outcome['final_agents'].values())
