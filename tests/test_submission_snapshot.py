import importlib
import json
from pathlib import Path

import pytest

from contagion.storage import seal,write_json


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    return importlib.import_module('submission_snapshot')


def fixture(root,ended='2020-11-08T06:00:00+00:00',status='completed',protocol='4.0-confirmatory'):
    root.mkdir(parents=True)
    manifest={'protocol_version':protocol,'model_identity':{'backend':'mock','model':'fixture','worker_label':'local'},'source_hash':'a'*64,'freeze_hash':'b'*64,
              'status':status,'completed_model_calls':25,'duration_seconds':10.,'ended_utc':ended}
    config={'job':{'family':'patch','source':'agent_0','context':'not_applicable','topology':'ring','executor':'deny','condition':'none','seed':1},'case':{'case_id':root.name},'phase':'confirmatory'}
    outcome={'final_downstream_violation_rate':0.,'any_round_violation':False,'task_success_rate':1.}
    write_json(root/'manifest.json',manifest);write_json(root/'config.snapshot.json',config);write_json(root/'outcome.json',outcome);(root/'events.jsonl').write_text('')
    seal(root);return root


def test_explicit_cutoff_completed_seals_only_and_immutable_output(module,tmp_path):
    source=tmp_path/'raw';fixture(source/'eligible');fixture(source/'late','2020-11-08T08:00:00+00:00');fixture(source/'failed',status='failed');fixture(source/'other',protocol='fixture-unsupported')
    pending=source/'unsealed';pending.mkdir();(pending/'manifest.json').write_text('{"protocol_version":"4.0-confirmatory"}')
    out=tmp_path/'frozen';result=module.prepare([source],'2020-11-08T07:00:00Z',out)
    assert len(result.rows)==1 and result.excluded_after_cutoff==1 and result.excluded_incomplete==1 and result.excluded_unsealed==1 and result.excluded_unsupported_protocol==1
    assert str(source) not in (out/'public.json').read_text() and 'fixture' not in (out/'public.json').read_text()
    assert result.rows[0].quality_precision is None and result.human_validation=='pending'
    with pytest.raises(ValueError,match='must be new'):module.prepare([source],'2020-11-08T07:00:00Z',out)
    assert module.digest({k:v for k,v in result.model_dump().items() if k!='snapshot_hash'})==result.snapshot_hash


def test_invalid_seals_and_non_utc_rejected(module,tmp_path):
    source=tmp_path/'raw';root=fixture(source/'eligible');(root/'outcome.json').write_text('{}')
    with pytest.raises(ValueError,match='seal mismatch'):module.prepare([source],'2020-11-08T07:00:00Z',tmp_path/'out')
    for cutoff in ['2020-11-08T07:00:00','2020-11-08T07:00:00-05:00']:
        with pytest.raises(ValueError,match='UTC'):module.prepare([source],cutoff,tmp_path/'out')


def test_overlap_dedup_pending_states_and_no_partial_effect(module,tmp_path):
    source=tmp_path/'raw';fixture(source/'eligible');state=tmp_path/'state.json';state.write_text('{"status":"running","completed_runs":4,"planned_runs":68,"credential":"never publish"}')
    result=module.prepare([source,source],'2020-11-08T07:00:00Z',tmp_path/'out',[('primary_long',state)])
    assert len(result.rows)==1 and result.pending[0].status=='running'
    assert 'never publish' not in (tmp_path/'out/public.json').read_text()
    safeguard=json.loads((tmp_path/'out/safeguard.json').read_text());assert safeguard['effect_estimate'] is None and safeguard['quality_recall'] is None
    with pytest.raises(ValueError):module.Pending(allocation='arbitrary private label',status='running',observed_utc='now')


def test_public_closed_schema_and_symlink_source_rejected(module,tmp_path):
    source=tmp_path/'raw';root=fixture(source/'eligible');target=tmp_path/'target';target.write_text('{}');(root/'outcome.json').unlink();(root/'outcome.json').symlink_to(target)
    with pytest.raises(ValueError,match='Symlink'):module.prepare([source],'2020-11-08T07:00:00Z',tmp_path/'out')
    with pytest.raises(ValueError):module.FrozenRun.model_validate({'secret':'bad'})


def test_validation_binds_companions_and_rejects_future_cutoff(module,tmp_path):
    source=tmp_path/'raw';fixture(source/'eligible');out=tmp_path/'out';result=module.prepare([source],'2020-11-08T07:00:00Z',out)
    assert module.validate(out)==result
    p=out/'safeguard.json';d=json.loads(p.read_text());d['quality_recall']=1.;p.write_text(json.dumps(d))
    with pytest.raises(ValueError,match='Safeguard summary'):module.validate(out)
    with pytest.raises(ValueError,match='future'):module.prepare([source],'2999-01-01T00:00:00Z',tmp_path/'future')


def test_validation_is_invariant_to_row_order_float_sums(module,tmp_path):
    source=tmp_path/'raw'
    for index,duration in enumerate([1e16,1.,1.]):
        root=fixture(source/str(index));m=json.loads((root/'manifest.json').read_text());m['duration_seconds']=duration;(root/'manifest.json').write_text(json.dumps(m));seal(root)
    out=tmp_path/'out';snapshot=module.prepare([source],'2020-11-08T07:00:00Z',out)
    assert module.validate(out)==snapshot
    assert snapshot.cohorts[0].runtime_seconds==10000000000000002.


def test_multi_family_cohort_order_is_canonical(module,tmp_path):
    source=tmp_path/'raw'
    for index,family in enumerate(['catalog','provenance','patch']):
        root=fixture(source/str(index));p=root/'config.snapshot.json';c=json.loads(p.read_text());c['job']['family']=family;p.write_text(json.dumps(c));seal(root)
    out=tmp_path/'out';snapshot=module.prepare([source],'2020-11-08T07:00:00Z',out)
    assert module.validate(out)==snapshot
