import asyncio
from pathlib import Path
import runpy

import pytest

from contagion.inference import MockProvider
from contagion.studies import StudyPlan, freeze_plan, run_plan

ROOT = Path(__file__).resolve().parents[1]


def monitor(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    return runpy.run_path(str(ROOT / 'scripts/experiment_progress.py'))


def test_estimates_distinguish_work_from_paused_finish(monkeypatch):
    api = monitor(monkeypatch)
    row = {'status': 'stopped', 'recorded_run_seconds': 100, 'measured_calls': 20,
           'physical_calls': 25, 'planned_calls': 45}
    result = api['estimates'](row)
    assert result['calls_per_minute'] == 12
    assert result['estimated_remaining_work_seconds'] == 100
    assert result['estimated_total_work_seconds'] == 200
    assert result['estimated_finish_utc'] is None
    from datetime import datetime, timezone
    assert api['estimates']({**row, 'status': 'running', 'updated_utc': datetime.now(timezone.utc).isoformat()})['estimated_finish_utc']
    assert api['estimates']({**row, 'status': 'running', 'updated_utc': '2020-01-01T00:00:00+00:00'})['estimated_finish_utc'] is None
    assert api['estimates']({'status': 'running'})['estimated_remaining_work_seconds'] is None
    assert api['estimates']({**row, 'physical_calls': 100})['estimated_remaining_work_seconds'] == 0


def test_local_progress_checks_integrity_and_deduplicates_sources(tmp_path, monkeypatch):
    api = monitor(monkeypatch)
    plan = StudyPlan(model='mock-v1', families=['catalog'], max_total_model_calls=50)
    freeze = tmp_path / 'freeze.json'
    freeze_plan(plan, freeze)
    paths = asyncio.run(run_plan(plan, MockProvider(), tmp_path / 'raw', freeze))
    data = api['local_studies']([tmp_path / 'raw', tmp_path / 'raw'])
    assert data['completed_runs'] == 2
    assert data['physical_calls'] == 0  # Mock backend makes no HTTP attempts.
    assert data['measured_calls'] == 50
    assert data['recorded_run_seconds'] > 0
    active = tmp_path / 'raw/unfinished'
    active.mkdir()
    (active / 'config.snapshot.json').write_text('{}')
    assert api['local_studies']([tmp_path / 'raw'])['unsealed_runs'] == 1
    (paths[0] / 'events.jsonl').write_text('corruption')
    with pytest.raises(ValueError):
        api['local_studies']([tmp_path / 'raw'])


def test_render_never_includes_paths_or_model_text(monkeypatch, capsys):
    api = monitor(monkeypatch)
    api['render']('Secondary', {'status': 'stopped', 'private_path': 'hidden', 'model': 'hidden'})
    text = capsys.readouterr().out
    assert 'hidden' not in text
    assert 'N/A' in text and 'unknown' in text


def test_pages_build_rejects_private_queue_progress(tmp_path, monkeypatch):
    import json
    from contagion.publication import export_snapshot
    from contagion.research_publication import ResearchSnapshot, SuiteProgress
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    build = runpy.run_path(str(ROOT / 'scripts/build_dashboard.py'))['build']
    source = tmp_path / 'dashboard'
    (source / 'data').mkdir(parents=True)
    export_snapshot([ROOT / 'tests/fixtures/mock_run'], source / 'data/results.json', env={})
    progress = SuiteProgress(status='stopped', planned_calls=100, physical_calls=5,
                             completed_runs=1, failed_runs=0, job_cursor=0,
                             planned_jobs=2, elapsed_seconds=3)
    snapshot = ResearchSnapshot(generated_utc='2026-11-08T00:00:00+00:00', limitations=[], suite=progress)
    (source / 'data/research.json').write_text(snapshot.model_dump_json())
    with pytest.raises(ValueError, match='Private operational telemetry'):
        build(source, tmp_path / 'public')
    assert not (tmp_path / 'public').exists()
