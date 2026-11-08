import asyncio
import importlib
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def judge(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return importlib.import_module('judge_repository_quality')


def dataset(tmp_path,judge,findings=2,code='diff --git a/a b/a\n+unsafe_value=1\n'):
    queue=tmp_path/'results/reviews/workspaces/quality-long';queue.mkdir(parents=True)
    raw={'schema_version':'repository-quality-1.1','samples':[{'sample_id':'sample','diff':code,'golden':[{'comment':'same concrete issue'}],
         'findings':[{'path':'a','line':1,'description':'candidate issue'} for _ in range(findings)]}]}
    source=queue/'quality_inputs.private.json';source.write_text(json.dumps(raw));(queue/'human_quality.csv').write_text('HUMAN FILE MUST NOT CHANGE\n')
    receipt=tmp_path/'results/finalizer/primary_long.receipt.private.json';receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps({'stage':'primary_long','status':'completed','output_sha256':{str(source.relative_to(tmp_path)):judge.sha(source)}}))
    env=tmp_path/'.env.primary';env.write_text('CONTAGION_BASE_URL=http://127.0.0.1:11835\n')
    return queue,receipt,env,raw['samples'][0]


def parsed(job,verdict='matched'):
    return {'judgments':[{'finding_index':i,'verdict':verdict,'golden_index':0 if verdict=='matched' else None,'reason':'Visible supported issue.',
                         'evidence':[f'finding:{i}',job['code_id'],*(['golden:0'] if verdict=='matched' else [])],'confidence':.5} for i in range(len(job['findings']))]}


class FakeProvider:
    def __init__(self,model,digest,bad_first=False):self.identity={'backend':'ollama'};self.model=model;self.digest=digest;self.audit=None;self.calls=0;self.bad_first=bad_first
    async def discover(self):return [{'name':self.model,'digest':self.digest}]
    async def close(self):pass
    async def chat(self,messages,config):
        from contagion.models import ModelResponse
        assert config.max_output_tokens==1536 and config.thinking=='disabled'
        if self.audit:self.audit('http_attempt',{})
        self.calls+=1
        if self.bad_first and self.calls==1:return ModelResponse(content='INVALID JSON',metadata={'done_reason':'stop'})
        payload=json.loads(messages[1]['content']);job={'findings':payload['findings'],'code_id':payload['code_part']['evidence_id']}
        return ModelResponse(content=json.dumps(parsed(job)),metadata={'done_reason':'stop','prompt_eval_count':1000})


def capacity():return {'available_ram_gib':64,'cpu_temperature_c':[35],'gpu_thermal':[{'temperature_c':35}]}


def test_utf8_chunks_cover_entire_code_and_respect_context_upper_bound(judge):
    sample={'sample_id':'x','diff':'📘a\n'*12000,'golden':[{'issue':'example'}],'findings':[{'description':'candidate'}]}
    parts=judge.split_code(sample)
    assert len(parts)>1 and parts[0]['start']==0 and parts[-1]['end']==len(sample['diff'])
    assert all(p['code_text']==sample['diff'][p['start']:p['end']] and judge.context_upper_bound(p)<=32768-1536 for p in parts)
    assert all(a['end']>=b['start'] and a['end']<b['end'] for a,b in zip(parts,parts[1:]))


def test_semantic_judgment_requires_exact_indices_and_valid_evidence(judge):
    job=judge.split_code({'sample_id':'x','diff':'code','golden':[{}],'findings':[{},{}]})[0]
    result=parsed(job);judge.validate_judgment(result,job)
    result['judgments'][1]['finding_index']=0
    with pytest.raises(ValueError):judge.validate_judgment(result,job)
    result=parsed(job);result['judgments'][0]['evidence'].append('invented:0')
    with pytest.raises(ValueError,match='evidence'):judge.validate_judgment(result,job)
    result=parsed(job);result['judgments'][0]['golden_index']=1
    with pytest.raises(ValueError,match='golden'):judge.validate_judgment(result,job)


def test_duplicate_golden_matches_count_once_and_empty_rows_unjudged(judge,tmp_path):
    queue,receipt,_,_=dataset(tmp_path,judge);output=tmp_path/'results/reviews/judge'
    plan=judge.prepare(queue,receipt,output,judge.MODEL,'a'*64,root=tmp_path)
    cached={j['id']:judge.validate_judgment(parsed(j),j) for j in plan['jobs']};result=judge.aggregate(plan,cached)
    row=result['rows'][0]
    assert row['matched_unique_goldens']==1 and row['provisional_golden_recall']==1 and row['provisional_precision']==.5
    assert result['human_labels_generated']==0 and not row['human_confirmed']
    empty={**plan,'sample_plan':[{'sample_id':'empty','finding_count':0,'golden_count':1,'job_ids':[],'status':'empty_findings_not_judged'}]}
    row=judge.aggregate(empty,{})['rows'][0]
    assert row['provisional_golden_recall'] is None and not row['human_confirmed']


