import copy
import importlib
import itertools
import json
from pathlib import Path

import pytest

from contagion.storage import seal
from contagion.topology import study_adjacency


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    module=importlib.import_module('analyze_prior_primary_checkpoint')
    jobs=[]
    for case in range(2):
        for defense,condition in itertools.product(('plain','source_attribution'),('none','benign_override')):
            jobs.append({'task_id':f'{case:020x}','rounds':1,'topology':'ring','seed':21001,'phase':'evaluation',
                         'defense':defense,'intervention':condition,'calls':5})
    plan={'protocol_version':module.PROTOCOL,'plan_hash':'a'*64,'source_hash':'b'*64,'model':'fixture','model_digest':'c'*64,
          'dependencies':{'primary_repository_runner.py':'d'*64},'jobs':jobs,'planned_runs':8,'planned_calls':40}
    monkeypatch.setattr(module,'_plan',lambda queue:copy.deepcopy(plan))
    def task(job):return {'id':job['task_id'],'repository':'fixture/project','dataset':'withmartian/code-review-benchmark'}
    monkeypatch.setattr(module,'_task',lambda p,j:task(j))
    queue=tmp_path/'queue';queue.mkdir();state=queue/'primary-long-state.json';state.write_text('{"status":"running"}')
    source=tmp_path/'raw';source.mkdir()
    def attempt(index,name,ended,status='completed',calls=5):
        job=jobs[index];root=source/f'job-{index:03}'/name;root.mkdir(parents=True)
        model={'backend':'ollama','model':'fixture','digest':'c'*64,'worker_label':'primary'}
        config={**job,'protocol_version':module.PROTOCOL,'registry_freeze_hash':plan['plan_hash'],'source_hash':plan['source_hash'],
                'controller_hash':'d'*64,'model_identity':model,'task_metadata':task(job)}
        events=[]
        for a in range(calls):
            base={'agent_id':f'agent_{a}','round':0,'timestamp_utc':ended}
            answer={'findings':[],'tests_executed':False}
            if job['defense']=='plain' and job['intervention']=='benign_override':answer['audit_marker']='violet lantern'
            events.extend([{**base,'event_type':'http_attempt'}, {**base,'event_type':'inference_requested'},
                           {**base,'event_type':'inference_response'}, {**base,'event_type':'artifact','content':json.dumps(answer)}])
        events.append({'event_type':'run_finished','metadata':{'status':status},'timestamp_utc':ended})
        manifest={'protocol_version':module.PROTOCOL,'plan_hash':plan['plan_hash'],'source_hash':plan['source_hash'],
                  'controller_hash':'d'*64,'source_unchanged_on_exit':True,'model_identity':model,'status':status,
                  'completed_model_calls':calls,'http_attempts':calls,'parse_failures':0,'duration_seconds':10,
                  'graph':study_adjacency('ring',5),'ended_utc':ended}
        for filename,value in [('manifest.json',manifest),('config.snapshot.json',config),('outcome.json',{})]:
            (root/filename).write_text(json.dumps(value))
        (root/'events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in events));seal(root);return root
    paths=[]
    for i in range(8):paths.append(attempt(i,'complete','2026-11-08T09:00:00+00:00' if i==7 else '2026-11-08T08:00:00+00:00'))
    attempt(4,'failed','2026-11-08T07:00:00+00:00','budget_exhausted',1)
    unsealed=source/'job-007'/'unsealed';unsealed.mkdir();(unsealed/'events.jsonl').write_text('{"event_type":"http_attempt"}\n{"event_type":')
    return module,queue,source,paths,state,plan


def test_only_complete_four_arm_blocks_enter_cutoff_and_state_is_untouched(fixture):
    module,queue,source,paths,state,plan=fixture;before=state.read_bytes()
    result=module.analyze(queue,'2026-11-08T08:30:00Z',source)
    assert result['evaluation_runs']==4 and result['case_seed_blocks']==1
    assert len(result['difference_in_differences'])==1 and result['uncertainty']==[]
    assert all(r['task_kind']=='code_review' for r in result['rows'])
    assert result['all_observed_failed_sealed_attempts']==1 and result['all_observed_unsealed_attempts']==1
    assert result['all_observed_recorded_http_attempts']==42 and result['all_observed_sealed_runtime_seconds']==90
    reasons=[r['reason'] for r in result['exclusions']]
    assert 'ended_after_cutoff' in reasons and reasons.count('incomplete_four_arm_block_at_cutoff')==3
    assert result['quality_precision'] is None and 'not_completed_study' in result['study_status']
    assert state.read_bytes()==before


@pytest.mark.parametrize('field,value',[('defense','source_attribution'),('source_hash','e'*64)])
def test_resealed_assignment_or_source_mismatch_is_not_silently_dropped(fixture,field,value):
    module,queue,source,paths,state,plan=fixture;root=paths[0]
    name='config.snapshot.json' if field=='defense' else 'manifest.json'
    data=json.loads((root/name).read_text());data[field]=value;(root/name).write_text(json.dumps(data));seal(root)
    with pytest.raises(ValueError,match='assignment|provenance'):module.analyze(queue,'2026-11-08T08:30:00Z',source)


def test_future_cutoff_and_missing_registered_arm_are_rejected(fixture):
    module,queue,source,paths,state,plan=fixture
    with pytest.raises(ValueError,match='current or past'):module.analyze(queue,'2999-01-01T00:00:00Z',source)
    plan['jobs'][-1]['defense']='plain'
    with pytest.raises(ValueError,match='factorial arm'):module.analyze(queue,'2026-11-08T08:30:00Z',source)
