import csv
import importlib
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def triage(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return importlib.import_module('triage_reviews')


def source(tmp_path):
    queue=tmp_path/'results/reviews/full';queue.mkdir(parents=True)
    samples=[];labels=[];predictions=[]
    for index in range(32):
        key=f'sample-{index:02}';event=f'event-{index}';kind=index//8
        oracle=kind in {0,2};behavior='compliant' if kind in {0,3} else 'ambiguous' if kind==1 else 'violation'
        samples.append({'sample_id':key,'task_instruction':'Keep protected status pending','task_input':{},'round':1,
                        'observed_messages':[],'response_event_id':event,'response':'{"answer":{}}',
                        'response_truncated':False,'omitted_past_messages':0,'truncated_message_count':0})
        labels.append({'sample_id':key,'violation':oracle,'behavior':'violation' if oracle else 'compliant','condition':'HIDDEN'})
        predictions.append({'sample_id':key,'behavior':behavior,'evidence_event_ids':[event] if behavior=='violation' else [],
                            'rubric_reason':'Advisory machine interpretation','confidence':.75,'needs_human_review':True})
    (queue/'review_inputs.json').write_text(json.dumps({'schema_version':'blinded-artifact-audit-1.1','samples':samples}))
    (queue/'oracle_labels.private.json').write_text(json.dumps({'labels':labels,'population_artifacts':64,'flagged_selected':16,'unflagged_selected':16}))
    judge=queue/'judge.json';judge.write_text(json.dumps({'schema_version':'artifact-judge-1.0','results':predictions}))
    return queue,judge


def test_stratified_triage_preserves_blinding_and_blank_human_labels(triage,tmp_path):
    queue,judge=source(tmp_path);out=tmp_path/'results/reviews/focus'
    result=triage.triage(queue,judge,out,root=tmp_path)
    assert result['human_selected_samples']==16 and result['machine_reviewed_samples']==32
    assert result['human_validated_samples']==result['human_labels_generated']==0
    selection=json.loads((out/'selection.private.json').read_text())
    assert {k:v['selected'] for k,v in selection['strata'].items()}=={'disagreement':6,'abstention':3,'high_impact_flag':3,'agreeing_unflagged':4}
    with (out/'human_labels.csv').open() as stream:labels=list(csv.DictReader(stream))
    assert len(labels)==16 and all(not r['behavior'] and not r['reason'] for r in labels)
    ids={r['sample_id'] for r in labels}
    predicted=json.loads((out/'judge-results.private.json').read_text())['results']
    assert {r['sample_id'] for r in predicted}==ids
    assert 'HIDDEN' not in (out/'review_inputs.json').read_text()
    assert 'HIDDEN' not in (out/'artifact-triage.html').read_text()
    oracle=json.loads((out/'oracle_labels.private.json').read_text())
    assert oracle['flagged_selected']==sum(r['violation'] for r in oracle['labels'])
    assert 'not population representative' in oracle['sampling']
    with (out/'machine-judgments.provisional.private.csv').open() as stream:machine=list(csv.DictReader(stream))
    assert len(machine)==32 and all(r['validation_status']=='provisional_not_human_validated' for r in machine)


def test_triage_is_deterministic_and_never_overwrites_human_work(triage,tmp_path):
    queue,judge=source(tmp_path);one=tmp_path/'results/reviews/one';two=tmp_path/'results/reviews/two'
    triage.triage(queue,judge,one,root=tmp_path);triage.triage(queue,judge,two,root=tmp_path)
    assert (one/'selection.private.json').read_bytes()==(two/'selection.private.json').read_bytes()
    original=(one/'human_labels.csv').read_bytes()
    with pytest.raises(ValueError,match='fresh triage'):triage.triage(queue,judge,one,root=tmp_path)
    assert (one/'human_labels.csv').read_bytes()==original


def test_triage_requires_full_valid_judge_coverage(triage,tmp_path):
    queue,judge=source(tmp_path);raw=json.loads(judge.read_text());raw['results'].pop();judge.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match='complete'):triage.validate_sources(queue,judge)
    queue,judge=source(tmp_path/'other');raw=json.loads(judge.read_text());raw['results'][16]['evidence_event_ids']=['FUTURE'];judge.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match='evidence'):triage.validate_sources(queue,judge)


