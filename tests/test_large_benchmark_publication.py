"""Static issue tasks enter shared views without publishing their source or oracle."""
import asyncio
import importlib
import json
from pathlib import Path
import pytest

from contagion.storage import source_fingerprint


def test_issue_diagnosis_publication_and_private_trace(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    runner=importlib.import_module('large_benchmark_runner')
    publication=importlib.import_module('repository_publication')
    row={'id':'a'*20,'dataset':'princeton-nlp/SWE-bench_Verified','dataset_revision':'b'*40,
         'repository':'fixture/project','characters':18000,'input_length':'long','task_kind':'issue_diagnosis',
         'context_selection':'reference_localized_base_windows','oracle_file':'must-stay-private.json'}
    payload={'task_id':row['id'],'repository':row['repository'],'problem_statement':'Explain the behavior.',
             'source_files':[{'path':'sample.py','content':'private source fixture','first_line':1,'last_line':1}]}
    plan={'plan_hash':'c'*64,'source_hash':source_fingerprint(),'dependencies':{'large_benchmark_runner.py':'d'*64},'max_run_seconds':60}
    job={'rounds':3,'topology':'ring','defense':'plain','phase':'integration_precheck','seed':31001,
         'intervention':'none','batch':0,'stage_id':'precheck'}
    source=tmp_path/'runs'
    asyncio.run(runner.run_case(row,payload,plan,job,runner.AttributedMock(),source))
    output=tmp_path/'public.json';snapshot=publication.export_repository_runs(source,output,{})
    assert len(snapshot.runs)==1
    result=snapshot.runs[0]
    assert result.protocol=='3.4-benchmark-static' and result.task_family=='issue_diagnosis'
    assert result.source_dataset==row['dataset'] and result.memory_policy=='original_task_plus_last_two_own_rounds'
    assert result.official_benchmark_score is False and result.task_success_rate is None
    assert 'private source fixture' not in output.read_text() and 'must-stay-private' not in output.read_text()
    detail=publication.private_detail(source,result.id,{})
    assert 'base source windows' in detail['task_input'] and 'not a proposed diff' in detail['task_instruction']
    assert 'private source fixture' not in json.dumps(detail)
    endpoint={'CONTAGION_BASE_URL':'http://127.0.0.1:11835'}
    # Endpoint parsing legitimately returns None username/password values.
    publication.export_repository_runs(source,tmp_path/'with-endpoint.json',endpoint)
    checked=[];original=publication.verify
    def check(path):checked.append(path);return original(path)
    monkeypatch.setattr(publication,'verify',check)
    publication.export_repository_runs(source,output,{})
    assert checked==[]  # Unchanged sealed rows do not repeatedly parse long request logs.
    event_path=next(source.rglob('events.jsonl'));event_path.write_bytes(event_path.read_bytes()+b'\n')
    with pytest.raises(ValueError,match='checksum'):
        publication.export_repository_runs(source,output,{})
    assert len(checked)==1


def test_private_progress_counts_active_calls_without_publishing_unsealed_results(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    service=importlib.import_module('serve_dashboard')
    root=tmp_path/'job-000'/'attempt';root.mkdir(parents=True)
    (root/'events.jsonl').write_text(json.dumps({'event_type':'http_attempt'})+'\n'+json.dumps({'event_type':'inference_response'})+'\n{"event_type":')
    result=service.active_repository_counters(tmp_path)
    assert result=={'completed_runs':0,'physical_calls':1,'active_attempts':1}
