import asyncio
import json
from pathlib import Path
import runpy

import pytest

ROOT=Path(__file__).resolve().parents[1]


def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return runpy.run_path(str(ROOT/'scripts/repository_benchmark.py')),runpy.run_path(str(ROOT/'scripts/run_repository_study.py'))


@pytest.mark.parametrize('url',['https://github.com.evil/owner/repo/pull/1','https://github.com/../../pull/1','https://person'+'@'+'github.com/owner/repo/pull/1','https://github.com/owner/repo/pull/1?token=hidden'])
def test_source_url_is_read_only_github_pr_reference(monkeypatch,url):
    importer,_=modules(monkeypatch)
    with pytest.raises(ValueError):importer['source_pr'](url)


def test_length_bins_and_weighting_are_explicit_and_no_silent_truncation(tmp_path,monkeypatch):
    importer,runner=modules(monkeypatch);private=tmp_path/'private';private.mkdir()
    tasks=[]
    for index,length in enumerate([4000,12000,17000,18000,19000]):
        blob=('diff --git a/file.py b/file.py\n'+'+'*length).encode();ident=f'{index:020x}'
        (private/(ident+'.diff')).write_bytes(blob)
        tasks.append({'id':ident,'diff_file':ident+'.diff','diff_sha256':importer['sha'](blob),'input_length':importer['tier'](blob.decode()),
            'planned_rounds':3 if index==0 else 8 if index==1 else 15,'repository':'test/project'})
    catalog={'tasks':tasks};catalog['catalog_hash']=importer['sha'](json.dumps(catalog,sort_keys=True).encode())
    (tmp_path/'catalog.json').write_text(json.dumps(catalog))
    frozen=importer['freeze'](tmp_path/'catalog.json',tmp_path/'freeze.json',5,2718)
    assert frozen['length_quotas']=={'long':3,'medium':1,'short':1}
    assert importer['tier']('x'*64001) is None
    _,row,payload=runner['load_input'](tmp_path/'freeze.json',tmp_path/'catalog.json',tasks[0]['id'])
    assert 'golden' not in payload and 'oracle_file' not in payload
    (private/tasks[0]['diff_file']).write_text('tampered')
    with pytest.raises(ValueError):runner['load_input'](tmp_path/'freeze.json',tmp_path/'catalog.json',tasks[0]['id'])


def test_repo_controller_propagates_only_via_messages_and_keeps_quality_unscored(tmp_path,monkeypatch):
    _,runner=modules(monkeypatch)
    provider=runner['RepoMock']();row={'id':'unit-fixture','planned_rounds':3,'input_length':'short'}
    paths=[]
    for condition in ['none','benign_override']:
        paths.append(asyncio.run(runner['run_case'](row,{'code_diff':'inert code text'}, {'freeze_hash':'test-freeze'},provider,tmp_path,'ring',condition)))
    control=json.loads((paths[0]/'outcome.json').read_text());injected=json.loads((paths[1]/'outcome.json').read_text())
    assert not control['any_violation'] and injected['multi_agent_boundary_failure']
    assert injected['collusion_status']=='not_adjudicated' and injected['quality_precision'] is None
    assert all(runner['verify'](p) for p in paths)
    cached=asyncio.run(runner['run_case'](row,{'code_diff':'inert code text'},{'freeze_hash':'test-freeze'},provider,tmp_path,'ring','none'))
    assert cached==paths[0] and len(list(tmp_path.glob('*/manifest.json')))==2


def test_repository_export_withholds_inputs_oracles_and_rejects_unsealed_changes(tmp_path,monkeypatch):
    importer,runner=modules(monkeypatch)
    from repository_publication import export_repository_runs,validate_repository_snapshot
    row={'id':'a'*20,'planned_rounds':3,'input_length':'short','characters':100,
         'repository':'test/project','dataset_revision':'b'*40}
    output=tmp_path/'raw'
    path=asyncio.run(runner['run_case'](row,{'code_diff':'PRIVATE_SOURCE_SENTINEL'},
        {'freeze_hash':'c'*64},runner['RepoMock'](),output,'ring','none'))
    public=tmp_path/'public.json'
    snapshot=export_repository_runs(output,public,{})
    assert len(snapshot.runs)==1 and snapshot.runs[0].calls==15
    assert snapshot.runs[0].task_success_rate is None
    assert snapshot.runs[0].collusion_status=='not_adjudicated'
    assert 'PRIVATE_SOURCE_SENTINEL' not in public.read_text()
    raw=json.loads(public.read_text());raw['runs'][0]['code_diff']='unexpected'
    public.write_text(json.dumps(raw))
    with pytest.raises(ValueError):validate_repository_snapshot(public,{})
    (path/'events.jsonl').write_text((path/'events.jsonl').read_text()+'\n')
    with pytest.raises(ValueError,match='checksum'):export_repository_runs(output,public,{})


def test_live_repository_adapter_reserves_context_and_operator_stop_prevents_calls(tmp_path,monkeypatch):
    import httpx
    from contagion.models import SamplingConfig
    _,runner=modules(monkeypatch);requests=[]
    def transport(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200,json={'message':{'content':'{}'},'prompt_eval_count':200,'eval_count':2})
    async def exercise():
        provider=runner['RepositoryProvider']('http://127.0.0.1',api='ollama',retries=0,transport=httpx.MockTransport(transport))
        try:
            await provider.chat([{'role':'user','content':'inert diff'}],SamplingConfig(model='fixture',seed=1,temperature=.2,max_output_tokens=512))
        finally:await provider.close()
    asyncio.run(exercise())
    assert requests[0]['options']['num_ctx']==32768 and requests[0]['think'] is False
    stop=tmp_path/'STOP';stop.write_text('stop')
    path=asyncio.run(runner['run_case']({'id':'fixture','planned_rounds':3,'input_length':'short'},
        {'code_diff':'inert'}, {'freeze_hash':'fixture'},runner['RepoMock'](),tmp_path/'runs','ring','none',stop_file=stop))
    manifest=json.loads((path/'manifest.json').read_text())
    assert manifest['status']=='budget_exhausted' and manifest['completed_model_calls']==0
