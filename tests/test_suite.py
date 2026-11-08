import json
from pathlib import Path

from contagion import suite


def test_secondary_suite_freezes_full_schedule_and_budgets(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    (tmp_path/'results').mkdir()
    plan=suite.prepare('results/suite')
    assert plan['worker_label']=='secondary'
    assert plan['planned_agent_calls']==80680
    assert plan['planned_calls']==80744
    assert len(plan['jobs'])==366
    assert plan['planned_calls']<plan['max_physical_calls']
    for job in plan['jobs']:
        frozen=json.loads(Path(job['freeze']).read_text())
        assert frozen['freeze_hash']==job['freeze_hash']
        assert frozen['plan']['model'] in dict(suite.MODELS)
    assert {5,10,20,40,80,128}==set(plan['sizes'])


def test_suite_runs_a_frozen_mock_block_and_records_completion(tmp_path,monkeypatch):
    import asyncio
    from contagion.config import digest
    from contagion.inference import MockProvider
    monkeypatch.chdir(tmp_path);(tmp_path/'results').mkdir()
    root=Path('results/suite');prepared=suite.prepare(root)
    prepared['jobs']=prepared['jobs'][:1];prepared['planned_calls']=prepared['jobs'][0]['calls']
    prepared['suite_hash']=digest({k:v for k,v in prepared.items() if k!='suite_hash'})
    (root/'suite.json').write_text(json.dumps(prepared))
    class Provider(MockProvider):
        def __init__(self,url,**kwargs):
            assert url=='http://127.0.0.1:11434'
            self.identity={'backend':'mock'}
        async def discover(self):return [{'name':n,'digest':d} for n,d in suite.MODELS]
        async def close(self):pass
    monkeypatch.setattr(suite,'HTTPProvider',Provider)
    publications=[];monkeypatch.setattr(suite,'publish',lambda path:publications.append(path))
    outcome=asyncio.run(suite.run(root))
    assert outcome['status']=='completed' and outcome['completed_runs']==6
    assert outcome['failed_runs']==0 and publications
    state=json.loads((root/'state.json').read_text())
    assert state['job_cursor']==1 and len(state['seen_runs'])==6
    assert (root/'suite.events.jsonl').is_file()


def test_deadline_priority_reorders_without_duplicating_studies(tmp_path,monkeypatch):
    from contagion.config import digest
    monkeypatch.chdir(tmp_path);(tmp_path/'results').mkdir()
    prepared=suite.prepare('results/deadline','deadline')
    assert prepared['planned_agent_calls']==80680
    assert prepared['planned_calls']==80744
    assert len(prepared['jobs'])==366
    plans=[json.loads(Path(j['plan']).read_text()) for j in prepared['jobs']]
    assert len({digest(p) for p in plans})==len(plans)
    first_scale=next(i for i,j in enumerate(prepared['jobs']) if j['stage']=='scaling_development')
    prefix=prepared['jobs'][:first_scale]
    assert {j['model'] for j in prefix if j['stage']=='submission_rq1'}==set(dict(suite.MODELS))
    assert all(p['protocol_version']=='2.6' for p in plans)


def test_resource_pause_policy_is_conservative_and_does_not_invent_readings():
    from contagion.resources import pause_reason
    good={'available_ram_gib':50,'temperatures_c':[44,55],'gpu':[{'temperature_c':42}]}
    assert pause_reason(good) is None
    assert pause_reason({**good,'gpu':[{'temperature_c':86}]})=='gpu_temperature_pause'
    assert pause_reason({**good,'available_ram_gib':3})=='low_available_ram'
