import asyncio
from decimal import Decimal
import importlib
import hashlib
import json
from pathlib import Path

import httpx
import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'));m=importlib.import_module('frontier_review')
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'private_values',lambda root,env:(set(),{}))
    queue=tmp_path/'queue';queue.mkdir();rows=[]
    for i in range(4):
        rows.append({'sample_id':hashlib.sha256(f'fixture-{i}'.encode()).hexdigest()[:16],'task_instruction':'Return public summary','task_input':{'catalog':[]},'round':i%2,
                     'observed_messages':[],'response_event_id':f'event-{i}','response':'{"answer":{}}','context_policy':'No future events'})
    (queue/'review_inputs.json').write_text(json.dumps({'schema_version':'blinded-artifact-audit-1.0','samples':rows}))
    env=tmp_path/'.env.judge';env.write_text('CONTAGION_BASE_URL=https://openrouter.ai/api/v1\nCONTAGION_API_KEY=fixture-only-token\n')
    metadata={'id':m.MODEL,'supported_parameters':['response_format','structured_outputs','reasoning'],'context_length':200000,
              'pricing':{'prompt':'0.000002','completion':'0.00001','request':'0.000001'}}
    ledger=tmp_path/'results/reviews/global-budget.private.json'
    return m,queue,env,metadata,ledger,rows


def transport_for(m,metadata,calls,cost='0.0001',bad_citation=False):
    def handler(request):
        calls.append(request)
        if request.method=='GET':return httpx.Response(200,json={'data':[metadata]})
        body=json.loads(request.content);sample=json.loads(body['messages'][1]['content'])
        review={'behavior':'compliant','evidence_event_ids':['absent'] if bad_citation else [sample['final_event_id']],
                'rubric_reason':'Visible task behavior','confidence':.5,'needs_human_review':True}
        return httpx.Response(200,json={'model':m.MODEL,'choices':[{'finish_reason':'stop','message':{'content':json.dumps(review)}}],
                                       'usage':{'prompt_tokens':100,'completion_tokens':50,'cost':cost}})
    return httpx.MockTransport(handler)


def test_default_dry_run_never_contacts_network_or_creates_budget(setup,tmp_path):
    m,queue,env,metadata,ledger,_=setup;calls=[]
    result=asyncio.run(m.execute_review(queue,tmp_path/'results/batch',env,usd_cap='20',ledger_file=ledger,transport=transport_for(m,metadata,calls)))
    assert result['status']=='offline_dry_run' and result['network_calls']==0 and not calls
    assert not ledger.exists() and not (tmp_path/'results/batch').exists()


def test_exact_model_strict_schema_private_routing_and_cache(setup,tmp_path):
    m,queue,env,metadata,ledger,_=setup;calls=[];out=tmp_path/'results/batch'
    result=asyncio.run(m.execute_review(queue,out,env,execute=True,usd_cap='20',max_calls=2,ledger_file=ledger,transport=transport_for(m,metadata,calls)))
    assert result['completed_calls']==2
    assert str(calls[0].url)=='https://openrouter.ai/api/v1/models'
    posts=[r for r in calls if r.method=='POST'];assert len(posts)==2
    for request in posts:
        body=json.loads(request.content)
        assert body['model']==m.MODEL and all(body['provider'][k]==v for k,v in m.PROVIDER.items())
        assert body['provider']['max_price']=={'prompt':2.5,'completion':12.5,'request':.00000125}
        assert body['response_format']['json_schema']['strict'] is True and 'tools' not in body
        assert 'temperature' not in body  # Sonnet5.5 does not advertise this parameter.
        assert body['max_tokens']==4096
        assert body['reasoning']=={'effort':'low','exclude':True}
    recorded=json.loads(ledger.read_text());assert len(recorded['entries'])==2
    assert sum(Decimal(e['budget_debit_usd']) for e in recorded['entries'])==Decimal('.0002')
    before=len(calls)
    cached=asyncio.run(m.execute_review(queue,out,env,execute=True,usd_cap='20',max_calls=2,resume=True,ledger_file=ledger,transport=transport_for(m,metadata,calls)))
    assert cached['status']=='cached_complete' and len(calls)==before
    assert 'fixture-only-token' not in '\n'.join(p.read_text() for p in out.glob('*.json'))


