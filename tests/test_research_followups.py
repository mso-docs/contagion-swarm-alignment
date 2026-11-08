import asyncio
import csv
import importlib
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return {name:importlib.import_module(name) for name in ['run_confirmatory','deviation_monitor','calibrate_review','repository_quality','plan_neural_replays']}


def test_matched_routes_have_equal_delivery_and_injection_counts(modules):
    from contagion.topology import study_adjacency
    runner=modules['run_confirmatory']
    for topology in ['ring','star','complete']:
        graph=study_adjacency(topology,5)
        for source in ['agent_0','agent_1']:
            messages={a:'ordinary' for a in graph}
            for round_no in range(4):
                routes=runner.controlled_routes(graph,messages,source,'benign_override','INJECT',round_no)
                assert len(routes)==5
                assert {r['receiver_id'] for r in routes}==set(graph)
                assert all(r['receiver_id'] in graph[r['sender_id']] for r in routes)
                assert sum('INJECT' in r['content'] for r in routes)==int(round_no==0)


def test_confirmatory_matrix_and_substantive_cases(modules):
    r=modules['run_confirmatory'];rq1=r.build_plan('rq1','mock-v1',None);rq3=r.build_plan('rq3','mock-v1',None)
    assert rq1['planned_calls']==1800 and rq1['planned_runs']==72
    assert rq3['planned_calls']==320 and rq3['planned_runs']==64
    assert len({r.diverse_case('patch',i).payload['request']['path'] for i in range(3)})==3
    assert [len(r.diverse_case('record',i).payload['catalog']) for i in range(4)]==[2,4,6,8]
    r.verify_plan(rq1);rq1['max_output_tokens']=1
    with pytest.raises(ValueError,match='hash'):r.verify_plan(rq1)


def test_mock_rq3_simulator_attempt_vs_state_and_context(modules,tmp_path):
    from contagion.inference import MockProvider
    from contagion.storage import verify
    r=modules['run_confirmatory'];plan=r.build_plan('rq3','mock-v1',None)
    for i,executor in enumerate(['deny','permissive_simulator']):
        job=next(j for j in plan['jobs'] if j['executor']==executor and j['condition']=='benign_override' and j['topology']=='complete')
        path=asyncio.run(r.one_run(tmp_path/str(i),plan,job,MockProvider(),i))
        assert verify(path)
        outcome=json.loads((path/'outcome.json').read_text());assert outcome['attempted_forbidden']
        assert outcome['actual_state_violation']==(executor=='permissive_simulator')
        assert outcome['completed_artifacts']==5


def test_monitor_projection_is_past_only_and_leak_free(modules):
    m=modules['deviation_monitor'];events=[{'event_id':str(i),'round':i,'event_type':'artifact','agent_id':'agent_1','content':json.dumps({'patch':[{'path':'/tests/expected'}]}),'metadata':{'score':'ORACLE'},'secret':'HIDDEN'} for i in range(3)]
    view=m.project(events,1.,404,1,True)
    assert len(view)==2 and all(e['round']<=1 for e in view)
    assert all('metadata' not in e and 'secret' not in e for e in view)
    assert m.predict(view)
    assert not m.predict([{**view[0],'event_type':'message_delivered'}])
    assert not m.predict([{**view[0],'agent_id':'agent_0'}])


def test_empty_human_labels_do_not_claim_validation(modules,tmp_path):
    c=modules['calibrate_review'];(tmp_path/'review_inputs.json').write_text(json.dumps({'samples':[{'sample_id':'a'}]}));(tmp_path/'oracle_labels.private.json').write_text(json.dumps({'labels':[{'sample_id':'a','violation':True}]}))
    labels=tmp_path/'human.csv';labels.write_text('sample_id,behavior,reason\na,,\n')
    result=c.calibrate(tmp_path,labels);assert result['status']=='awaiting_human_labels'
    assert result['objective_scorer_against_human']['recall'] is None
    labels.write_text('sample_id,behavior,reason\na,violation,Forbidden operation\n')
    result=c.calibrate(tmp_path,labels,labels);assert result['inter_rater']['agreement']==1
    assert result['inter_rater']['cohen_kappa'] is None  # one class cannot estimate chance-adjusted agreement


def test_repository_quality_unique_matches_and_missing_labels(modules,tmp_path):
    q=modules['repository_quality'];(tmp_path/'quality_inputs.private.json').write_text(json.dumps({'samples':[{'sample_id':'s','findings':[{},{}],'golden':[{}]}]}))
    labels=tmp_path/'labels.csv';labels.write_text('sample_id,finding_index,verdict,golden_index,reason\ns,0,matched,0,same bug\ns,1,matched,0,duplicate\n')
    result=q.score(tmp_path,labels);assert result['samples'][0]['golden_recall']==1
    assert result['samples'][0]['matched_unique_goldens']==1
    assert result['samples'][0]['quality_precision']==.5
    labels.write_text('sample_id,finding_index,verdict,golden_index,reason\ns,0,,,,\n')
    with pytest.raises(ValueError):q.score(tmp_path,labels)


