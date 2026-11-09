import asyncio
import importlib
import json
from pathlib import Path
import pytest


@pytest.mark.parametrize('module_name,protocol', [
    ('secondary_review_v35','3.5-repository-output-budget'),
    ('secondary_review_v38','3.8-repository-bounded-output'),
])
def test_secondary_output_cohort_publishes_its_actual_budget(tmp_path, monkeypatch, module_name, protocol):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    runner = importlib.import_module(module_name)
    publication = importlib.import_module('repository_publication')
    from run_repository_study import RepoMock
    row = {'id': 'a' * 20, 'planned_rounds': 3, 'input_length': 'long', 'characters': 5000,
           'repository': 'fixture/project', 'dataset_revision': 'b' * 40}
    source = tmp_path / 'runs'
    asyncio.run(runner.run_case(row, {'code_diff': 'private-source-canary'},
        {'freeze_hash': 'c' * 64}, {'plan_hash': 'd' * 64}, RepoMock(), source, 'ring', 'none'))
    output = tmp_path / 'public.json'
    snapshot = publication.export_repository_runs(source, output, {})
    assert len(snapshot.runs) == 1
    item = snapshot.runs[0]
    assert item.protocol == protocol and item.output_token_limit == 3072
    assert item.memory_policy == 'full_history' and 'private-source-canary' not in output.read_text()


def test_private_progress_includes_both_new_queue_kinds(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    service = importlib.import_module('serve_dashboard')
    base = tmp_path / 'results/campaigns'
    for name, statefile in [('secondary', 'secondary-bounded-state.json'),
                            ('primary', 'primary-output-state.json'),
                            ('domains', 'multidomain-live-state.json')]:
        root = base / name; root.mkdir(parents=True)
        (root / statefile).write_text(json.dumps({'status': 'waiting', 'planned_runs': 24,
            'planned_calls': 940, 'completed_runs': 0, 'physical_calls': 0, 'failed_runs': 0}))
    result = service.private_campaigns(base)
    assert {r['kind'] for r in result} == {'secondary_recovery_queue', 'primary_output_queue', 'multidomain_queue'}
    assert all(r['physical_calls'] == 0 and r['status'] == 'waiting' for r in result)


def test_completed_continuation_supersedes_historical_stopped_progress(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    service=importlib.import_module('serve_dashboard');base=tmp_path/'results/campaigns'
    for name,status,stamp in [('older','stopped','2026-11-08T10:00:00Z'),('newer','completed','2026-11-08T20:00:00Z')]:
        root=base/name;root.mkdir(parents=True)
        (root/'secondary-isolated-state.json').write_text(json.dumps({'status':status,'backend':'ollama',
            'updated_utc':stamp,'planned_runs':21,'planned_calls':895,'completed_runs':21 if status=='completed' else 3}))
    root=base/'mock';root.mkdir()
    (root/'secondary-isolated-state.json').write_text(json.dumps({'status':'stopped','backend':'mock','updated_utc':'2099-01-01T00:00:00Z'}))
    result=service.private_campaigns(base)
    assert len(result)==1 and result[0]['status']=='completed'
