"""A report checkpoint must not absorb a later batch by accident."""
import hashlib
import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    return importlib.import_module('large_batch_reports')


def test_report_cutoff_binds_receipt_seals_and_keeps_later_runs_out(module,tmp_path):
    plan={'plan_hash':'a'*64,'jobs':[{'batch':1},{'batch':2}]};seals={}
    for index,ended in [(0,'2026-11-08T08:00:00+00:00'),(1,'2026-11-08T09:00:00+00:00')]:
        root=tmp_path/f'job-{index:03}'/'attempt';root.mkdir(parents=True)
        (root/'checksum.sha256').write_text(str(index));(root/'manifest.json').write_text(json.dumps({'status':'completed','ended_utc':ended}))
        seals[f'job-{index:03}']=hashlib.sha256((root/'checksum.sha256').read_bytes()).hexdigest()
    receipt={'batch':1,'plan_hash':plan['plan_hash'],'runs':1,'operational_gate_passed':True,'seals':{'job-000':seals['job-000']}}
    assert module.receipt_cutoff(plan,receipt,tmp_path)=='2026-11-08T08:00:00+00:00'
    receipt['seals']['job-001']=seals['job-001']
    with pytest.raises(ValueError,match='receipt'):module.receipt_cutoff(plan,receipt,tmp_path)


def test_zero_signal_report_has_real_denominators_and_unknown_quality(module,tmp_path):
    data={'analysis_scope':'completed_registered_batches_descriptive','rows':[{
        'phase':'evaluation','dataset':'fixture/source','task_kind':'issue_diagnosis','defense':'plain',
        'intervention':'none','any_round_downstream_violation':False,'final_downstream_any_violation':False,
        'case':'a'*20,'runtime_seconds':2.0}]}
    result=module.plots(data,tmp_path/'figures')
    assert len(result['files'])==9 and result['semantic_quality']=='not_validated'
    assert '0/1' in (tmp_path/'figures/boundary_signals.svg').read_text()
