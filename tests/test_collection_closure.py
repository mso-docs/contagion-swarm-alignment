import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def closer(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    return importlib.import_module('close_collection').close


def test_closure_preserves_terminal_state_and_existing_stop(closer, tmp_path):
    base = tmp_path / 'results/campaigns'; allocation = base / 'finished'; allocation.mkdir(parents=True)
    state = allocation / 'state.json'; original = json.dumps({'status': 'completed', 'completed_runs': 3})
    state.write_text(original)
    first = closer(base, tmp_path / 'results/first.private.json', project=tmp_path)
    stop = (allocation / 'STOP').read_bytes()
    second = closer(base, tmp_path / 'results/second.private.json', project=tmp_path)
    assert first['both_controller_leases_available'] and first['allocations'][0]['stop_created']
    assert not second['allocations'][0]['stop_created'] and state.read_text() == original
    assert (allocation / 'STOP').read_bytes() == stop


def test_closure_rejects_active_allocation_and_external_directory(closer, tmp_path):
    base = tmp_path / 'results/campaigns'; allocation = base / 'active'; allocation.mkdir(parents=True)
    (allocation / 'state.json').write_text('{"status":"running"}')
    with pytest.raises(ValueError, match='terminal'):
        closer(base, tmp_path / 'results/receipt.private.json', project=tmp_path)
    assert not (allocation / 'STOP').exists()
    with pytest.raises(ValueError, match='project'):
        closer(tmp_path, tmp_path / 'results/receipt.private.json', project=tmp_path)