def test_local_run_persists_responses_and_resume_does_not_reset_budget(judge,tmp_path):
    queue,receipt,env,_=dataset(tmp_path,judge);output=tmp_path/'results/reviews/judge'
    plan=judge.prepare(queue,receipt,output,judge.MODEL,'a'*64,root=tmp_path);fake=FakeProvider(judge.MODEL,'a'*64,bad_first=True)
    before=(queue/'human_quality.csv').read_bytes()
    with pytest.raises(ValueError):asyncio.run(judge.run(output,env,root=tmp_path,provider_factory=lambda *args,**kwargs:fake,capacity_reader=capacity))
    failed=list((output/'responses').glob('*.json'));assert len(failed)==1;original=failed[0].read_bytes()
    assert json.loads((output/'judge-state.private.json').read_text())['physical_calls']==1
    with pytest.raises(ValueError,match='resume'):asyncio.run(judge.run(output,env,root=tmp_path))
    result=asyncio.run(judge.run(output,env,resume=True,root=tmp_path,provider_factory=lambda *args,**kwargs:fake,capacity_reader=capacity))
    assert result['physical_calls']==2 and result['machine_advisory_completed_rows']==1
    assert failed[0].read_bytes()==original and (queue/'human_quality.csv').read_bytes()==before
    assert len(list((output/'requests').glob('*.json')))==2 and not list(output.rglob('*.csv'))
    def forbidden(*args,**kwargs):pytest.fail('Cached resume must not create an inference provider')
    cached=asyncio.run(judge.run(output,env,resume=True,root=tmp_path,provider_factory=forbidden))
    assert cached['physical_calls']==2
    with pytest.raises(ValueError,match='already allocated'):judge.prepare(queue,receipt,tmp_path/'results/reviews/another',judge.MODEL,'a'*64,root=tmp_path)


def test_context_budget_selection_keeps_rows_wholly_unreviewed(judge,tmp_path):
    queue,receipt,_,_=dataset(tmp_path,judge,code='code\n'*12000);output=tmp_path/'results/reviews/judge'
    plan=judge.prepare(queue,receipt,output,judge.MODEL,'a'*64,max_calls=1,max_physical=2,root=tmp_path)
    assert plan['planned_calls']==0 and plan['sample_plan'][0]['status']=='unreviewed_complete_chunk_call_budget'
    assert judge.aggregate(plan,{})['rows'][0]['provisional_precision'] is None


def test_finalizer_receipt_and_model_pin_required(judge,tmp_path):
    queue,receipt,_,_=dataset(tmp_path,judge);receipt.write_text('{"status":"completed","stage":"primary_long","output_sha256":{}}')
    with pytest.raises(ValueError,match='receipt'):judge.prepare(queue,receipt,tmp_path/'results/reviews/judge',judge.MODEL,'a'*64,root=tmp_path)
    with pytest.raises(ValueError,match='Nemotron'):judge.prepare(queue,receipt,tmp_path/'results/reviews/judge','other-model','a'*64,root=tmp_path)


def test_missing_request_or_changed_cache_fails_before_inference(judge,tmp_path):
    queue,receipt,env,_=dataset(tmp_path,judge);output=tmp_path/'results/reviews/judge'
    plan=judge.prepare(queue,receipt,output,judge.MODEL,'a'*64,root=tmp_path);fake=FakeProvider(judge.MODEL,'a'*64)
    asyncio.run(judge.run(output,env,root=tmp_path,provider_factory=lambda *args,**kwargs:fake,capacity_reader=capacity))
    validated=output/'validated'/(plan['jobs'][0]['id']+'.json');record=json.loads(validated.read_text());record['judgment']['judgments'][0]['reason']='Changed machine advice';validated.write_text(json.dumps(record))
    with pytest.raises(ValueError,match='persisted response'):asyncio.run(judge.run(output,env,resume=True,root=tmp_path))
    (output/record['request_file']).unlink()
    with pytest.raises(ValueError,match='preserved request'):asyncio.run(judge.run(output,env,resume=True,root=tmp_path))
    assert fake.calls==1


def test_conflicting_partial_judgments_abstain(judge,tmp_path):
    queue,receipt,_,_=dataset(tmp_path,judge,findings=1,code='code\n'*12000);output=tmp_path/'results/reviews/judge'
    plan=judge.prepare(queue,receipt,output,judge.MODEL,'a'*64,root=tmp_path);assert len(plan['jobs'])>1
    cached={j['id']:judge.validate_judgment(parsed(j,'matched' if i==0 else 'invalid'),j) for i,j in enumerate(plan['jobs'])}
    row=judge.aggregate(plan,cached)['rows'][0]
    assert row['judgments'][0]['verdict']=='uncertain' and row['provisional_precision'] is None and row['provisional_golden_recall'] is None


def test_physical_budget_is_not_reset_by_explicit_resume(judge,tmp_path):
    queue,receipt,env,_=dataset(tmp_path,judge);output=tmp_path/'results/reviews/judge'
    judge.prepare(queue,receipt,output,judge.MODEL,'a'*64,max_calls=1,max_physical=1,root=tmp_path);fake=FakeProvider(judge.MODEL,'a'*64,bad_first=True)
    with pytest.raises(ValueError):asyncio.run(judge.run(output,env,root=tmp_path,provider_factory=lambda *args,**kwargs:fake,capacity_reader=capacity))
    with pytest.raises(RuntimeError,match='Physical-call budget'):asyncio.run(judge.run(output,env,resume=True,root=tmp_path,provider_factory=lambda *args,**kwargs:fake,capacity_reader=capacity))
    assert fake.calls==1 and judge.physical_count(output/'events.jsonl')==1


def test_empty_dataset_findings_do_not_load_model_or_claim_review(judge,tmp_path):
    queue,receipt,env,_=dataset(tmp_path,judge,findings=0);output=tmp_path/'results/reviews/judge'
    plan=judge.prepare(queue,receipt,output,judge.MODEL,'a'*64,root=tmp_path);assert plan['planned_calls']==0
    def forbidden(*args,**kwargs):pytest.fail('Empty findings must not load a judge')
    result=asyncio.run(judge.run(output,env,root=tmp_path,provider_factory=forbidden))
    assert result['physical_calls']==0 and result['machine_advisory_completed_rows']==0
    assert result['rows'][0]['provisional_golden_recall'] is None and not result['rows'][0]['human_confirmed']
