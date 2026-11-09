from pathlib import Path
import runpy


def service(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / 'scripts'))
    return runpy.run_path(str(root / 'scripts/serve_dashboard.py'))


def test_frozen_submission_prevents_collector_startup(monkeypatch,tmp_path):
    import pytest
    import sys
    api=service(monkeypatch);main=api['main']
    path=tmp_path/'dashboard/data/submission-freeze.json';path.parent.mkdir(parents=True);path.write_text('{}')
    monkeypatch.setitem(main.__globals__,'ROOT',tmp_path)
    monkeypatch.setitem(main.__globals__,'private_values',lambda *args:pytest.fail('Frozen startup must not read operator settings'))
    monkeypatch.setattr(sys,'argv',['serve_dashboard.py','--sync-secondary'])
    with pytest.raises(SystemExit) as exc:main()
    assert exc.value.code==2


def test_local_service_failure_is_visible_and_does_not_echo_private_values(monkeypatch, tmp_path, capsys):
    api = service(monkeypatch)
    refresh = api['refresh']
    def fail(*args, **kwargs):
        raise ValueError('private content must never be echoed')
    monkeypatch.setitem(refresh.__globals__, 'publish', fail)
    output = tmp_path / 'research.json'
    output.write_text('previous validated snapshot')
    state = {'studies': 7}
    refresh([], output, {}, state)
    assert output.read_text() == 'previous validated snapshot'
    assert state['status'] == 'blocked' and state['studies'] == 7
    assert 'private content' not in capsys.readouterr().out


def test_local_service_never_serves_raw_paths_or_temporary_exports(monkeypatch, tmp_path):
    api = service(monkeypatch)
    handler = api['handler_type'](tmp_path, {})
    for path in ['/.env', '/data/research.tmp', '/results/events.jsonl', '/../../.env', '/%2e%2e/.env']:
        request = handler.__new__(handler)
        request.path = path
        errors = []
        request.send_error = lambda code: errors.append(code)
        request.do_GET()
        assert errors == [404]


def test_cpu_capture_collector_fetches_completed_artifacts_without_manual_import(monkeypatch):
    api=service(monkeypatch);calls=[]
    def remote(server,action,env_file):
        calls.append((server,action))
        return [{'phase':'capture_fetched' if len(calls)<=2 else 'trained_captures_synced'}]
    assert api['sync_secondary_neural'](Path('private-config'),remote)==2
    assert calls==[('secondary','trained-fetch')]*3
    calls.clear()
    assert api['sync_secondary_neural'](Path('private-config'),lambda *args:[{'phase':'capture_fetched'}])==8


def test_private_progress_retains_completion_and_excludes_private_fields(monkeypatch,tmp_path):
    import json
    api=service(monkeypatch);root=tmp_path/'campaigns';active=root/'active';active.mkdir(parents=True)
    plan={'planned_calls':5400,'jobs':[{'plan':{'families':['catalog'],'case_indices':[1],'seeds':[11001],
        'topologies':['ring'],'interventions':['none','benign_override']}}]}
    (active/'campaign.json').write_text(json.dumps(plan))
    state={'status':'cooling','completed_runs':1,'physical_calls':31,'failed_runs':0,'private_host':'must-not-leave-reader','run_root':'private path'}
    (active/'state.json').write_text(json.dumps(state))
    rows=api['private_campaigns'](root)
    assert rows==[{'kind':'swarm_campaign','status':'cooling','planned_runs':2,'planned_calls':5400,'completed_runs':1,'physical_calls':31,'failed_runs':0}]
    assert 'private' not in json.dumps(rows)
    (active/'state.json').write_text(json.dumps({**state,'status':'completed'}))
    completed=api['private_campaigns'](root)
    assert completed==[{**rows[0],'status':'completed'}]
    assert 'private' not in json.dumps(completed)
    (active/'state.json').write_text(json.dumps({**state,'status':'stopped'}))
    assert api['private_campaigns'](root)[0]['status']=='stopped'


def test_git_snapshot_rewind_cannot_rewind_live_data(monkeypatch,tmp_path):
    import asyncio
    import json
    from contagion.inference import MockProvider
    from contagion.studies import StudyPlan,freeze_plan,run_plan
    from contagion.research_publication import make_research_snapshot
    api=service(monkeypatch);tracked=tmp_path/'tracked';tracked.mkdir();live=tmp_path/'live'
    plan=StudyPlan(families=['catalog'],model='mock-v1',max_total_model_calls=50)
    freeze=tmp_path/'freeze.json';freeze_plan(plan,freeze)
    asyncio.run(run_plan(plan,MockProvider(),tmp_path/'raw',freeze))
    snapshot=make_research_snapshot([tmp_path/'raw'],env={})
    (tracked/'research.json').write_text(snapshot.model_dump_json())
    api['seed_live_data'](tracked,live,{})
    assert len(json.loads((live/'research.json').read_text())['studies'])==2
    # Simulate pre-commit restoring an earlier tracked snapshot during collection.
    (tracked/'research.json').write_text(snapshot.model_copy(update={'studies':[]}).model_dump_json())
    api['seed_live_data'](tracked,live,{})
    assert len(json.loads((live/'research.json').read_text())['studies'])==2
    assert json.loads((tracked/'research.json').read_text())['studies']==[]
    handler=api['handler_type'](tracked,{},live);request=handler.__new__(handler)
    assert request.translate_path('/data/research.json')==str(live/'research.json')


def test_collector_status_rejects_nonlocal_host_headers(monkeypatch,tmp_path):
    from types import SimpleNamespace
    api=service(monkeypatch);handler=api['handler_type'](tmp_path,{})
    for host in ['untrusted.invalid:8765','localhost:invalid','localhost:9999']:
        request=handler.__new__(handler);request.path='/__local_status';request.headers={'Host':host}
        request.server=SimpleNamespace(server_port=8765);errors=[];request.send_error=lambda code:errors.append(code)
        request.do_GET();assert errors==[403]


def test_explicit_export_preserves_live_cache_and_validates_reviewed_copy(monkeypatch,tmp_path):
    from contagion.research_publication import ResearchSnapshot
    api=service(monkeypatch)
    module=runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/export_live_dashboard.py'))
    source=tmp_path/'live';source.mkdir();destination=tmp_path/'tracked'
    snapshot=ResearchSnapshot(generated_utc='2026-11-08T00:00:00+00:00',limitations=[])
    (source/'research.json').write_text(snapshot.model_dump_json());before=(source/'research.json').read_bytes()
    assert module['export'](source,destination,{})==1
    assert (source/'research.json').read_bytes()==before==(destination/'research.json').read_bytes()
    api['validate_live_data'](destination,{})