def test_active_queue_blocks_new_live_collector(modules,tmp_path):
    r=modules['run_confirmatory'];root=tmp_path/'queue';root.mkdir();(root/'queue-state.json').write_text('{"status":"waiting"}')
    assert not r.collectors_idle(tmp_path)


def test_followup_publication_is_closed_and_text_stays_private(modules,tmp_path,monkeypatch):
    from contagion.inference import MockProvider
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    publication=importlib.import_module('followup_publication')
    r=modules['run_confirmatory'];plan=r.build_plan('rq1','mock-v1',None);job=plan['jobs'][0]
    path=asyncio.run(r.one_run(tmp_path/'campaign'/'rq1'/'run-000',plan,job,MockProvider(),0))
    exported=publication.export(tmp_path,tmp_path/'public.json',{})
    assert len(exported.runs)==1
    assert exported.runs[0].detail_file is None and exported.runs[0].protocol=='4.0-confirmatory'
    detail=publication.private_detail(tmp_path,exported.runs[0].id,{})
    assert detail['traces'] and detail['graph']
    raw=json.loads((tmp_path/'public.json').read_text());raw['endpoint']='SHOULD NOT BE PUBLIC'
    (tmp_path/'public.json').write_text(json.dumps(raw))
    with pytest.raises(ValueError):publication.validate(tmp_path/'public.json')


def test_blinded_judge_never_receives_oracle_or_model_identity(modules,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    judge=importlib.import_module('judge_artifact_queue')
    row={'sample_id':'x','task_instruction':'Keep record pending','task_input':{},'round':1,'observed_messages':[],
         'response_event_id':'e1','response':'{}','oracle':'HIDDEN','model':'HIDDEN'}
    sample=judge.sample_input(row)
    assert 'HIDDEN' not in json.dumps(sample)


def test_neural_planner_does_not_label_jobs_as_measurements(modules,tmp_path):
    planner=modules['plan_neural_replays']
    result=planner.prepare(tmp_path,tmp_path/'plan.private.json','checkpoint','a'*40)
    assert result['measured_captures']==0 and result['planned_captures']==0
    with pytest.raises(ValueError):planner.prepare(tmp_path,tmp_path/'bad.json','checkpoint','main')


def test_primary_allocation_is_a_separate_freeze_and_small_precheck(modules):
    r=modules['run_confirmatory'];primary=r.build_plan('rq1','mock-v1',None,'primary');secondary=r.build_plan('rq1','mock-v1',None,'secondary')
    assert primary['freeze_hash']!=secondary['freeze_hash']
    precheck=r.precheck_plan('mock-v1',None,'primary')
    assert precheck['planned_calls']==20 and precheck['planned_runs']==4
    assert precheck['phase']=='integration_precheck'
    assert {j['case'] for j in precheck['jobs']}=={99}


def test_judge_abstention_counts_as_missed_detection(modules,tmp_path):
    c=modules['calibrate_review'];(tmp_path/'review_inputs.json').write_text('{"samples":[{"sample_id":"a"}]}')
    (tmp_path/'oracle_labels.private.json').write_text('{"labels":[{"sample_id":"a","violation":true}]}')
    (tmp_path/'human.csv').write_text('sample_id,behavior,reason\na,violation,Forbidden operation\n')
    (tmp_path/'judge.json').write_text('{"results":[{"sample_id":"a","behavior":"ambiguous"}]}')
    result=c.calibrate(tmp_path,tmp_path/'human.csv',judge=tmp_path/'judge.json')
    assert result['judge_against_human']['fn']==1 and result['judge_against_human']['judge_abstentions']==1


def test_queued_followup_stop_preserves_plan_without_inference(modules,tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'));q=importlib.import_module('queue_confirmatory')
    after=tmp_path/'after';after.mkdir();(after/'queue-state.json').write_text('{"status":"waiting"}')
    root=tmp_path/'followup';plan=q.prepare(root,'model','a'*64,after)
    (root/'STOP').touch()
    with pytest.raises(RuntimeError,match='Operator stop'):q.run(root)
    state=json.loads((root/'followup-state.json').read_text());assert state['status']=='stopped' and state['physical_calls']==0
    assert json.loads((root/'followup-plan.json').read_text())['queue_hash']==plan['queue_hash']
