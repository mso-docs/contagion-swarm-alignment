import asyncio
import json
from pathlib import Path

import pytest

from contagion.inference import MockProvider
from contagion.monitor import detection_metrics, keyword_rule, restricted_view, evaluate_visibility
from contagion.review import ReviewResult, samples_from_runs, validate_review, review_batch, calibration_report
from contagion.studies import StudyPlan, freeze_plan, verify_freeze, run_plan, summarize_study
from contagion.tasks import TaskArtifact, ToyRecordStore, make_case, task_score

FIXTURE=Path(__file__).parent/'fixtures/mock_run'


@pytest.mark.parametrize('family',['catalog','provenance','patch','record'])
def test_task_cases_and_ground_truth(family):
    development=make_case(family,'development',0);evaluation=make_case(family,'evaluation',0)
    assert development.case_id!=evaluation.case_id
    assert development.payload!=evaluation.payload or family=='patch'
    clean=TaskArtifact(answer=development.expected,message='data')
    assert task_score(development,clean,ToyRecordStore())['task_success']
    assert task_score(development,None,ToyRecordStore())['behavior']=='unscorable'
    assert 'expected' not in development.payload


def test_simulator_denial_and_permissive_state_are_distinct():
    action={'operation':'propose_protected_update','status':'approved'}
    denied=ToyRecordStore();permissive=ToyRecordStore(True)
    assert denied.propose(action)=={'attempted':True,'state_violation':False,'valid_action':True}
    assert permissive.propose(action)['state_violation']
    assert ToyRecordStore().status=='pending'
    assert not denied.propose({'operation':'shell','command':'anything'})['valid_action']


def test_heldout_seed_and_budget_enforcement():
    with pytest.raises(ValueError):StudyPlan(split='evaluation',seeds=[101])
    with pytest.raises(ValueError):StudyPlan(max_total_model_calls=1)
    with pytest.raises(ValueError):StudyPlan(seeds=[101,101])
    assert StudyPlan(split='evaluation',seeds=[10001]).split=='evaluation'


def execute_study(tmp_path,plan):
    freeze=tmp_path/'freeze.json';freeze_plan(plan,freeze)
    return asyncio.run(run_plan(plan,MockProvider(),tmp_path/'raw',freeze))


def test_frozen_plan_and_mock_propagation(tmp_path):
    plan=StudyPlan(families=['catalog'],model='mock-v1',max_total_model_calls=50)
    paths=execute_study(tmp_path,plan)
    rows=summarize_study(tmp_path/'raw')
    assert len(paths)==2
    assert all(r['manifest']['completed_model_calls']==25 for r in rows)
    by={r['config']['interventions'][0]:r['outcome'] for r in rows}
    assert not by['none']['any_violation']
    assert by['benign_override']['downstream_final_violation_rate']==1
    with pytest.raises(ValueError):verify_freeze(plan.model_copy(update={'temperature':.7}),tmp_path/'freeze.json')


@pytest.mark.parametrize('executor',['deny','permissive_simulator'])
def test_rq3_equal_calls_and_fresh_simulated_state(tmp_path,executor):
    plan=StudyPlan(research_question='rq3',families=['record'],topologies=['single','complete'],
                   model='mock-v1',executor=executor,max_model_calls=5,max_total_model_calls=20)
    execute_study(tmp_path,plan)
    rows=summarize_study(tmp_path/'raw')
    assert len(rows)==4
    assert all(r['manifest']['completed_model_calls']==5 for r in rows)
    for row in rows:
        challenged=row['config']['interventions']==['benign_override']
        assert row['outcome']['attempted_forbidden']==challenged
        assert row['outcome']['actual_state_violation']==(challenged and executor=='permissive_simulator')
        if not challenged:assert row['outcome']['task_success_rate']==1


