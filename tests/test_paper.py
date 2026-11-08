import copy
import json
from pathlib import Path
import runpy

import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_paper_distinguishes_intermediate_and_final_endpoints(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    build=runpy.run_path(str(ROOT/'scripts/build_paper.py'))
    data=json.loads((ROOT/'report/data/compact_evidence.json').read_text())
    build['validate_draft_evidence'](data)
    table=build['generated_table'](data)
    assert 'Any-round' in table and 'Final' in table
    assert 'Patch & Injected & 6 & 6 & 0' in table
    changed=copy.deepcopy(data)
    next(r for r in changed['runs'] if r['status']=='completed')['final_any_violation']=True
    with pytest.raises(ValueError,match='transient/final'):build['validate_draft_evidence'](changed)


def test_long_horizon_registry_uses_same_inputs_across_round_budgets(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    queue=runpy.run_path(str(ROOT/'scripts/run_long_horizon.py'))
    # Exercise design construction without accessing a live inference service.
    queue['prepare'].__globals__['validate_readiness']=lambda p:{'readiness_hash':'fixture'}
    from repository_benchmark import sha
    tasks=[{'id':str(i)*20,'input_length':'long','planned_rounds':15,'diff_sha256':str(i)*64} for i in range(3)]
    data={'tasks':tasks};data['catalog_hash']=sha(json.dumps(data,sort_keys=True).encode())
    (tmp_path/'catalog.json').write_text(json.dumps(data))
    initial={'tasks':tasks};initial['freeze_hash']=sha(json.dumps(initial,sort_keys=True).encode())
    (tmp_path/'selection.json').write_text(json.dumps(initial))
    plan=queue['prepare'](tmp_path/'queue',tmp_path/'catalog.json',tmp_path/'selection.json',tmp_path/'proof.json')
    assert plan['planned_runs']==36 and plan['planned_calls']==1560
    freezes=[json.loads((tmp_path/'queue'/f'freeze-h{n:02}.json').read_text()) for n in [3,8,15]]
    assert all([r['id'] for r in f['tasks']]==[r['id'] for r in freezes[0]['tasks']] for f in freezes)
    assert len({f['freeze_hash'] for f in freezes})==3
    assert tasks[0]['id'] not in [r['id'] for r in freezes[0]['tasks']]


def test_temporal_figure_uses_patch_runs_only_not_other_task_denominators(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    analysis=runpy.run_path(str(ROOT/'scripts/paper_analysis.py'))
    data=json.loads((ROOT/'report/data/compact_evidence.json').read_text())
    series=analysis['temporal_patch_series'](data)
    assert sum(values[1]*8 for values in series.values())==17
    assert all(values[0]==0 and values[-1]==0 for values in series.values())