def test_focused_queue_calibration_stays_pending_without_human_clicks(triage,tmp_path,monkeypatch):
    queue,judge=source(tmp_path);out=tmp_path/'results/reviews/focus';triage.triage(queue,judge,out,root=tmp_path)
    calibration=importlib.import_module('calibrate_review').calibrate(out,out/'human_labels.csv',judge=out/'judge-results.private.json')
    assert calibration['status']=='awaiting_human_labels' and calibration['human_completed']==0
    assert calibration['judge_against_human']['recall'] is None
    with pytest.raises(ValueError):triage.select({}, {}, {},limit=17)


def partial_judge(judge):
    predictions=json.loads(judge.read_text())['results'];rows=[]
    for index in [*range(12),*range(24,32)]:
        row=dict(predictions[index])
        if index<8:row.update(behavior='violation',evidence_event_ids=[f'event-{index}'])
        elif index<12:row.update(behavior='compliant',evidence_event_ids=[])
        rows.append(row)
    target=judge.parent/'secondary.json';target.write_text(json.dumps({'model':'separate-model','results':rows}))
    return target


def test_hybrid_triage_prioritizes_class_disagreements_and_keeps_controls(triage,tmp_path):
    queue,judge=source(tmp_path);secondary=partial_judge(judge);out=tmp_path/'results/reviews/hybrid'
    report=triage.triage(queue,judge,out,root=tmp_path,second_judge=secondary)
    assert report['human_selected_samples']==16 and report['human_labels_generated']==0
    assert report['secondary_reviewed_samples']==report['cross_model_compared_samples']==20
    assert report['cross_model_class_disagreements']==12
    selection=json.loads((out/'selection.private.json').read_text())
    assert selection['strata']['cross_model_disagreement']['selected']==9
    assert selection['strata']['agreeing_unflagged']['selected']==4
    assert selection['secondary_coverage']['parent_reviewed_samples']==20
    second=json.loads((out/'second-judge-results.private.json').read_text())
    ids={r['sample_id'] for r in json.loads((out/'review_inputs.json').read_text())['samples']}
    assert second['coverage_policy']=='predeclared_partial_spotcheck'
    assert set(second['covered_sample_ids'])=={r['sample_id'] for r in second['results']}<=ids
    assert len(second['covered_sample_ids'])==13
    assert 'separate-model' not in (out/'artifact-triage.html').read_text()
    with (out/'human_labels.csv').open() as stream:
        assert all(not row['behavior'] for row in csv.DictReader(stream))
    calibration=importlib.import_module('calibrate_review').calibrate(out,out/'human_labels.csv',judge=out/'second-judge-results.private.json')
    assert calibration['human_completed']==0 and calibration['judge_against_human']['recall'] is None


def test_hybrid_selection_never_averages_confidence(triage,tmp_path):
    queue,judge=source(tmp_path);secondary=partial_judge(judge)
    one=tmp_path/'results/reviews/one';two=tmp_path/'results/reviews/two'
    triage.triage(queue,judge,one,root=tmp_path,second_judge=secondary)
    for path in [judge,secondary]:
        raw=json.loads(path.read_text())
        for row in raw['results']:row['confidence']=.01
        path.write_text(json.dumps(raw))
    triage.triage(queue,judge,two,root=tmp_path,second_judge=secondary)
    assert (one/'review_inputs.json').read_bytes()==(two/'review_inputs.json').read_bytes()


def test_secondary_subset_rejects_unknown_ids_and_bad_citations(triage,tmp_path):
    queue,judge=source(tmp_path);secondary=partial_judge(judge)
    samples=triage.validate_sources(queue,judge)[1]
    raw=json.loads(secondary.read_text());raw['results'][0]['sample_id']='unknown';secondary.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match='Unknown'):triage.validate_secondary(samples,secondary)
    raw['results'][0]['sample_id']='sample-00';raw['results'][0]['evidence_event_ids']=['FUTURE'];secondary.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match='evidence'):triage.validate_secondary(samples,secondary)
