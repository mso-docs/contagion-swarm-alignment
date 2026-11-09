import hashlib
import json
import runpy
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from contagion.config import digest
from contagion.storage import seal

ROOT = Path(__file__).resolve().parents[1]


def api(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return runpy.run_path(str(ROOT/'scripts/final_evidence_inventory.py'))


def source(root, run='same-attempt', status='completed', calls=2):
    root.mkdir()
    (root/'manifest.json').write_text(json.dumps({'run_id':run,'status':status}))
    (root/'config.snapshot.json').write_text('{}')
    (root/'outcome.json').write_text('{}')
    (root/'events.jsonl').write_text(''.join(json.dumps({'event_type':'inference_response','sequence_no':i})+'\n' for i in range(calls)))
    seal(root)
    return root


def entry(module, ident, **extra):
    return module['Entry'](index='research',id=ident,protocol='2.4',model='mock-v1',backend='mock',family='catalog',phase='development',condition='none',status='completed',calls=2,topology='ring',**extra)


def test_lineage_verifies_copies_without_exporting_paths(tmp_path,monkeypatch):
    module=api(monkeypatch)
    a=source(tmp_path/'a'); b=source(tmp_path/'b')
    mapping=module['raw_index'](tmp_path)
    row=module['reconcile'](entry(module,digest('same-attempt')[:16]),mapping)
    assert row.trajectory_hash==hashlib.sha256((a/'events.jsonl').read_bytes()).hexdigest()
    assert row.source_seal and str(tmp_path) not in row.model_dump_json()
    assert len(mapping[digest('same-attempt')[:16]])==2
    assert (b/'events.jsonl').read_bytes()==(a/'events.jsonl').read_bytes()


def test_corrupt_matching_seal_and_counter_disagreement_fail_closed(tmp_path,monkeypatch):
    module=api(monkeypatch); directory=source(tmp_path/'run'); ident=digest('same-attempt')[:16]
    row=entry(module,ident);mapping=module['raw_index'](tmp_path)
    with pytest.raises(ValueError,match='counters'):
        module['reconcile'](row.model_copy(update={'calls':3}),mapping)
    (directory/'outcome.json').write_text('{"changed":true}')
    with pytest.raises(ValueError,match='checksum'):
        module['reconcile'](row,mapping)


def test_unknown_lineage_is_explicit_and_schema_is_closed(monkeypatch):
    module=api(monkeypatch);row=entry(module,'a'*16)
    assert module['reconcile'](row,{}).trajectory_hash is None
    with pytest.raises(ValidationError):
        module['Entry'](**row.model_dump(),request_history='not public')
    with pytest.raises(ValidationError):
        module['Entry'](**{**row.model_dump(),'calls':-1})


def test_different_trajectories_for_one_identifier_rejected(tmp_path,monkeypatch):
    module=api(monkeypatch);source(tmp_path/'a');b=source(tmp_path/'b')
    (b/'events.jsonl').write_text(''.join(json.dumps({'event_type':'inference_response','sequence_no':i,'round':1})+'\n' for i in range(2)))
    seal(b)
    with pytest.raises(ValueError,match='Ambiguous'):
        module['reconcile'](entry(module,digest('same-attempt')[:16]),module['raw_index'](tmp_path))


def test_build_deduplicates_across_indexes_and_excludes_unmatched(tmp_path,monkeypatch):
    module=api(monkeypatch);build=module['build'];scope=build.__globals__
    for name in ['validate_snapshot','validate_research_snapshot','validate_repository_snapshot','validate_followups']:
        monkeypatch.setitem(scope,name,lambda *a,**kw:None)
    raw=tmp_path/'raw';raw.mkdir();source(raw/'run');ident=digest('same-attempt')[:16]
    data=tmp_path/'data';data.mkdir()
    row={'id':ident,'protocol':'2.4','model':'test-model','backend':'ollama','task_family':'catalog','split':'evaluation','intervention':'none','status':'completed','calls':2,'rounds':1,'agent_count':2,'topology':'ring'}
    stamp='2026-11-09T00:00:00+00:00'
    snapshots={'results':{'runs':[]},'research':{'studies':[row,{**row,'id':'f'*16}],'neural':[],'monitor':[],'reviews':[]},'repositories':{'runs':[row]},'followups':{'runs':[],'monitor':[],'reviews':[],'multidomain':[],'diversity':[]}}
    for name,value in snapshots.items():
        (data/f'{name}.json').write_text(json.dumps({'generated_utc':stamp,**value}))
    inventory=build(data,raw)
    assert inventory.counts.indexed_rows==3
    assert inventory.counts.duplicate_index_rows==1
    assert inventory.counts.live_distinct_verified_trajectories==1
    assert inventory.counts.live_distinct_returned_responses==2
    assert inventory.counts.unmatched_rows==1
    output=tmp_path/'inventory.json';output.write_text(inventory.model_dump_json())
    assert module['validate_inventory'](output).counts==inventory.counts
    changed=inventory.model_dump();changed['counts']['indexed_rows']=99
    output.write_text(json.dumps(changed))
    with pytest.raises(ValueError,match='denominator'):
        module['validate_inventory'](output)

    changed=inventory.model_dump();changed['counts']['live_distinct_returned_responses']=1000
    output.write_text(json.dumps(changed))
    with pytest.raises(ValueError,match='derived count'):
        module['validate_inventory'](output)
    output.write_text(inventory.model_dump_json())
    module['validate_inventory'](output,data_root=data)
    (data/'results.json').write_text('{}')
    with pytest.raises(ValueError,match='input changed'):
        module['validate_inventory'](output,data_root=data)


def test_public_inventory_cli_is_read_only_and_refuses_overwrite(monkeypatch,capsys):
    root=ROOT
    monkeypatch.syspath_prepend(str(root/'scripts'))
    path=root/'report/data/final_inventory.json'
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(sys,'argv',['final_evidence_inventory.py','--validate-only'])
    runpy.run_path(str(root/'scripts/final_evidence_inventory.py'),run_name='__main__')
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    monkeypatch.setattr(sys,'argv',['final_evidence_inventory.py'])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(root/'scripts/final_evidence_inventory.py'),run_name='__main__')
    assert exc.value.code==2
    assert 'never overwritten' in capsys.readouterr().err
