import importlib
import json
from pathlib import Path


def test_queued_large_campaign_has_totals_without_inventing_finish_time(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    module=importlib.import_module('experiment_progress');monkeypatch.setattr(module,'ROOT',tmp_path)
    root=tmp_path/'results/campaigns/large';root.mkdir(parents=True)
    (root/'primary-large-plan.json').write_text(json.dumps({'planned_runs':264,'planned_calls':19320,'max_wall_seconds':259200}))
    result=module.benchmark_campaign_status(root)
    assert result['status']=='waiting' and result['planned_calls']==19320 and result['planned_runs']==264
    assert result['estimated_finish_utc'] is None and result['estimated_remaining_work_seconds'] is None
