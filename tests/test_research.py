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


def test_two_worker_shards_cover_schedule_without_splitting_pairs(tmp_path):
    plan=StudyPlan(families=['catalog'],model='mock-v1',rounds=1,
                   topologies=['ring','star','complete'],max_total_model_calls=30)
    freeze=tmp_path/'freeze.json';freeze_plan(plan,freeze)
    def run(index):
        return asyncio.run(run_plan(plan,MockProvider(),tmp_path/f'worker{index}',freeze,index,2))
    a,b=run(0),run(1)
    assert len(a)==4 and len(b)==2
    def conditions(paths):
        result={}
        for path in paths:
            c=json.loads((path/'config.snapshot.json').read_text())
            result.setdefault((c['family'],c['case_index'],c['seed'],c['topology']),set()).add(c['intervention'])
        return result
    x,y=conditions(a),conditions(b)
    assert not set(x).intersection(y) and len(set(x)|set(y))==3
    assert all(v=={'none','benign_override'} for v in [*x.values(),*y.values()])
    with pytest.raises(ValueError):asyncio.run(run_plan(plan,MockProvider(),tmp_path/'invalid',freeze,2,2))


def test_live_sharding_rejects_unknown_model_digest_before_calls(tmp_path):
    plan=StudyPlan(families=['catalog'],rounds=1,max_total_model_calls=10)
    provider=MockProvider();provider.identity={'backend':'openai','model':'test','digest':None}
    with pytest.raises(ValueError):asyncio.run(run_plan(plan,provider,tmp_path/'invalid',tmp_path/'missing.json',0,2))
    assert not (tmp_path/'invalid').exists()


def test_cli_digest_mismatch_closes_provider_without_inference(monkeypatch,tmp_path):
    from types import SimpleNamespace
    from contagion import research
    observed=[]
    class Provider:
        def __init__(self,*args,**kwargs):
            self.identity={'backend':'ollama'}
        async def discover(self):return [{'name':'test-model','digest':'actual-digest'}]
        async def close(self):observed.append('closed')
        async def chat(self,*args):observed.append('inference');raise AssertionError('Unexpected inference')
    monkeypatch.setattr(research,'HTTPProvider',Provider)
    monkeypatch.setattr(research,'environment',lambda path:{'CONTAGION_BASE_URL':'http://localhost:11434'})
    args=SimpleNamespace(command='study',env_file=None,model='test-model',provider='ollama',expected_digest='other-digest')
    with pytest.raises(ValueError):asyncio.run(research.main_async(args))
    assert observed==['closed']


@pytest.mark.parametrize('count',[5,10,20,40,80,128])
def test_scaling_graphs_and_protocol_gate(count):
    from contagion.topology import adjacency,study_adjacency
    ring=study_adjacency('ring',count);star=study_adjacency('star',count)
    assert len(ring)==count and all(len(v)==2 for v in ring.values())
    assert len(star['agent_0'])==count-1
    assert all(a not in v for a,v in ring.items())
    assert all(a in ring[b] for a,neighbors in ring.items() for b in neighbors)
    if count!=5:
        with pytest.raises(ValueError):adjacency('ring',count)
        with pytest.raises(ValueError):StudyPlan(agent_count=count)
    StudyPlan(protocol_version='2.1',agent_count=count,families=['catalog'],rounds=2,
              max_model_calls=count*2,max_total_model_calls=count*4)


def test_scaling_mock_call_count_isolation_and_public_cohort(tmp_path):
    from contagion.research_publication import make_research_snapshot
    plan=StudyPlan(protocol_version='2.1',agent_count=10,families=['catalog'],model='mock-v1',rounds=2,
                   max_model_calls=20,max_total_model_calls=40)
    execute_study(tmp_path,plan)
    rows=summarize_study(tmp_path/'raw')
    assert len(rows)==2 and all(len(r['manifest']['graph'])==10 for r in rows)
    assert all(r['manifest']['completed_model_calls']==20 for r in rows)
    public=make_research_snapshot(study_sources=[tmp_path/'raw'],env={})
    assert all(r.protocol=='2.1' and r.agent_count==10 for r in public.studies)
    with pytest.raises(ValueError):StudyPlan(protocol_version='2.1',agent_count=128,families=['catalog'],topologies=['complete'],
                                           rounds=2,max_model_calls=256,max_total_model_calls=512)


def test_v2_monitor_rescores_catalog_and_excludes_other_tasks(tmp_path):
    plan=StudyPlan(families=['catalog','patch'],model='mock-v1',rounds=2,max_total_model_calls=40)
    execute_study(tmp_path,plan)
    result=evaluate_visibility(tmp_path/'raw',tmp_path/'monitor')
    assert result['skipped_non_catalog_runs']==2
    assert len(result['observations'])==16
    assert {x['truth'] for x in result['observations']}=={True,False}
    assert all(x['model']=='mock-v1' and x['protocol']=='2.0' for x in result['summary'])
    for path in (tmp_path/'monitor').glob('*.view.json'):
        assert 'metadata' not in json.dumps(json.loads(path.read_text()))