def test_budget_preflight_rejects_batch_before_paid_post(setup,tmp_path):
    m,queue,env,metadata,ledger,_=setup;calls=[]
    with pytest.raises(ValueError,match='Batch exceeds'):
        asyncio.run(m.execute_review(queue,tmp_path/'results/batch',env,execute=True,usd_cap='.000001',max_calls=2,ledger_file=ledger,transport=transport_for(m,metadata,calls)))
    assert len(calls)==1 and calls[0].method=='GET'
    assert json.loads(ledger.read_text())['entries']==[]


def test_missing_exact_model_has_no_fallback(setup,tmp_path):
    m,queue,env,metadata,ledger,_=setup;calls=[];metadata={**metadata,'id':'different/model'}
    with pytest.raises(ValueError,match='unavailable'):
        asyncio.run(m.execute_review(queue,tmp_path/'results/batch',env,execute=True,usd_cap='20',ledger_file=ledger,transport=transport_for(m,metadata,calls)))
    assert all(r.method=='GET' for r in calls)


def test_privacy_scrub_and_hidden_future_evidence_rejected_before_network(setup,tmp_path):
    m,queue,env,metadata,ledger,rows=setup
    row={**rows[0],'response':'Contact reader@example.com'}
    safe,count=m.strict_sample(row,{})
    assert 'reader@example.com' not in json.dumps(safe) and count>0
    with pytest.raises(ValueError,match='Unexpected'):m.strict_sample({**rows[0],'oracle':True},{})
    future={**rows[0],'observed_messages':[{'event_id':'future','round':99,'content':'hidden'}]}
    with pytest.raises(ValueError,match='future'):m.strict_sample(future,{})


def test_global_ledger_cannot_be_reset_for_later_batch(setup,tmp_path):
    m,queue,env,metadata,ledger,rows=setup;calls=[]
    plan,samples=m.build_plan(rows,{},max_calls=1,usd_cap='20')
    reservation=m.reserve_cost(m.payload(samples[0],4096,True),m.prices(metadata))[1];cap=reservation*Decimal('1.5');actual=reservation*Decimal('.9')
    first=asyncio.run(m.execute_review(queue,tmp_path/'results/first',env,execute=True,usd_cap=str(cap),max_calls=1,ledger_file=ledger,transport=transport_for(m,metadata,calls,str(actual))))
    assert first['status']=='completed'
    posts=sum(r.method=='POST' for r in calls)
    with pytest.raises(ValueError,match='remaining USD cap'):
        asyncio.run(m.execute_review(queue,tmp_path/'results/second',env,execute=True,usd_cap=str(cap),max_calls=1,ledger_file=ledger,transport=transport_for(m,metadata,calls,str(actual))))
    assert sum(r.method=='POST' for r in calls)==posts
    with pytest.raises(ValueError,match='cannot reset'):
        asyncio.run(m.execute_review(queue,tmp_path/'results/reset',env,execute=True,usd_cap=str(cap),max_calls=1,ledger_file=tmp_path/'results/reviews/another-ledger.json',transport=transport_for(m,metadata,calls)))


def test_uncertain_paid_attempt_is_reserved_and_never_automatically_retried(setup,tmp_path):
    m,queue,env,metadata,ledger,_=setup;calls=[]
    def handler(request):
        calls.append(request)
        if request.method=='GET':return httpx.Response(200,json={'data':[metadata]})
        raise httpx.ReadTimeout('fixture timeout')
    out=tmp_path/'results/batch'
    with pytest.raises(httpx.ReadTimeout):asyncio.run(m.execute_review(queue,out,env,execute=True,usd_cap='20',max_calls=1,ledger_file=ledger,transport=httpx.MockTransport(handler)))
    entries=json.loads(ledger.read_text())['entries'];assert len(entries)==1 and Decimal(entries[0]['budget_debit_usd'])>0
    assert entries[0]['status']=='failed_or_uncertain'
    before=len(calls)
    with pytest.raises(ValueError,match='operator review'):
        asyncio.run(m.execute_review(queue,out,env,execute=True,usd_cap='20',max_calls=1,resume=True,ledger_file=ledger,transport=httpx.MockTransport(handler)))
    assert len(calls)==before


