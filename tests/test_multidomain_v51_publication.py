import asyncio
import importlib
import json
from pathlib import Path

import pytest


def test_separate_coverage_protocol_numeric_export_and_private_detail(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    docket = importlib.import_module('multidomain_docket')
    live = importlib.import_module('multidomain_live_v51')
    publication = importlib.import_module('multidomain_publication_v51')
    monkeypatch.setattr(docket, 'ROOT', tmp_path)
    catalog = tmp_path / 'results/catalog'; docket.build(catalog)
    root = tmp_path / 'results/campaigns/new-coverage'
    plan = live.prepare(root, catalog, 'fixture-model', 'a' * 64, rounds=5)
    _, payloads, oracles = live.validate(root)
    job = plan['jobs'][0]; task = job['task_id']
    class Mock(live.Mock):
        identity = {'backend': 'mock', 'model': 'fixture-model'}
    async def guard():
        return None
    path = root / 'runs/job-000/attempt-001'
    assert asyncio.run(live.one_run(path, plan, job, payloads[task], oracles[task], Mock(), guard, 'mock')) == 'completed'
    rows = publication.summaries(root.parent)
    assert len(rows) == 1 and rows[0].protocol == '5.1-multidomain-question-coverage'
    assert rows[0].final_questions == 50 and rows[0].scientific_status == 'mock_only'
    text = rows[0].model_dump_json()
    assert 'Q001' not in text and str(root) not in text and task not in text
    detail = publication.private_detail(root.parent, rows[0].id)
    assert detail['protocol'] == rows[0].protocol and detail['text_included'] is True
    assert not any(e['event_type'] == 'inference_requested' for e in detail['traces'])
    other = root.parent / 'other/runs/job-000/attempt-001'; other.mkdir(parents=True)
    (other / 'manifest.json').write_text(json.dumps({'protocol_version': '5.0-multidomain-evidence'}))
    assert len(publication.summaries(root.parent)) == 1
    (path / 'outcome.json').write_text('{}')
    with pytest.raises(ValueError, match='seal'):
        publication.summaries(root.parent)
