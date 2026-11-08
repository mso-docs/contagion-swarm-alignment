import importlib
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def finalizer(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return importlib.import_module('research_finalize')


def source_states(module,base,status='completed'):
    for stage in module.registry(base):
        readiness=Path(stage['readiness']);readiness.parent.mkdir(parents=True,exist_ok=True);readiness.write_text(json.dumps({'status':status}))
        for name in stage['sources']:
            path=Path(name);path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('{"tasks":[]}' if path.name=='catalog.json' else '{}')


def fake_execute(stage,base):
    for name in stage['outputs']:
        path=Path(name)
        if path.suffix:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{"fixture":true}')
        else:
            path.mkdir(parents=True);(path/'immutable.json').write_text('{"fixture":true}');(path/'human_labels.csv').write_text('sample_id,behavior,reason\n')
    return {'fixture_only':True,'human_labels_generated':0}


def test_fixed_registry_and_all_terminal_exit(finalizer,tmp_path,monkeypatch):
    source_states(finalizer,tmp_path);directory=tmp_path/'results/finalizer';plan=finalizer.prepare(directory,tmp_path,max_wait_seconds=60,poll_seconds=1)
    assert len(plan['stages'])==3 and plan['script_sha256'] and plan['immutable_source_sha256_at_registration']
    monkeypatch.setattr(finalizer,'execute_stage',fake_execute)
    result=finalizer.run(directory,sleep=lambda _:pytest.fail('No polling after all terminal'))
    assert result['status']=='completed' and all(s['status']=='completed' for s in result['stages'].values())
    assert all((directory/(s['id']+'.receipt.private.json')).exists() for s in plan['stages'])


def test_one_failed_source_does_not_trash_other_stages(finalizer,tmp_path,monkeypatch):
    source_states(finalizer,tmp_path);first=finalizer.registry(tmp_path)[0];Path(first['readiness']).write_text('{"status":"failed"}')
    directory=tmp_path/'results/finalizer';finalizer.prepare(directory,tmp_path,max_wait_seconds=60,poll_seconds=1);monkeypatch.setattr(finalizer,'execute_stage',fake_execute)
    result=finalizer.run(directory)
    assert result['status']=='completed_with_blockers'
    assert result['stages']['primary_rq1']['status']=='blocked'
    assert result['stages']['advisory_triage']['status']==result['stages']['primary_long']['status']=='completed'


def test_unknown_existing_outputs_are_preserved_and_blocked(finalizer,tmp_path,monkeypatch):
    source_states(finalizer,tmp_path);directory=tmp_path/'results/finalizer';plan=finalizer.prepare(directory,tmp_path,max_wait_seconds=60,poll_seconds=1)
    original=Path(plan['stages'][0]['outputs'][0]);original.parent.mkdir(parents=True,exist_ok=True);original.write_text('PRESERVE HUMAN WORK')
    monkeypatch.setattr(finalizer,'execute_stage',fake_execute);result=finalizer.run(directory)
    assert result['stages']['primary_rq1']['status']=='blocked' and original.read_text()=='PRESERVE HUMAN WORK'
    assert result['stages']['advisory_triage']['status']=='completed'


def test_reuse_verifies_immutable_hash_but_preserves_human_csv(finalizer,tmp_path,monkeypatch):
    source_states(finalizer,tmp_path);directory=tmp_path/'results/finalizer';plan=finalizer.prepare(directory,tmp_path,max_wait_seconds=60,poll_seconds=1)
    monkeypatch.setattr(finalizer,'execute_stage',fake_execute);finalizer.run(directory)
    human=Path(plan['stages'][1]['outputs'][0])/'human_labels.csv';human.write_text('Real human editing, preserved\n')
    monkeypatch.setattr(finalizer,'execute_stage',lambda *args:pytest.fail('Completed stage must not rerun'))
    assert finalizer.run(directory)['status']=='completed'
    immutable=Path(plan['stages'][0]['outputs'][0]);immutable.write_text('TAMPERED')
    result=finalizer.run(directory)
    assert result['stages']['primary_rq1']['status']=='blocked' and human.read_text()=='Real human editing, preserved\n'
    assert result['stages']['advisory_triage']['status']=='completed'


def test_wait_budget_and_poll_limit(finalizer,tmp_path):
    source_states(finalizer,tmp_path,status='running');directory=tmp_path/'results/finalizer';finalizer.prepare(directory,tmp_path,max_wait_seconds=2,poll_seconds=1)
    clock=[0];sleeps=[]
    def sleep(seconds):sleeps.append(seconds);clock[0]+=seconds
    result=finalizer.run(directory,now=lambda:clock[0],sleep=sleep)
    assert result['status']=='completed_with_blockers' and sleeps==[1,1]
    assert all(s['reason']=='wait_budget_exhausted' for s in result['stages'].values())
    with pytest.raises(ValueError):finalizer.prepare(tmp_path/'results/invalid',tmp_path,poll_seconds=31)


def test_malformed_source_only_blocks_its_stage(finalizer,tmp_path,monkeypatch):
    source_states(finalizer,tmp_path);directory=tmp_path/'results/finalizer';plan=finalizer.prepare(directory,tmp_path,max_wait_seconds=60,poll_seconds=1)
    Path(plan['stages'][1]['readiness']).write_text('{partial');monkeypatch.setattr(finalizer,'execute_stage',fake_execute)
    result=finalizer.run(directory)
    assert result['stages']['advisory_triage']['reason']=='invalid_source_state'
    assert result['stages']['primary_rq1']['status']==result['stages']['primary_long']['status']=='completed'


def test_registered_input_hash_change_fails_closed(finalizer,tmp_path,monkeypatch):
    source_states(finalizer,tmp_path);directory=tmp_path/'results/finalizer';plan=finalizer.prepare(directory,tmp_path,max_wait_seconds=60,poll_seconds=1)
    Path(plan['stages'][0]['sources'][0]).write_text('{"changed":true}');monkeypatch.setattr(finalizer,'execute_stage',fake_execute)
    result=finalizer.run(directory)
    assert result['stages']['primary_rq1']['status']=='blocked'
    assert result['stages']['advisory_triage']['status']=='completed'


def test_unsealed_long_tails_are_hashed_and_preserved(finalizer,tmp_path,monkeypatch):
    source_states(finalizer,tmp_path);directory=tmp_path/'results/finalizer';plan=finalizer.prepare(directory,tmp_path,max_wait_seconds=60,poll_seconds=1)
    tail=Path(plan['stages'][2]['raw'])/'job-000'/'interrupted'/'events.jsonl';tail.parent.mkdir(parents=True);tail.write_text('{"partial":')
    monkeypatch.setattr(finalizer,'execute_stage',fake_execute);result=finalizer.run(directory)
    assert result['status']=='completed' and tail.read_text()=='{"partial":'
    receipt=json.loads((directory/'primary_long.receipt.private.json').read_text())
    assert any(key.endswith('interrupted/events.jsonl') for key in receipt['source_sha256'])
    tail.write_text('CHANGED TAIL')
    assert finalizer.run(directory)['stages']['primary_long']['status']=='blocked'


def test_runtime_operation_failure_is_isolated(finalizer,tmp_path,monkeypatch):
    source_states(finalizer,tmp_path);directory=tmp_path/'results/finalizer';finalizer.prepare(directory,tmp_path,max_wait_seconds=60,poll_seconds=1)
    def execute(stage,base):
        if stage['id']=='advisory_triage':raise RuntimeError('Fixture runtime failure')
        return fake_execute(stage,base)
    monkeypatch.setattr(finalizer,'execute_stage',execute);result=finalizer.run(directory)
    assert result['stages']['advisory_triage']['status']=='blocked'
    assert result['stages']['primary_rq1']['status']==result['stages']['primary_long']['status']=='completed'


def test_hybrid_frontier_subset_is_registered_and_passed_to_triage(finalizer,tmp_path,monkeypatch):
    import triage_reviews
    source_states(finalizer,tmp_path);directory=tmp_path/'results/finalizer';stage=finalizer.registry(tmp_path)[1]
    frontier=Path(stage['sources'][3]);frontier.write_text(json.dumps({'results':[{'sample_id':str(i)} for i in range(20)]}))
    plan=finalizer.prepare(directory,tmp_path,max_wait_seconds=60,poll_seconds=1)
    assert any(key.endswith('frontier-spotcheck-v2/frontier-results.private.json') for key in plan['immutable_source_sha256_at_registration'])
    captured={}
    def triage(queue,judge,output,limit,root,second_judge):
        captured.update(second_judge=second_judge,limit=limit)
        assert len(json.loads(Path(second_judge).read_text())['results'])==20
        return {'machine_reviewed_samples':64,'human_selected_samples':16}
    monkeypatch.setattr(triage_reviews,'triage',triage)
    result=finalizer.execute_stage(stage,tmp_path)
    assert captured['second_judge']==str(frontier) and captured['limit']==16 and result['human_labels_generated']==0


def test_hybrid_source_missing_blocks_only_advisory_stage(finalizer,tmp_path,monkeypatch):
    source_states(finalizer,tmp_path);directory=tmp_path/'results/finalizer';plan=finalizer.prepare(directory,tmp_path,max_wait_seconds=60,poll_seconds=1)
    Path(plan['stages'][1]['sources'][3]).unlink();monkeypatch.setattr(finalizer,'execute_stage',fake_execute)
    result=finalizer.run(directory)
    assert result['stages']['advisory_triage']['status']=='blocked'
    assert result['stages']['primary_rq1']['status']==result['stages']['primary_long']['status']=='completed'
