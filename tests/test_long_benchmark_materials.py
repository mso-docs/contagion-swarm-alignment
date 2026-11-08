import copy
import importlib
import json
from pathlib import Path

import httpx
import pytest


@pytest.fixture
def materials(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    m=importlib.import_module('long_benchmark_materials');out=tmp_path/'materials';(out/'private').mkdir(parents=True)
    sources=[];tasks=[]
    for dataset in (m.MARTIAN,m.SWE):
        name=('martian' if dataset==m.MARTIAN else 'swe')+'.LICENSE';(out/'private'/name).write_text('MIT License')
        sources.append({'dataset':dataset,'revision':'a'*40,'license_spdx':'MIT','license_file':name,'license_sha256':m.sha(b'MIT License')})
        for i in range(3):
            repo=f'fixture-{i}/'+('review' if dataset==m.MARTIAN else 'issue')
            payload={'repository':repo,'code_diff':'diff --git a/a.py b/a.py\n'+'x'*17000} if dataset==m.MARTIAN else {
                'repository':repo,'problem_statement':'Diagnose the supplied issue','source_files':[{'path':'a.py','content':'x'*17000,'sha256':'1'*64,'first_line':1,'last_line':1}],'context_policy':'reference_localized_base_windows'}
            row=m.make_task(out,dataset,'a'*40,repo,i,'b'*40,payload,{'hidden_reference':'NEVER_SEND_REFERENCE'},'test_fixture',{'a.py':'1'*64},'test_reference')
            row.update(prior_exposure=False,prior_project_exposure=False);tasks.append(row)
    split=m.project_splits(tasks)
    for row in tasks:row['split']=split[row['project_group']]
    data={'schema_version':'long-benchmark-materials-1.0','sources':sources,'tasks':tasks,'agent_tools':[],'upstream_execution':False,'official_benchmark_score':False}
    data['catalog_hash']=m.catalog_hash(data);m.write(out/'catalog.json',data)
    return m,out/'catalog.json',data


def save(m,path,data):
    data['catalog_hash']=m.catalog_hash({k:v for k,v in data.items() if k!='catalog_hash'})
    path.write_bytes(m.canonical(data))


def test_static_loader_never_returns_hidden_reference(materials):
    m,path,data=materials;assert len(m.validate_catalog(path)['tasks'])==6
    for row in data['tasks']:
        payload=m.load_task(path,row)
        assert 'NEVER_SEND_REFERENCE' not in json.dumps(payload)
        assert 'oracle_file' not in payload


def test_source_oracle_and_split_tampering_stops(materials):
    m,path,data=materials
    row=data['tasks'][0];source=path.parent/'private'/row['input_file'];source.write_text('{}')
    with pytest.raises(ValueError,match='integrity'):m.validate_catalog(path)


def test_split_is_project_disjoint_and_order_independent(materials):
    m,path,data=materials
    assert m.project_splits(data['tasks'])==m.project_splits(list(reversed(data['tasks'])))
    changed=copy.deepcopy(data);changed['tasks'][0]['split']='heldout' if changed['tasks'][0]['split']!='heldout' else 'train';save(m,path,changed)
    with pytest.raises(ValueError,match='deterministic split'):m.validate_catalog(path)


def test_hidden_nested_fields_are_rejected_even_with_new_hash(materials):
    m,path,data=materials;row=next(r for r in data['tasks'] if r['task_kind']=='issue_diagnosis')
    source=path.parent/'private'/row['input_file'];payload=json.loads(source.read_text());payload['source_files'][0]['oracle']='hidden'
    source.write_bytes(m.canonical(payload));row['input_sha256']=m.sha(source.read_bytes());save(m,path,data)
    with pytest.raises(ValueError,match='source-document'):m.validate_catalog(path)


def test_redirect_private_host_is_never_contacted():
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'));m=importlib.import_module('long_benchmark_materials');seen=[]
    def handler(request):
        seen.append(str(request.url));return httpx.Response(302,headers={'location':'http://127.0.0.1/private'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError,match='Unapproved'):m.bounded_get(client,'https://huggingface.co/test')
    assert seen==['https://huggingface.co/test']


def test_long_material_budget_never_pads_or_truncates_fixture(materials):
    m,path,_=materials
    with pytest.raises(ValueError,match='long_input_budget'):
        m.make_task(path.parent,m.MARTIAN,'a'*40,'fixture/new',999,'b'*40,{'repository':'fixture/new','code_diff':'short'}, {},'fixture',{},'fixture')


def test_known_fork_aliases_never_inflate_project_independence(materials):
    m,path,data=materials
    assert m.canonical_project('AI-Code-Review-Evaluation/sentry-greptile.git')=='getsentry/sentry'
    assert m.canonical_project('ai-code-review-evaluation/keycloak-greptile')=='keycloak/keycloak'
    with pytest.raises(ValueError,match='Unreviewed'):m.canonical_project('ai-code-review-evaluation/new-fork')
    data['project_aliases']=m.PROJECT_ALIASES
    data['tasks'][0]['source_repository']='ai-code-review-evaluation/sentry-greptile';save(m,path,data)
    with pytest.raises(ValueError,match='canonical project'):m.validate_catalog(path)


def test_two_project_source_uses_dev_and_heldout_without_fabricated_train(materials):
    m,_,_=materials
    rows=[{'dataset':m.MARTIAN,'project_group':x} for x in ('fixture/a','fixture/b')]
    assert set(m.project_splits(rows).values())=={'dev','heldout'}