def test_invalid_citations_stop_after_persisting_response(setup,tmp_path):
    m,queue,env,metadata,ledger,_=setup;calls=[];out=tmp_path/'results/batch'
    with pytest.raises(ValueError,match='absent'):
        asyncio.run(m.execute_review(queue,out,env,execute=True,usd_cap='20',max_calls=2,ledger_file=ledger,transport=transport_for(m,metadata,calls,bad_citation=True)))
    assert sum(r.method=='POST' for r in calls)==1
    assert (out/'response-000.private.json').exists()
    assert json.loads((out/'receipt-000.private.json').read_text())['actual_cost_usd']=='0.0001'


def test_paid_execution_requires_explicit_cap_and_ledger(setup,tmp_path):
    m,queue,env,metadata,ledger,_=setup;calls=[]
    with pytest.raises(ValueError,match='USD cap'):
        asyncio.run(m.execute_review(queue,tmp_path/'results/no-cap',env,execute=True,ledger_file=ledger,transport=transport_for(m,metadata,calls)))
    with pytest.raises(ValueError,match='ledger'):
        asyncio.run(m.execute_review(queue,tmp_path/'results/no-ledger',env,execute=True,usd_cap='20',transport=transport_for(m,metadata,calls)))
    with pytest.raises(ValueError,match='at most20'):
        asyncio.run(m.execute_review(queue,tmp_path/'results/over-cap',env,execute=True,usd_cap='21',ledger_file=ledger,transport=transport_for(m,metadata,calls)))
    assert not calls


def test_metadata_prices_and_reasoning_are_bounded(setup):
    m,queue,env,metadata,ledger,rows=setup
    plan,samples=m.build_plan(rows,{},max_calls=1)
    body=m.payload(samples[0],4096,True)
    rates=m.prices({**metadata,'pricing':{**metadata['pricing'],'internal_reasoning':'.000005'}})
    _,with_reasoning=m.reserve_cost(body,rates)
    _,without_reasoning=m.reserve_cost(body,m.prices(metadata))
    assert with_reasoning>without_reasoning
    optional=m.prices({**metadata,'pricing':{'prompt':'0.000002','completion':'0.00001'}})
    assert optional['request']==0 and m.routing_price_limits(optional)['request']==0
    with pytest.raises(ValueError,match='token prices'):m.prices({**metadata,'pricing':{'prompt':'0'}})
    with pytest.raises(ValueError):m.payload(samples[0],4097)


def test_tampered_raw_response_is_not_reused(setup,tmp_path):
    m,queue,env,metadata,ledger,_=setup;calls=[];out=tmp_path/'results/batch'
    asyncio.run(m.execute_review(queue,out,env,execute=True,usd_cap='20',max_calls=1,ledger_file=ledger,transport=transport_for(m,metadata,calls)))
    path=out/'response-000.private.json';raw=json.loads(path.read_text());raw['choices'][0]['message']['content']='{}';path.write_text(json.dumps(raw))
    before=len(calls)
    with pytest.raises(ValueError,match='integrity'):
        asyncio.run(m.execute_review(queue,out,env,execute=True,usd_cap='20',max_calls=1,resume=True,ledger_file=ledger,transport=transport_for(m,metadata,calls)))
    assert len(calls)==before


def test_optional_request_price_is_explicitly_constrained_at_runtime(setup,tmp_path):
    m,queue,env,metadata,ledger,_=setup;calls=[]
    metadata={**metadata,'pricing':{'prompt':'0.000002','completion':'0.00001'}}
    result=asyncio.run(m.execute_review(queue,tmp_path/'results/batch',env,execute=True,usd_cap='20',max_calls=1,ledger_file=ledger,transport=transport_for(m,metadata,calls)))
    assert result['completed_calls']==1
    body=json.loads(next(r for r in calls if r.method=='POST').content)
    assert body['provider']['max_price']=={'prompt':2.5,'completion':12.5,'request':0.0}
    stored=json.loads((tmp_path/'results/batch/model-metadata.private.json').read_text())
    assert stored['request_fee_advertised'] is False and stored['routing_max_price']['request']==0
    assert 'request' not in stored['pricing']  # Preserve advertised metadata rather than inventing a field.
