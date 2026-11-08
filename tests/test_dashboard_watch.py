import asyncio
import json
import runpy
from pathlib import Path

import pytest

from contagion.inference import MockProvider
from contagion.studies import StudyPlan, freeze_plan, run_plan


def test_watcher_merges_sealed_runs_preserves_evidence_and_fails_closed(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / 'scripts'))
    publish = runpy.run_path(str(root / 'scripts/watch_dashboard.py'))['publish']
    plan = StudyPlan(families=['catalog'], model='mock-v1', max_total_model_calls=50)
    freeze = tmp_path / 'freeze.json'
    freeze_plan(plan, freeze)
    paths = asyncio.run(run_plan(plan, MockProvider(), tmp_path / 'raw', freeze))
    output = tmp_path / 'public/research.json'
    assert publish([tmp_path / 'raw'], output, {}) == (True, 2)
    original = json.loads(output.read_text())
    original['limitations'].append('Existing approved evidence is preserved.')
    output.write_text(json.dumps(original))
    before = output.read_bytes()
    assert publish([tmp_path / 'raw'], output, {}) == (False, 2)
    assert output.read_bytes() == before
    assert publish([paths[0]], output, {}, include_text=True) == (True, 2)
    assert 'Existing approved evidence is preserved.' in json.loads(output.read_text())['limitations']
    assert list((output.parent / 'studies').glob('*.json'))
    # An active run with no seal is skipped; a corrupted sealed run blocks publication.
    active = tmp_path / 'active'
    active.mkdir()
    (active / 'manifest.json').write_text('{}')
    (active / 'config.snapshot.json').write_text('{"protocol_version":"2.4"}')
    assert publish([active], output, {}) == (False, 0)
    before = output.read_bytes()
    (paths[0] / 'outcome.json').write_text('{}')
    with pytest.raises(ValueError):
        publish([tmp_path / 'raw'], output, {})
    assert output.read_bytes() == before
