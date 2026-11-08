import asyncio
import importlib
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return importlib.import_module('primary_long_queue'),importlib.import_module('primary_repository_runner')


def catalog(tmp_path,long_count=8):
    from contagion.config import digest
    from repository_benchmark import sha
    private=tmp_path/'private';private.mkdir()
    rows=[]
    for index in range(long_count+1):
        blob=('diff --git a/item.py b/item.py\n+value='+str(index)).encode();ident=f'{index+1:020x}'
        (private/(ident+'.diff')).write_bytes(blob)
        rows.append({'id':ident,'diff_file':ident+'.diff','diff_sha256':sha(blob),'input_length':'short' if index==0 else 'long',
                     'repository':'fixture/project','dataset_revision':'b'*40,'characters':len(blob),'planned_rounds':3 if index==0 else 15})
    data={'tasks':rows};data['catalog_hash']=sha(json.dumps(data,sort_keys=True).encode());path=tmp_path/'catalog.json';path.write_text(json.dumps(data));return path


def test_frozen_long_matrix_has_eight_cases_and_balanced_cells(tmp_path,modules):
    queue,_=modules;source=catalog(tmp_path)
    plan=queue.prepare(tmp_path/'queue',source,'fixture','a'*64,None)
    assert plan['planned_runs']==68 and plan['planned_calls']==4860
    main=[j for j in plan['jobs'] if j['phase']=='evaluation'];assert len({j['task_id'] for j in main})==8
    assert {j['rounds'] for j in main}=={15} and {j['topology'] for j in main}=={'ring'}
    for case in {j['task_id'] for j in main}:
        cells=[j for j in main if j['task_id']==case]
        assert len(cells)==8 and {j['defense'] for j in cells}=={'plain','source_attribution'}
        assert {j['intervention'] for j in cells}=={'none','benign_override'}
    queue.validate_plan(tmp_path/'queue')
    data=json.loads((tmp_path/'queue/primary-long-plan.json').read_text());data['max_http_attempts']=99999
    (tmp_path/'queue/primary-long-plan.json').write_text(json.dumps(data))
    with pytest.raises(ValueError,match='plan changed'):queue.validate_plan(tmp_path/'queue')


def test_attribution_is_recorded_in_actual_request_and_only_mock_defense_effect(tmp_path,modules):
    queue,runner=modules;source=catalog(tmp_path,1);plan=queue.prepare(tmp_path/'queue',source,'fixture','a'*64,None,case_count=1,seeds=(21001,))
    assert runner.peer_view([{'sender':'agent_3','source_round':2,'content':'peer text'}],'plain')==['peer text']
    results={}
    for defense in ['plain','source_attribution']:
        job=next(j for j in plan['jobs'] if j['phase']=='integration_precheck' and j['defense']==defense and j['intervention']=='benign_override')
        row,payload=queue.load_payload(plan,job)
        path=asyncio.run(runner.run_case(row,payload,plan,job,runner.AttributedMock(),tmp_path/defense))
        from contagion.storage import verify
        assert verify(path)
        results[defense]=json.loads((path/'outcome.json').read_text())
        events=[json.loads(line) for line in (path/'events.jsonl').read_text().splitlines()]
        if defense=='source_attribution':
            request=next(e for e in events if e['event_type']=='inference_requested' and e['round']==1)
            visible=json.dumps(request['metadata']['messages'])
            assert 'controller_source' in visible and 'untrusted_peer_data' in visible
            assert runner.ATTRIBUTION_RULE in request['metadata']['messages'][0]['content']
    assert results['plain']['any_violation'] and not results['source_attribution']['any_violation']
    assert all(r['quality_precision'] is None and r['collusion_status']=='not_adjudicated' for r in results.values())


