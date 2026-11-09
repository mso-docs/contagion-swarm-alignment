import asyncio
import importlib
import json
from pathlib import Path

import pytest

from contagion.storage import seal


@pytest.fixture
def setup(tmp_path, monkeypatch):
    repo = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(repo / 'scripts'))
    docket = importlib.import_module('multidomain_docket')
    calibration = importlib.import_module('diversity_calibration')
    publication = importlib.import_module('diversity_publication')
    monkeypatch.setattr(docket, 'ROOT', tmp_path)
    source = tmp_path / 'results/campaigns'; catalog = tmp_path / 'results/catalog'; docket.build(catalog)
    pins = json.loads((repo / 'configs/diversity_models.example.json').read_text())
    pins['models'][0]['model'] = 'qwen-private-fixture-value'
    pins['models'][1]['family_label'] = 'LFM-private-fixture-value'
    pin_file = tmp_path / 'pins.json'; pin_file.write_text(json.dumps(pins))
    root = source / 'calibration'
    plan = calibration.prepare(root, catalog, pin_file, 'humanities-archive_chronology-0', rotations=5, roles=True)
    _, payloads, oracles = calibration.validate(root)
    async def guard():
        return None
    def create(index, provider=None):
        job = plan['jobs'][index]
        path = root / 'runs' / f'job-{index:03}' / 'attempt-001'
        asyncio.run(calibration.one_run(path, plan, job, payloads[job['task_id']], oracles[job['task_id']],
                                       provider or calibration.Mock(), guard, 'mock'))
        return path
    return publication, calibration, source, root, plan, create


def test_heterogeneous_roles_and_each_topology_preserved(setup):
    pub, core, source, root, plan, create = setup
    indexes = [i for i, j in enumerate(plan['jobs']) if j['phase'] == 'role_calibration'
               and j['rotation'] == 2 and j['intervention'] == 'clean']
    for index in indexes:
        create(index)
    rows = pub.summaries(source)
    assert len(rows) == 3 and {r.topology for r in rows} == {'ring', 'star', 'complete'}
    for row in rows:
        assert row.protocol == '6.0-model-topology-calibration' and row.composition == 'heterogeneous'
        assert row.rotation == 2 and set(row.agent_roles.values()) == set(core.ROLES)
        assert row.graph == core.study_adjacency(row.topology, 5)
        assert {m.model_group for m in row.agent_models.values()} == {'qwen', 'lfm', 'nemotron'}
        assert row.final_questions == 50 and row.scientific_status == 'mock_only' and row.heldout_evidence is False
        assert sum(a.questions for a in row.agents.values()) == row.final_questions
        assert row.source_plan_hash == plan['plan_hash']


def test_summary_recomputes_artifacts_instead_of_saved_outcome(setup):
    pub, core, source, root, plan, create = setup
    path = create(18)
    before = pub.summaries(source)[0]
    (path / 'outcome.json').write_text('{"final_agents":{"invented":"not evidence"}}'); seal(path)
    after = pub.summaries(source)[0]
    assert after.final_correct == before.final_correct and after.final_questions == before.final_questions


def test_redaction_private_model_assignments_and_no_request_or_oracle_payload(setup):
    pub, core, source, root, plan, create = setup
    class Text(core.Mock):
        async def chat(self, messages):
            response = await super().chat(messages)
            content = json.loads(response.content); content['message'] = 'private-fixture-value'
            response.content = json.dumps(content); return response
    path = create(18, Text())
    env = {'CONTAGION_API_KEY': 'private-fixture-value'}
    row = pub.summaries(source, env)[0]
    assert 'private-fixture-value' not in row.model_dump_json()
    assert plan['jobs'][18]['task_id'] not in row.model_dump_json()
    detail = pub.private_detail(source, row.id, env)
    serialized = json.dumps(detail)
    assert 'private-fixture-value' not in serialized
    assert all(e['event_type'] != 'inference_requested' and 'metadata' not in e for e in detail['traces'])
    assert all(len(e['content']) <= 4096 for e in detail['traces']) and len(detail['traces']) <= 200
    assert 'oracle_hash' not in serialized and 'payload_hash' not in serialized and 'required_question_ids' not in serialized
    assert detail['graph'] == core.study_adjacency('ring', 5)
    assert set(detail['agent_models']) == {f'agent_{i}' for i in range(5)}
    assert all('assigned_model' in e and 'assigned_role' in e for e in detail['traces'] if e.get('agent_id'))


def test_incomplete_endpoints_are_null_and_long_output_is_bounded(setup):
    pub, core, source, root, plan, create = setup
    class Malformed(core.Mock):
        async def chat(self, messages):
            response = await super().chat(messages); response.content = 'ordinary words repeated ' * 400; return response
    path = create(0, Malformed())
    row = pub.summaries(source)[0]
    assert row.status == 'failed' and row.retained_failed_attempts == 1 and row.parse_failures == 1
    assert row.final_questions is None and row.final_correct is None and row.downstream_final_marker_adoptions is None
    assert all(all(v is None for v in a.model_dump().values()) for a in row.agents.values())
    detail = pub.private_detail(source, row.id)
    response = next(e for e in detail['traces'] if e['event_type'] == 'inference_response')
    assert response['content_truncated'] and len(response['content']) == 4096


def test_changed_seal_or_graph_blocks_export(setup):
    pub, core, source, root, plan, create = setup
    path = create(18)
    pub.summaries(source)
    manifest = json.loads((path / 'manifest.json').read_text()); manifest['graph']['agent_0'] = []
    (path / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='seal'):
        pub.summaries(source)
    seal(path)
    with pytest.raises(ValueError, match='graph'):
        pub.summaries(source)


def test_public_schema_rejects_private_fields_and_unknown_roles(setup):
    pub, core, source, root, plan, create = setup
    create(18)
    row = pub.summaries(source)[0]
    with pytest.raises(ValueError):
        pub.Row.model_validate({**row.model_dump(), 'request_histories': []})
    data = row.model_dump(); data['agent_roles']['agent_0'] = 'unrestricted_operator'
    with pytest.raises(ValueError):
        pub.Row.model_validate(data)
