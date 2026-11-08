from pathlib import Path
import runpy


def service(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / 'scripts'))
    return runpy.run_path(str(root / 'scripts/serve_dashboard.py'))


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