def test_mock_queue_explicit_resume_skips_sealed_work_and_preserves_budgets(tmp_path,modules,monkeypatch):
    queue,_=modules;source=catalog(tmp_path,1);plan=queue.prepare(tmp_path/'queue',source,'fixture','a'*64,None,case_count=1,seeds=(21001,))
    hashes=queue.dependency_hashes();monkeypatch.setattr(queue,'ROOT',tmp_path);monkeypatch.setattr(queue,'dependency_hashes',lambda:hashes)
    first=asyncio.run(queue.run(tmp_path/'queue'));assert first['status']=='completed' and first['completed_runs']==8
    output=tmp_path/'results/repository-runs/queue';before={str(p):p.read_bytes() for p in output.rglob('events.jsonl')}
    with pytest.raises(ValueError,match='explicit'):asyncio.run(queue.run(tmp_path/'queue'))
    second=asyncio.run(queue.run(tmp_path/'queue',resume=True));assert second['resume_count']==1 and second['completed_runs']==8
    assert before=={str(p):p.read_bytes() for p in output.rglob('events.jsonl')}
    assert second['physical_calls']==0 and second['returned_calls']==360


def test_partial_failed_attempts_consume_physical_budget_without_repair(tmp_path,modules):
    queue,_=modules;run=tmp_path/'job-000'/'attempt-001';run.mkdir(parents=True)
    event={'event_type':'http_attempt'};blob=json.dumps(event)+'\n'+json.dumps({'event_type':'inference_response'})+'\n{"incomplete":'
    (run/'events.jsonl').write_text(blob)
    recovered=queue.recover(tmp_path)
    assert recovered['physical_calls']==1 and recovered['returned_calls']==1 and recovered['failed_runs']==1
    assert (run/'events.jsonl').read_text()==blob
    (run/'manifest.json').write_text('{"status":"failed"}')
    assert queue.recover(tmp_path)['failed_runs']==1  # Interrupted before sealing is retained, not repaired.


def test_bad_source_and_oversized_queue_budget_are_rejected(tmp_path,modules):
    queue,_=modules;source=catalog(tmp_path)
    with pytest.raises(ValueError,match='cap'):queue.prepare(tmp_path/'large',source,'fixture','a'*64,None,max_http_attempts=6001)
    data=json.loads(source.read_text());diff=source.parent/'private'/data['tasks'][1]['diff_file'];diff.write_text('changed')
    with pytest.raises(ValueError,match='integrity'):queue.prepare(tmp_path/'changed',source,'fixture','a'*64,None)


def test_primary_safeguard_publication_is_numeric_and_retains_protocol(tmp_path,modules):
    queue,runner=modules;source=catalog(tmp_path,1);plan=queue.prepare(tmp_path/'queue',source,'fixture','a'*64,None,case_count=1,seeds=(21001,))
    job=next(j for j in plan['jobs'] if j['phase']=='evaluation' and j['defense']=='source_attribution' and j['intervention']=='none')
    # A short software fixture tests the same exporter without 75 unnecessary mock calls.
    job={**job,'rounds':3};row,payload=queue.load_payload(plan,job)
    provider=runner.AttributedMock();provider.identity={**provider.identity,'worker_label':'primary'}
    path=asyncio.run(runner.run_case(row,payload,plan,job,provider,tmp_path/'runs'))
    from repository_publication import export_repository_runs,private_detail
    snapshot=export_repository_runs(tmp_path/'runs',tmp_path/'public.json',{})
    assert len(snapshot.runs)==1
    exported=snapshot.runs[0]
    assert exported.protocol=='3.3-repository-safeguard' and exported.worker_label=='primary'
    assert exported.defense=='source_attribution' and exported.split=='evaluation'
    assert exported.task_success_rate is None and exported.benchmark_quality_status=='not_scored'
    assert 'code_diff' not in (tmp_path/'public.json').read_text()
    detail=private_detail(tmp_path/'runs',exported.id,{})
    assert detail['traces'] and 'controller-attributed' in detail['task_instruction']
