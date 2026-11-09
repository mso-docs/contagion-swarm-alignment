import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]


def api(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return runpy.run_path(str(ROOT/'scripts/all_task_figures.py'))


def row(ident,**changes):
    return {'id':ident,'model':'test-model','backend':'ollama','protocol':'4.0-confirmatory','task_family':'catalog','status':'completed','calls':5,'runtime':1,'rounds':None,**changes}


def write_data(root):
    root.mkdir(parents=True)
    datasets={'results':{'runs':[row('legacy',protocol_version='1.0',completed_calls=5,duration_seconds=1)]},
        'research':{'studies':[row('study',task_family='record')]},
        'repositories':{'runs':[row('repo',task_family='issue_diagnosis',backend='mock',memory_policy='full_history')]},
        'followups':{'runs':[row('confirmatory',task_family='patch')],
                     'multidomain':[row('multidomain',domain='science',protocol='5.1-multidomain-evidence',runtime_seconds=2)],
                     'diversity':[row('diversity',domain='defensive_cybersecurity',backend='mock',protocol='6.0-model-topology-calibration',runtime_seconds=3)]}}
    for name,data in datasets.items():(root/f'{name}.json').write_text(json.dumps(data))


def test_all_six_sources_keep_protocols_and_missing_horizons(tmp_path,monkeypatch):
    module=api(monkeypatch);write_data(tmp_path/'data')
    rows,hashes=module['inventory'](tmp_path/'data')
    assert len(rows)==6 and len(hashes)==4
    assert {r['source'] for r in rows}=={'legacy','study','repository','confirmatory','multidomain','diversity'}
    assert {r['task'] for r in rows}=={'catalog','record','issue_diagnosis','patch','science','defensive_cybersecurity'}
    assert all(r['rounds'] is None for r in rows)
    assert next(r for r in rows if r['source']=='repository')['memory_policy']=='full_history'
    assert next(r for r in rows if r['source']=='diversity')['protocol']=='6.0-model-topology-calibration'
    assert next(r for r in rows if r['source']=='multidomain')['runtime']==2
    counts=module['coverage_counts'](rows)
    assert counts['issue_diagnosis']=={'live':0,'mock':1}
    assert counts['defensive_cybersecurity']=={'live':0,'mock':1}


def test_frozen_dashboard_overrides_live_cache_and_invalid_freeze_stops(tmp_path,monkeypatch):
    module=api(monkeypatch);scope=module['inventory'].__globals__
    monkeypatch.setitem(scope,'ROOT',tmp_path)
    write_data(tmp_path/'dashboard/data');write_data(tmp_path/'results/dashboard-live/data')
    assert module['default_data_root']()==tmp_path/'results/dashboard-live/data'
    freeze=tmp_path/'dashboard/data/submission-freeze.json';freeze.write_text('{}')
    assert module['default_data_root']()==tmp_path/'dashboard/data'
    checked=[]
    monkeypatch.setitem(sys.modules,'freeze_dashboard',SimpleNamespace(validate=lambda path:checked.append(path)))
    rows,_=module['inventory']();assert len(rows)==6 and checked==[freeze]
    def fail(path):raise ValueError('changed after freeze')
    monkeypatch.setitem(sys.modules,'freeze_dashboard',SimpleNamespace(validate=fail))
    with pytest.raises(ValueError,match='changed after freeze'):module['inventory']()


def test_duplicate_rows_fail_instead_of_inflating_counts(tmp_path,monkeypatch):
    module=api(monkeypatch);write_data(tmp_path/'data')
    path=tmp_path/'data/followups.json';data=json.loads(path.read_text());data['multidomain']*=2;path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='Duplicate'):module['inventory'](tmp_path/'data')
