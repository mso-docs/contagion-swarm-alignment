import asyncio
import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    docket = importlib.import_module('multidomain_docket')
    live = importlib.import_module('multidomain_live')
    publication = importlib.import_module('multidomain_publication')
    monkeypatch.setattr(docket, 'ROOT', tmp_path)
    catalog = tmp_path / 'results/catalog'; docket.build(catalog)
    root = tmp_path / 'results/campaigns/current'
    plan = live.prepare(root, catalog, 'not-used-mock', 'a' * 64, rounds=5)
    _, payloads, oracles = live.validate(root)
    job = plan['jobs'][0]; path = root / 'runs/job-000/attempt-001'
    class Mock(live.Mock):
        identity = {'backend': 'mock', 'model': 'private-canary-token'}
        async def chat(self, messages):
            response = await super().chat(messages)
            data = json.loads(response.content)
            data['message'] = 'private-canary-token person@example.org'
            response.content = json.dumps(data)
            return response
    async def guard():
        return None
    assert asyncio.run(live.one_run(path, plan, job, payloads[job['task_id']], oracles[job['task_id']], Mock(), guard, 'mock')) == 'completed'
    return publication, root, path, {'CONTAGION_API_KEY': 'private-canary-token'}


def test_closed_numeric_summary_redacts_and_recomputes(sample):
    publication, root, path, env = sample
    rows = publication.summaries(root.parent, env)
    assert len(rows) == 1 and rows[0].calls == 15 and rows[0].final_questions == 50
    text = rows[0].model_dump_json()
    assert 'private-canary-token' not in text and 'Q001' not in text and 'explanation' not in text
    assert str(root) not in text and 'example.org' not in text
    assert rows[0].scientific_status == 'mock_only'
    # Stored outcome scores cannot override independently recomputed artifacts.
    data = json.loads((path / 'outcome.json').read_text())
    data['final_agents'] = {}; (path / 'outcome.json').write_text(json.dumps(data))
    from contagion.storage import seal
    seal(path)
    changed = publication.summaries(root.parent, env)
    assert changed[0].final_questions == rows[0].final_questions
    with pytest.raises(ValueError):
        publication.MultidomainRun(**{**rows[0].model_dump(), 'source_text': 'forbidden'})


def test_private_traces_bounded_redacted_and_no_request_or_oracle(sample):
    publication, root, path, env = sample
    detail = publication.private_detail(root.parent, publication.identifier(path), env)
    text = json.dumps(detail)
    assert 'private-canary-token' not in text and 'person@example.org' not in text
    assert 'inference_requested' not in text and 'oracle_hash' not in text
    assert detail['protocol'] == '5.0-multidomain-evidence' and detail['text_included']
    assert len(detail['traces']) <= 200 and all(len(e['content']) <= 4096 for e in detail['traces'])
    with pytest.raises(ValueError):
        publication.private_detail(root.parent, '../invalid', env)


def test_changed_seal_is_rejected_even_after_cache(sample):
    publication, root, path, env = sample
    publication.summaries(root.parent, env)
    (path / 'outcome.json').write_text('{}')
    with pytest.raises(ValueError, match='seal'):
        publication.summaries(root.parent, env)


def test_followup_export_accepts_optional_numeric_extension(sample, tmp_path):
    publication, root, _, env = sample
    followup = importlib.import_module('followup_publication')
    output = tmp_path / 'followups.json'
    result = followup.export(root.parent, output, env)
    assert len(result.multidomain) == 1 and not result.runs
    assert followup.validate(output, env).multidomain[0].protocol == '5.0-multidomain-evidence'
    old = result.model_dump(); old.pop('multidomain')
    assert followup.Snapshot.model_validate(old).multidomain == []


def test_incomplete_endpoints_cannot_be_published_as_zero(sample):
    publication, root, _, env = sample
    row = publication.summaries(root.parent, env)[0]
    with pytest.raises(ValueError, match='unknown'):
        publication.MultidomainRun(**{**row.model_dump(), 'status': 'failed'})