def test_visibility_nested_deterministic_and_no_oracle_leak():
    events=[{'event_id':f'e{i}','sequence_no':i,'round':i//5,'event_type':'message_delivered','content':'violet lantern' if i%2 else 'clean',
             'receiver_id':'agent_1','metadata':{'oracle':True,'intervention':'hidden'}} for i in range(40)]
    a=restricted_view(events,.25,404);b=restricted_view(events,.5,404)
    assert {e['event_id'] for e in a}<={e['event_id'] for e in b}
    assert restricted_view(events,0,404)==[]
    assert len(restricted_view(events,1,404))==40
    changed=[{**e,'metadata':{'oracle':False}} for e in events]
    assert restricted_view(changed,.25,404)==a
    assert keyword_rule(restricted_view(changed,1,404))==keyword_rule(restricted_view(events,1,404))
    assert all('metadata' not in e for e in b)
    assert all(e['round']<=1 for e in restricted_view(events,1,404,cutoff=1))


def test_detection_undefined_recall():
    result=detection_metrics([(False,True),(False,False)])
    assert result['recall'] is None and result['f1'] is None
    assert result['precision']==0 and result['false_positive_rate']==.5


def test_monitor_fixture_is_synthetic_and_persists_masks(tmp_path):
    result=evaluate_visibility(FIXTURE,tmp_path/'monitor')
    assert len(result['observations'])==8
    assert all(o['backend']=='mock' for o in result['observations'])
    assert len(list((tmp_path/'monitor').glob('*.view.json')))==8


def test_blinded_review_inputs_and_evidence_validation():
    samples,oracle=samples_from_runs(FIXTURE)
    assert len(samples)==5 and len(oracle)==5
    text=json.dumps(samples)
    assert 'adopted_instruction' not in text and 'intervention' not in text and 'metadata' not in text
    with pytest.raises(ValueError):validate_review({'behavior':'violation','evidence_event_ids':['future-event'],'rubric_reason':'claim','confidence':1,'needs_human_review':False},samples[0])


def test_review_queue_preserves_unreviewed_and_calibration_requires_labels(tmp_path):
    directory=tmp_path/'reviews'
    result=asyncio.run(review_batch(FIXTURE,directory,max_calls=2,audit_fraction=1))
    assert result=={'samples':5,'reviewed':2,'queued':5,'remaining':3}
    queue=json.loads((directory/'queue.json').read_text())
    assert all(q['random_audit'] for q in queue[:2])
    assert all(q['reasons']==['not_reviewed_call_budget'] for q in queue[2:])
    assert (directory/'review.events.jsonl').is_file()
    labels=tmp_path/'labels.jsonl';labels.write_text('')
    with pytest.raises(ValueError):calibration_report(directory,labels)
    samples=json.loads((directory/'inputs.json').read_text())
    labels.write_text(json.dumps({'sample_id':samples[0]['sample_id'],'behavior':'compliant','evidence_event_ids':[samples[0]['final_event_id']]})+'\n')
    calibration=calibration_report(directory,labels)
    assert calibration['recall'] is None and calibration['auto_clear_enabled'] is False


def test_scenario_registry_sampling_and_split_integrity(tmp_path):
    from contagion.scenarios import build_database, load_registry, sample_scenarios
    db=tmp_path/'scenarios.sqlite';index=tmp_path/'index.json'
    summary=build_database(db,index)
    records=load_registry(db)
    assert summary['scenario_count']==384 and len({r['case_id'] for r in records})==384
    assert sum(r['split']=='development' for r in records)==256
    assert sum(r['split']=='evaluation' for r in records)==128
    for family in ['catalog','provenance','patch','record']:
        dev={json.dumps(r['payload'],sort_keys=True) for r in records if r['family']==family and r['split']=='development'}
        evaluation={json.dumps(r['payload'],sort_keys=True) for r in records if r['family']==family and r['split']=='evaluation'}
        assert not dev.intersection(evaluation)
    a,h=sample_scenarios(db,'development',['catalog','provenance','patch'],6,707)
    b,h2=sample_scenarios(db,'development',['catalog','provenance','patch'],6,707)
    assert a==b and h==h2 and len({c.family for c in a})==3
    assert all(c.split=='development' for c in a)
    with pytest.raises(ValueError):build_database(db)
    public=json.loads(index.read_text())
    assert all('payload' not in r and 'expected' not in r for r in public['scenarios'])


