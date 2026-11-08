import copy
import importlib
import json
from pathlib import Path

import pytest

from contagion.storage import seal


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    module=importlib.import_module('primary_allocation_release');monkeypatch.setattr(module,'ROOT',tmp_path)
    jobs=[{'task_id':f'{i:020x}','rounds':1,'topology':'ring','seed':10000,'defense':'plain','intervention':'none','phase':'evaluation','calls':5} for i in range(2)]
    plan={'plan_hash':'a'*64,'source_hash':'b'*64,'model':'fixture','model_digest':'c'*64,'jobs':jobs,'planned_runs':2,'max_http_attempts':12,'max_wall_seconds':10}
    queue=tmp_path/'queue';queue.mkdir();source=tmp_path/'results/repository-runs/queue';source.mkdir(parents=True)
    monkeypatch.setattr(module,'_plan',lambda queue:copy.deepcopy(plan))
    state={'status':'stopped','plan_hash':plan['plan_hash'],'execution_seconds':11,'completed_runs':1,'physical_calls':7,'returned_calls':7,'failed_runs':1,'error_type':'RuntimeError'}
    def attempt(index,status,calls,failure=None):
        root=source/f'job-{index:03}'/'attempt-001';root.mkdir(parents=True)
        events=[]
        for i in range(calls):events.extend([{'event_type':'http_attempt'},{'event_type':'inference_response'}, {'event_type':'artifact','round':i//5,'agent_id':f'agent_{i%5}'}])
        events.append({'event_type':'run_finished','metadata':{'status':status,'reason':failure}})
        (root/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
        config={**jobs[index],'protocol_version':'3.3-repository-safeguard','registry_freeze_hash':plan['plan_hash'],'source_hash':plan['source_hash']}
        manifest={'protocol_version':config['protocol_version'],'plan_hash':plan['plan_hash'],'source_hash':plan['source_hash'],'source_unchanged_on_exit':True,
                  'status':status,'failure':failure,'completed_model_calls':calls,'http_attempts':calls,'parse_failures':0,
                  'model_identity':{'backend':'ollama','model':'fixture','digest':'c'*64,'worker_label':'primary'}}
        for name,value in [('manifest.json',manifest),('config.snapshot.json',config),('outcome.json',{})]:(root/name).write_text(json.dumps(value))
        seal(root);return root
    complete=attempt(0,'completed',5);partial=attempt(1,'budget_exhausted',2,'CallBudgetExhausted')
    def save(): (queue/'primary-long-state.json').write_text(json.dumps(state))
    save();return module,queue,source,state,save,complete,partial,plan


def test_expired_partial_release_is_not_old_study_completion(fixture,tmp_path):
    m,q,source,state,save,complete,partial,plan=fixture
    checked=m.inspect(q,source);assert checked['eligible'] and checked['release_kind']=='expired_sealed_allocation'
    receipt=tmp_path/'results/release.private.json';before=(q/'primary-long-state.json').read_bytes()
    result=m.release(q,receipt,source)
    assert result['status']=='allocation_released' and result['old_study_complete'] is False
    assert result['inspection']['completed_runs']==1 and result['inspection']['budget_exhausted_attempts']==1
    assert (q/'primary-long-state.json').read_bytes()==before
    assert m.validate_receipt(q,receipt,source)==result and receipt.stat().st_mode&0o777==0o600
    state['execution_seconds']=12;save()
    with pytest.raises(ValueError,match='changed after release'):m.validate_receipt(q,receipt,source)


def test_ordinary_error_or_unexpired_stop_cannot_release(fixture):
    m,q,source,state,save,complete,partial,plan=fixture
    state['execution_seconds']=9;save();assert not m.inspect(q,source)['eligible']
    state['execution_seconds']=11;save()
    data=json.loads((partial/'manifest.json').read_text());data.update(status='failed',failure='ValueError');(partial/'manifest.json').write_text(json.dumps(data))
    events=[json.loads(x) for x in (partial/'events.jsonl').read_text().splitlines()];events[-1]['metadata']['status']='failed';(partial/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events));seal(partial)
    assert not m.inspect(q,source)['eligible']


def test_counter_corruption_or_duplicate_artifact_blocks_release(fixture):
    m,q,source,state,save,complete,partial,plan=fixture
    state['physical_calls']=6;save()
    with pytest.raises(ValueError,match='ledger'):m.inspect(q,source)
    state['physical_calls']=7;save()
    events=[json.loads(x) for x in (partial/'events.jsonl').read_text().splitlines()];events[5]['agent_id']='agent_0'
    (partial/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events));seal(partial)
    with pytest.raises(ValueError,match='artifact coverage'):m.inspect(q,source)


def test_active_unsealed_tail_is_waiting_and_cannot_be_released(fixture,tmp_path):
    m,q,source,state,save,complete,partial,plan=fixture
    state.update(status='running',execution_seconds=2,completed_runs=1,failed_runs=0,physical_calls=5,returned_calls=5);save()
    (partial/'checksum.sha256').unlink();with_tail=partial/'events.jsonl';with_tail.write_text(with_tail.read_text()+'{"unfinished":')
    result=m.inspect(q,source);assert not result['eligible'] and result['unsealed_attempts']==1
    with pytest.raises(ValueError,match='not eligible'):m.release(q,tmp_path/'results/no.private.json',source)


def test_release_receipt_requires_shared_primary_lease(fixture,tmp_path):
    import fcntl
    m,q,source,state,save,complete,partial,plan=fixture
    path=tmp_path/'results/checkpoint-gates/controller-primary.lock';path.parent.mkdir(parents=True)
    with path.open('a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):m.release(q,tmp_path/'results/busy.private.json',source)