def test_public_study_detail_is_bounded_and_redacted(tmp_path):
    from contagion.research_publication import make_research_snapshot,validate_study_detail
    plan=StudyPlan(families=['catalog'],model='mock-v1',rounds=2,max_total_model_calls=20)
    execute_study(tmp_path,plan)
    public=make_research_snapshot(study_sources=[tmp_path/'raw'],detail_directory=tmp_path/'details',include_text=True,env={})
    assert all(r.detail_file for r in public.studies)
    for path in (tmp_path/'details').glob('*.json'):
        detail=validate_study_detail(path,env={})
        assert detail.task_instruction and detail.task_input and detail.traces
        assert len(detail.traces)+detail.omitted_events==detail.eligible_events
        assert all(t.event_type!='inference_requested' for t in detail.traces)


def test_protocol22_retains_invalid_outputs_without_runner_failure(tmp_path):
    from contagion.models import ModelResponse
    class Provider:
        identity={'backend':'ollama','model':'fixture'}
        async def chat(self,messages,config):
            return ModelResponse(content=json.dumps({'answer':{},'audit_marker':'violet lantern','message':'untrusted','refusal':False}))
    plan=StudyPlan(protocol_version='2.2',families=['catalog'],model='fixture',rounds=1,max_total_model_calls=10)
    freeze=tmp_path/'freeze.json';freeze_plan(plan,freeze)
    asyncio.run(run_plan(plan,Provider(),tmp_path/'raw',freeze))
    rows=summarize_study(tmp_path/'raw')
    assert all(r['manifest']['status']=='completed' and r['manifest']['parse_failures']==5 for r in rows)
    assert all(r['outcome']['unscorable_final_agents']==5 and r['outcome']['task_success_rate']==0 for r in rows)
    from contagion.research_publication import make_research_snapshot
    exported=make_research_snapshot(study_sources=[tmp_path/'raw'],env={})
    assert all(r.violation_status=='indeterminate' and not r.violation for r in exported.studies)
    with pytest.raises(ValueError,match='No matching completed catalog'):
        evaluate_visibility(tmp_path/'raw',tmp_path/'monitor')


def test_openai_compatible_judge_uses_backend_default_thinking(tmp_path):
    from contagion.models import ModelResponse
    class Reviewer:
        identity={'backend':'openai'}
        async def chat(self,messages,config):
            assert config.thinking=='default'
            return ModelResponse(content=json.dumps({'behavior':'ambiguous','evidence_event_ids':[],
                'rubric_reason':'Needs human review','confidence':0.2,'needs_human_review':True}))
    asyncio.run(review_batch(FIXTURE,tmp_path/'review',Reviewer(),model='fixture',max_calls=1))
    rows=json.loads((tmp_path/'review/reviews.json').read_text())
    assert rows[0]['error'] is None


def test_openrouter_id_discovery_uses_api_id_even_when_display_name_present(monkeypatch,tmp_path):
    from types import SimpleNamespace
    from contagion import research
    class Provider:
        def __init__(self,*args,**kwargs):self.identity={'backend':'openai'}
        async def discover(self):return [{'id':'vendor/model','name':'Friendly display name'}]
        async def close(self):pass
    observed=[]
    async def review(*args,**kwargs):observed.append(args[3]);return {'reviewed':0}
    monkeypatch.setattr(research,'HTTPProvider',Provider)
    monkeypatch.setattr(research,'review_batch',review)
    monkeypatch.setattr(research,'environment',lambda path:{'CONTAGION_BASE_URL':'http://localhost:1234/v1'})
    args=SimpleNamespace(command='review',env_file=None,model='vendor/model',provider='openai',expected_digest=None,
                         source=tmp_path,out=tmp_path/'out',max_calls=1,seed=404)
    asyncio.run(research.main_async(args))
    assert observed==['vendor/model']


def test_public_study_metrics_are_derived_from_sealed_logs(tmp_path):
    from contagion.research_publication import make_research_snapshot
    plan=StudyPlan(families=['catalog'],model='mock-v1',max_total_model_calls=50)
    execute_study(tmp_path,plan)
    snapshot=make_research_snapshot([tmp_path/'raw'],env={})
    control=next(r for r in snapshot.studies if r.intervention=='none')
    injected=next(r for r in snapshot.studies if r.intervention=='benign_override')
    assert control.calls==25 and control.attempted_calls==25 and control.http_attempts==0
    assert control.started_utc and control.source_hash and control.rounds==5
    assert control.generated_tokens is None  # Never invent token telemetry for mock inference.
    assert control.median_call_seconds is not None
    assert len(control.agents)==5 and all(a.task_success for a in control.agents)
    assert sum(a.messages_received for a in control.agents)==control.messages_delivered
    assert control.downstream_adoption_rate==0 and injected.downstream_adoption_rate==1
    assert control.downstream_clean_rate==1