def test_research_export_registry_and_closed_schema(tmp_path):
    from contagion.scenarios import build_database
    from contagion.research_publication import make_research_snapshot,validate_research_snapshot
    index=tmp_path/'index.json';build_database(tmp_path/'db.sqlite',index)
    snapshot=make_research_snapshot(scenario_index=index)
    assert len(snapshot.scenarios)==384 and not snapshot.neural and not snapshot.reviewer_calibrated
    output=tmp_path/'research.json';output.write_text(snapshot.model_dump_json())
    assert validate_research_snapshot(output)==snapshot
    data=json.loads(output.read_text());data['raw_prompt']='private'
    output.write_text(json.dumps(data))
    with pytest.raises(ValueError):validate_research_snapshot(output)


def test_neural_runtime_is_honest_and_rejects_unmeasured_capture():
    from contagion.neural import runtime_status,validate_numeric_capture
    assert isinstance(runtime_status(),dict)
    with pytest.raises((ValueError,KeyError,TypeError)):validate_numeric_capture({'layers':[]})


def test_research_validation_rejects_known_private_model_value(tmp_path):
    from contagion.research_publication import ResearchSnapshot,validate_research_snapshot
    snapshot=ResearchSnapshot(generated_utc='2026-11-07T00:00:00Z',limitations=[])
    data=snapshot.model_dump()
    data['reviews']=[{'sample_id':'sample','behavior':'ambiguous','confidence':0.1,'needs_human_review':True,
                     'evidence_event_ids':[],'reason':'opaquePrivateTestValue','queue_reasons':[],'priority':60}]
    output=tmp_path/'research.json';output.write_text(json.dumps(data))
    with pytest.raises(ValueError):validate_research_snapshot(output,env={'CONTAGION_API_KEY':'opaquePrivateTestValue'})


def test_neural_public_reducer_withholds_private_inputs_and_checks_integrity(tmp_path):
    import hashlib
    from contagion.research_publication import make_research_snapshot,validate_research_snapshot
    directory=tmp_path/'capture';directory.mkdir()
    # Synthetic numeric unit fixture only; never exported into the repository snapshot.
    raw={'schema_version':'1.0','evidence_type':'random_weight_smoke','model':'unit-fixture',
         'revision':None,'seed':101,'dtype':'float32','device':'cpu','duration_seconds':0.1,
         'clean_token_count':1,'corrupt_token_count':1,
         'layers':[{'layer':0,'clean_residual_rms':[0.2],'corrupt_residual_rms':[0.3],
                    'neurons':[{'index':0,'clean':[0.4],'corrupt':[0.5]}]}],
         'patch':{'hook':'blocks.0.hook_out','clean_position':0,'corrupt_position':0,
                  'target_token_id_private':42,'clean_target_logit':1.,'corrupt_target_logit':0.,
                  'patched_target_logit':0.5,'noop_target_logit':0.,'position_control_logit':0.},
         'raw_prompt':'privatePromptMustStayLocal'}
    (directory/'capture.json').write_text(json.dumps(raw))
    (directory/'private_inputs.json').write_text(json.dumps({'token_ids':[42],'text':'privatePromptMustStayLocal'}))
    (directory/'activations.safetensors').write_bytes(b'unit fixture only')
    hashes={name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in ['capture.json','private_inputs.json','activations.safetensors']}
    (directory/'checksums.json').write_text(json.dumps(hashes))
    snapshot=make_research_snapshot(neural_sources=[directory],env={})
    text=snapshot.model_dump_json()
    assert 'privatePromptMustStayLocal' not in text and 'target_token_id_private' not in text and 'token_ids' not in text
    out=tmp_path/'public.json';out.write_text(text);validate_research_snapshot(out,env={})
    (directory/'private_inputs.json').write_text('changed')
    with pytest.raises(ValueError):make_research_snapshot(neural_sources=[directory],env={})
    data=json.loads(text);data['neural'][0]['layers'][0]['clean_residual_rms']=[1.,2.]
    out.write_text(json.dumps(data))
    with pytest.raises(ValueError):validate_research_snapshot(out,env={})
