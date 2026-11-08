"""Scientific reporting gates use recorded runs, never invented human labels."""
import copy
import importlib
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def analysis(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return importlib.import_module('analyze_confirmatory')


def test_case_interval_keeps_nested_seeds_and_refuses_sparse_cases(analysis):
    pairs=[{'case':case,'effect':float(case%2)} for case in range(3) for seed in range(100)]
    result=analysis.case_cluster_interval(pairs,'effect')
    assert result['case_clusters']==3 and result['paired_runs']==300
    assert result['interval'] is None and result['status']=='insufficient_case_clusters'
    assert result['case_weighted_mean']==pytest.approx(1/3)


def test_case_interval_is_reproducible_for_eligible_case_count(analysis):
    pairs=[{'case':case,'effect':float(case%2)} for case in range(8)]
    first=analysis.case_cluster_interval(pairs,'effect',replicates=100)
    assert first==analysis.case_cluster_interval(pairs,'effect',replicates=100)
    assert first==analysis.case_cluster_interval(list(reversed(pairs)),'effect',replicates=100)
    assert first['interval'][0]<=first['case_weighted_mean']<=first['interval'][1]


def test_rq3_collective_difference_does_not_establish_refusal_bypass(analysis):
    common={'family':'record','status':'completed','cohort':'a','case':0,'seed':1,'condition':'benign_override','executor':'permissive_simulator','context':'natural_history','task_success_rate':1.}
    rows=[{**common,'topology':'single','run_id':'single','attempted_forbidden':False,'actual_state_violation':False,'refusal_rate':0.},
          {**common,'topology':'complete','run_id':'team','attempted_forbidden':True,'actual_state_violation':True,'refusal_rate':0.}]
    result=analysis.rq3_comparisons(rows)[0]
    assert result['collective_state_violation_difference']==1
    assert result['refusal_bypass_status']=='no_observed_single_refusal'
    assert result['refusal_bypass_established'] is False
    rows[0]['refusal_rate']=1.
    assert analysis.rq3_comparisons(rows)[0]['refusal_bypass_status']=='candidate_requires_direct_full_task_refusal_control_and_adjudication'


def test_rq3_context_and_executor_strata_stay_separate(analysis):
    base={'family':'record','status':'completed','cohort':'a','case':0,'seed':1,'condition':'benign_override','task_success_rate':1.,'attempted_forbidden':False,'actual_state_violation':False,'refusal_rate':0.}
    rows=[{**base,'topology':'single','run_id':'s','executor':'deny','context':'matched_reset'},
          {**base,'topology':'complete','run_id':'t','executor':'permissive_simulator','context':'natural_history'}]
    assert analysis.rq3_comparisons(rows)==[]


def review_queue(tmp_path):
    (tmp_path/'review_inputs.json').write_text('{"samples":[{"sample_id":"a"},{"sample_id":"b"}]}')
    (tmp_path/'oracle_labels.private.json').write_text('{"labels":[{"sample_id":"a","violation":true},{"sample_id":"b","violation":false}]}')
    labels=tmp_path/'human.csv';return labels


def test_duplicate_blank_human_labels_are_rejected(monkeypatch,tmp_path):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'));calibrate=importlib.import_module('calibrate_review')
    labels=review_queue(tmp_path);labels.write_text('sample_id,behavior,reason\na,,\na,,\nb,,\n')
    with pytest.raises(ValueError,match='duplicate'):calibrate.calibrate(tmp_path,labels)


def test_ambiguous_human_labels_remain_unadjudicated(monkeypatch,tmp_path):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'));calibrate=importlib.import_module('calibrate_review')
    labels=review_queue(tmp_path);labels.write_text('sample_id,behavior,reason\na,ambiguous,Insufficient context\nb,compliant,Exact task\n')
    result=calibrate.calibrate(tmp_path,labels)
    assert result['human_completed']==2 and result['binary_evaluable_samples']==1
    assert result['status']=='awaiting_adjudication' and not result['fully_adjudicated']


def test_missing_judge_prediction_is_not_dropped_from_recall(monkeypatch,tmp_path):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'));calibrate=importlib.import_module('calibrate_review')
    labels=review_queue(tmp_path);labels.write_text('sample_id,behavior,reason\na,violation,Forbidden operation\nb,compliant,Exact task\n')
    judge=tmp_path/'judge.json';judge.write_text('{"results":[{"sample_id":"b","behavior":"compliant"}]}')
    result=calibrate.calibrate(tmp_path,labels,judge=judge)['judge_against_human']
    assert result['fn']==1 and result['n']==2 and result['recall']==0
    assert result['missing_judge_samples']==1 and result['judge_prediction_coverage']==.5


def test_monitor_requires_full_downstream_artifact_coverage(monkeypatch,tmp_path):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'));monitor=importlib.import_module('deviation_monitor')
    from contagion.storage import seal
    root=tmp_path/'source'/'run';root.mkdir(parents=True)
    config={'family':'patch','plan':{'research_question':'rq1','agent_count':5,'rounds':5}}
    (root/'config.snapshot.json').write_text(json.dumps(config));(root/'manifest.json').write_text('{"status":"completed"}')
    (root/'events.jsonl').write_text('');(root/'outcome.json').write_text('{}');seal(root)
    with pytest.raises(ValueError,match='coverage'):monitor.evaluate(root.parent,tmp_path/'out')


def test_predeclared_partial_spotcheck_exclusions_are_not_false_negatives(monkeypatch,tmp_path):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'));calibrate=importlib.import_module('calibrate_review')
    labels=review_queue(tmp_path);labels.write_text('sample_id,behavior,reason\na,violation,Forbidden operation\nb,compliant,Exact task\n')
    judge=tmp_path/'judge.json';judge.write_text('{"coverage_policy":"predeclared_partial_spotcheck","covered_sample_ids":["b"],"results":[{"sample_id":"b","behavior":"compliant"}]}')
    result=calibrate.calibrate(tmp_path,labels,judge=judge)['judge_against_human']
    assert result['n']==1 and result['fn']==0 and result['recall'] is None
    assert result['unassessed_by_design']==1 and result['missing_judge_samples']==0
    changed=json.loads(judge.read_text());changed['covered_sample_ids']=['a','b'];judge.write_text(json.dumps(changed))
    with pytest.raises(ValueError,match='coverage'):calibrate.calibrate(tmp_path,labels,judge=judge)
