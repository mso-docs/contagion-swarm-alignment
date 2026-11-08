"""Opt-in, budget-capped OpenRouter second-opinion review; offline dry-run default.

No model output becomes a human label or ground truth. Failed/uncertain paid
attempts are never retried automatically. All records remain under private results.
"""
import argparse
import asyncio
import fcntl
from decimal import Decimal,InvalidOperation
import json
import os
from pathlib import Path
import random
import re

import httpx

from contagion.config import canonical,digest
from contagion.publication import Redactor,sensitive_values
from contagion.review import ReviewResult,validate_review
from contagion.storage import write_json
from judge_artifact_queue import RUBRIC
from run_campaign import atomic
from run_pilot import ROOT,load_env
from scan_privacy import scan_blob
from security_guard import private_values

MODEL='anthropic/claude-sonnet-5.5'
BASE='https://openrouter.ai/api/v1'
PROVIDER={'data_collection':'deny','zdr':True,'require_parameters':True,'allow_fallbacks':False}
FIELDS={'sample_id','task_instruction','task_input','round','observed_messages','response_event_id','response','context_policy'}
EVENT_FIELDS={'event_id','round','content'}


def money(value):
    try:result=Decimal(str(value))
    except InvalidOperation:raise ValueError('Invalid cost value') from None
    if not result.is_finite() or result<0:raise ValueError('Cost must be finite and nonnegative')
    return result


def strict_sample(row,env):
    if not isinstance(row,dict) or set(row)-FIELDS or not FIELDS-{'context_policy'}<=set(row):raise ValueError('Unexpected blinded sample fields')
    if not isinstance(row['sample_id'],str) or not re.fullmatch(r'[a-f0-9]{16}',row['sample_id']):raise ValueError('Invalid opaque sample ID')
    if type(row['round'])is not int or row['round']<0 or not isinstance(row['observed_messages'],list):raise ValueError('Invalid round/messages')
    if len(row['observed_messages'])>20:raise ValueError('Input message cap exceeded')
    events=[]
    for event in row['observed_messages']:
        if not isinstance(event,dict) or set(event)!=EVENT_FIELDS or type(event['round'])is not int or event['round']>row['round'] or event['round']<0:raise ValueError('Hidden/future fields in reviewer evidence')
        if not isinstance(event['event_id'],str) or not isinstance(event['content'],str):raise ValueError('Invalid evidence strings')
        events.append(dict(event))
    for key in ['task_instruction','response_event_id','response']:
        if not isinstance(row[key],str):raise ValueError('Invalid evidence text')
    events.append({'event_id':row['response_event_id'],'round':row['round'],'content':row['response']})
    if len({e['event_id'] for e in events})!=len(events):raise ValueError('Duplicate event IDs')
    sample={'sample_id':row['sample_id'],'task':{'instruction':row['task_instruction'],'input':row['task_input']},'round':row['round'],'events':events,'final_event_id':row['response_event_id']}
    redact=Redactor(sensitive_values(env))
    def clean(value):
        if isinstance(value,str):return redact(value)
        if isinstance(value,list):return [clean(v) for v in value]
        if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
        if value is None or type(value)in {int,float,bool}:return value
        raise ValueError('Unsupported reviewer input type')
    identifier_pattern=r'(?:[a-f0-9]{20}-attempt-[0-9]{3}:[0-9]{6}|event-[0-9]+)'
    if any(not re.fullmatch(identifier_pattern,e['event_id']) for e in events):raise ValueError('Unapproved opaque evidence identifier')
    # These closed, controller-generated identifiers are hashes/counters, not free text.
    # Redacting digit substrings would corrupt valid citations. Scan them below too.
    safe={'sample_id':sample['sample_id'],'task':clean(sample['task']),'round':sample['round'],
          'events':[{**e,'content':clean(e['content'])} for e in events],'final_event_id':sample['final_event_id']}
    blob=canonical(safe).encode()
    if len(blob)>48000:raise ValueError('Review sample context cap; no silent truncation')
    if scan_blob(blob,public=True,known=sensitive_values(env)):raise ValueError('Privacy gate rejected reviewer input')
    if safe['sample_id']!=sample['sample_id'] or safe['final_event_id']!=sample['final_event_id'] or [e['event_id'] for e in safe['events']]!=[e['event_id'] for e in sample['events']]:raise ValueError('Redaction altered evidence identifiers')
    return safe,redact.count


def select_samples(rows,max_calls=20,seed=20261108,local_results=None,oracle=None):
    if not 1<=max_calls<=20:raise ValueError('Frontier review is capped at20calls')
    ids=[r['sample_id'] for r in rows]
    if len(ids)!=len(set(ids)) or not ids:raise ValueError('Empty/duplicate review queue')
    local={r['sample_id']:r for r in (local_results or {}).get('results',[])}
    if set(local)-set(ids):raise ValueError('Local reviewer sample mismatch')
    ground={r['sample_id']:r for r in (oracle or {}).get('labels',[])}
    if set(ground)-set(ids):raise ValueError('Selection oracle sample mismatch')
    priority=[]
    for row in rows:
        prediction=local.get(row['sample_id']);truth=ground.get(row['sample_id'])
        if prediction and (prediction.get('needs_human_review') or prediction.get('behavior')in {'ambiguous','unscorable'} or truth and (prediction.get('behavior')=='violation')!=bool(truth.get('violation'))):priority.append(row)
    rng=random.Random(seed);rng.shuffle(priority);chosen=priority[:max_calls//2]
    remaining=[r for r in rows if r['sample_id']not in {c['sample_id'] for c in chosen}]
    strata={}
    for row in remaining:strata.setdefault((digest(row['task_instruction']),row['round']),[]).append(row)
    for group in strata.values():rng.shuffle(group)
    keys=list(strata);rng.shuffle(keys)
    while len(chosen)<min(max_calls,len(rows)):
        for key in keys:
            if strata[key] and len(chosen)<max_calls:chosen.append(strata[key].pop())
        keys=[key for key in keys if strata[key]]
        if not keys:break
    rng.shuffle(chosen)
    return chosen


def prices(metadata):
    if metadata.get('id')!=MODEL:raise ValueError('Exact frontier model is unavailable; no alias/fallback')
    supported=set(metadata.get('supported_parameters',[]))
    if not {'response_format','structured_outputs'}&supported:raise ValueError('Selected model does not advertise structured outputs')
    raw=metadata.get('pricing',{})
    if not {'prompt','completion'}<=set(raw):raise ValueError('Missing current token prices')
    return {key:money(raw.get(key,'0')) for key in ['prompt','completion','request','internal_reasoning']}


def payload(sample,max_output_tokens,reasoning=False,price_limits=None):
    if not 128<=max_output_tokens<=4096:raise ValueError('Output ceiling must be128..4096tokens')
    body={'model':MODEL,'messages':[{'role':'system','content':RUBRIC},{'role':'user','content':canonical(sample)}],
            'max_tokens':max_output_tokens,'provider':dict(PROVIDER),
            'response_format':{'type':'json_schema','json_schema':{'name':'artifact_review','strict':True,'schema':ReviewResult.model_json_schema()}}}
    if price_limits is not None:body['provider']['max_price']=dict(price_limits)
    if reasoning:body['reasoning']={'effort':'low','exclude':True}
    return body


def routing_price_limits(rates):
    # Provider max_price token units are USD/million; request units are USD/request.
    # Missing aggregate request pricing is not a verified zero fee: request=0
    # explicitly forbids routing to a positive per-request fee instead.
    return {'prompt':float(rates['prompt']*Decimal('1250000')),'completion':float(rates['completion']*Decimal('1250000')),'request':float(rates['request']*Decimal('1.25'))}


def reserve_cost(body,rates):
    # UTF-8 bytes upper-bound ordinary byte-tokenized content; fixed allowance
    # includes provider chat/schema framing. This is a conservative reservation,
    # not a promise about provider accounting. Actual billed cost is persisted.
    input_bound=len(canonical(body).encode('utf-8'))+2048
    estimate=Decimal(input_bound)*rates['prompt']+Decimal(body['max_tokens'])*(rates['completion']+rates['internal_reasoning'])+rates['request']
    return input_bound,estimate*Decimal('1.25')


def build_plan(rows,env,max_calls=20,max_output_tokens=4096,usd_cap=None,local_results=None,oracle=None):
    chosen=select_samples(rows,max_calls,local_results=local_results,oracle=oracle);safe=[];redactions=0
    for row in chosen:
        sample,n=strict_sample(row,env);safe.append(sample);redactions+=n
    cap=money(usd_cap) if usd_cap is not None else None
    if cap is not None and not cap>0:raise ValueError('USD cap must be positive')
    plan={'schema_version':'frontier-advisory-1.0','model':MODEL,'max_calls':max_calls,'selected_sample_ids':[r['sample_id'] for r in safe],
          'input_hash':digest(safe),'rubric_hash':digest(RUBRIC),'max_output_tokens':max_output_tokens,'usd_cap':str(cap) if cap is not None else None,
          'provider':dict(PROVIDER),'reasoning_policy':'Low effort with reasoning text excluded when metadata advertises reasoning; output ceiling includes generated reasoning.','redaction_replacements':redactions,'selection':'Up to half prioritized disagreements/abstentions; remainder deterministic task-instruction/round-stratified random audit.',
          'limitations':['Uncalibrated model second opinion, never human labels or ground truth.','Selection is enriched and not prevalence representative.','Private-provider routing requirements may make the model unavailable.']}
    # Validate requested output cap even during offline planning.
    for sample in safe:payload(sample,max_output_tokens)
    plan['plan_hash']=digest(plan);return plan,safe


def completed_cache(output,plan,samples):
    path=Path(output)/'frontier-plan.private.json'
    if not path.exists():return [],Decimal('0')
    if json.loads(path.read_text())!=plan:raise ValueError('Existing frontier freeze differs; use a new output root')
    completed=[];debit=Decimal('0')
    for index,sample in enumerate(samples):
        request=Path(output)/f'request-{index:03}.private.json';receipt=Path(output)/f'receipt-{index:03}.private.json'
        if not request.exists():continue
        record=json.loads(request.read_text())
        if record['sample_id']!=sample['sample_id'] or record['request_hash']!=digest(payload(sample,plan['max_output_tokens'],record.get('reasoning_requested',False),record.get('price_limits'))):raise ValueError('Cached sample/request assignment differs')
        if not receipt.exists():raise ValueError('Uncertain prior paid attempt; no automatic retry')
        paid=json.loads(receipt.read_text());debit+=money(paid['budget_debit_usd'])
        if paid['status']!='validated':raise ValueError('Prior paid attempt failed validation; operator review required')
        raw=json.loads((Path(output)/f'response-{index:03}.private.json').read_text())
        if digest(raw)!=paid.get('response_hash'):raise ValueError('Cached raw response integrity mismatch')
        result=validate_review(json.loads(raw['choices'][0]['message']['content']),sample)
        if result.model_dump()!=paid['review']:raise ValueError('Cached parsed review differs from raw response')
        completed.append({'sample_id':sample['sample_id'],**result.model_dump()})
    return completed,debit


class BudgetLedger:
    """One project authorization binds all batches to one ledger and USD ceiling."""
    def __init__(self,path,cap):
        self.path=Path(path).resolve();self.cap=money(cap);self.lock=None
        if not 0<self.cap<=Decimal('20'):raise ValueError('This authorization permits at most20USD total')
        if (ROOT/'results').resolve() not in self.path.parents:raise ValueError('Budget ledger must stay in private results')
    def __enter__(self):
        directory=ROOT/'results/reviews';directory.mkdir(parents=True,exist_ok=True)
        self.lock=(directory/'frontier-budget-authorization.lock').open('a')
        try:
            fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            marker=directory/'frontier-budget-authorization.private.json'
            authorization={'schema_version':'frontier-authorization-1.0','ledger':str(self.path),'usd_cap':str(self.cap),'model':MODEL}
            if marker.exists():
                if json.loads(marker.read_text())!=authorization:raise ValueError('Another ledger/cap cannot reset the existing authorization')
                if not self.path.exists():raise ValueError('Authorized ledger is missing; no automatic budget reset')
            else:
                if self.path.exists():raise ValueError('Unbound existing ledger needs operator review')
                self.path.parent.mkdir(parents=True,exist_ok=True)
                write_json(self.path,{'schema_version':'frontier-budget-1.0','usd_cap':str(self.cap),'model':MODEL,'entries':[]})
                write_json(marker,authorization)
            self.data=json.loads(self.path.read_text())
            if self.data.get('schema_version')!='frontier-budget-1.0' or self.data.get('usd_cap')!=str(self.cap) or self.data.get('model')!=MODEL:raise ValueError('Ledger authorization mismatch')
            if len({e['id'] for e in self.data['entries']})!=len(self.data['entries']):raise ValueError('Duplicate ledger entries')
            if self.spent()>self.cap:raise ValueError('Global review budget already exhausted')
            return self
        except BaseException:
            self.lock.close();raise
    def __exit__(self,*_):
        if self.lock:self.lock.close()
    def spent(self):return sum((money(e['budget_debit_usd']) for e in self.data['entries']),Decimal('0'))
    def reserve(self,ident,sample_id,amount,batch_hash):
        if any(e['id']==ident for e in self.data['entries']):raise ValueError('Prior paid reservation cannot be retried or overwritten')
        if self.spent()+amount>self.cap:raise ValueError('Global USD cap rejects request')
        self.data['entries'].append({'id':ident,'batch_hash':batch_hash,'sample_id':sample_id,'model':MODEL,'reserved_usd':str(amount),'budget_debit_usd':str(amount),'actual_cost_usd':None,'status':'reserved_before_network'})
        atomic(self.path,self.data)
    def receipt(self,ident,receipt):
        entry=next(e for e in self.data['entries'] if e['id']==ident)
        entry.update({k:receipt[k] for k in ['status','budget_debit_usd','actual_cost_usd']})
        atomic(self.path,self.data)


async def execute_review(queue,output,env_file,*,execute=False,usd_cap=None,max_calls=20,max_output_tokens=4096,resume=False,metadata_file=None,local_results_file=None,oracle_file=None,transport=None,ledger_file=None):
    queue=Path(queue);output=Path(output)
    # Configuration is read as data, never sourced. Cloud endpoint is fixed.
    configured=load_env(Path(env_file),{}) if Path(env_file).exists() else {}
    _,private=private_values(ROOT,{})
    env={**private,**configured};rows=json.loads((queue/'review_inputs.json').read_text())['samples']
    local=json.loads(Path(local_results_file).read_text()) if local_results_file else None
    oracle=json.loads(Path(oracle_file).read_text()) if oracle_file else None
    plan,samples=build_plan(rows,env,max_calls,max_output_tokens,usd_cap,local,oracle)
    if not execute:
        result={'status':'offline_dry_run','planned_calls':len(samples),'model':MODEL,'usd_cap':plan['usd_cap'],'network_calls':0,'redaction_replacements':plan['redaction_replacements']}
        if metadata_file:
            metadata=json.loads(Path(metadata_file).read_text());rates=prices(metadata)
            estimates=[reserve_cost(payload(s,max_output_tokens,'reasoning' in metadata.get('supported_parameters',[]),routing_price_limits(rates)),rates)[1] for s in samples]
            result.update(estimated_reserved_usd=str(sum(estimates)),estimate_source='Provided metadata only; live metadata must be fetched before execution')
            if usd_cap is not None and sum(estimates)>money(usd_cap):raise ValueError('Batch exceeds USD cap before any paid request')
        return result
    if usd_cap is None or money(usd_cap)<=0:raise ValueError('Explicit positive USD cap required before paid calls')
    if ledger_file is None:raise ValueError('An explicit shared global budget ledger is required')
    if configured.get('CONTAGION_BASE_URL') not in {None,'',BASE}:raise ValueError('Only the fixed OpenRouter endpoint is allowed')
    key=configured.get('CONTAGION_API_KEY') or os.environ.get('CONTAGION_API_KEY')
    if not key:raise ValueError('Set the API key in private .env.judge; never share it in chat')
    if output.exists() and not resume:raise ValueError('Existing frontier output requires explicit --resume')
    cached,debit=completed_cache(output,plan,samples)
    if len(cached)==len(samples):return {'status':'cached_complete','completed_calls':len(cached),'budget_debit_usd':str(debit),'model':MODEL}
    if (ROOT/'results').resolve() not in output.resolve().parents:raise ValueError('Paid review records must stay in private results')
    output.mkdir(parents=True,exist_ok=True)
    if not (output/'frontier-plan.private.json').exists():write_json(output/'frontier-plan.private.json',plan)
    write_samples=output/'inputs.private.json'
    if not write_samples.exists():write_json(write_samples,{'samples':samples})
    results=list(cached);done={r['sample_id'] for r in cached}
    with BudgetLedger(ledger_file,usd_cap) as ledger:
        async with httpx.AsyncClient(base_url=BASE,headers={'Authorization':'Bearer '+key},timeout=90,follow_redirects=False,transport=transport) as client:
            # This GET is free metadata discovery; no paid POST occurs until all
            # selected requests fit within the remaining budget at current prices.
            response=await client.get('/api/v1/models' if client.base_url.path=='/' else 'models')
            response.raise_for_status();inventory=response.json()
            model=next((r for r in inventory.get('data',[]) if r.get('id')==MODEL),None)
            if model is None:raise ValueError('Pinned frontier model unavailable; no fallback')
            rates=prices(model);metadata={'id':model['id'],'pricing':model['pricing'],'supported_parameters':model.get('supported_parameters',[]),'context_length':model.get('context_length'),'canonical_slug':model.get('canonical_slug'),'created':model.get('created'),'request_fee_advertised':'request' in model['pricing'],'request_fee_policy':'Use advertised request fee if supplied; otherwise constrain provider max_price.request to0 without claiming a verified zero fee.','routing_max_price':routing_price_limits(rates)}
            atomic(output/'model-metadata.private.json',metadata)
            reservations={s['sample_id']:reserve_cost(payload(s,max_output_tokens,'reasoning' in model.get('supported_parameters',[]),routing_price_limits(rates)),rates) for s in samples if s['sample_id']not in done}
            if ledger.spent()+sum(v[1] for v in reservations.values())>money(usd_cap):raise ValueError('Batch exceeds remaining USD cap before any paid request')
            for index,sample in enumerate(samples):
                if sample['sample_id']in done:continue
                if (output/'STOP').exists():raise RuntimeError('Operator stop before paid request')
                body=payload(sample,max_output_tokens,'reasoning' in model.get('supported_parameters',[]),routing_price_limits(rates));input_bound,reserved=reservations[sample['sample_id']]
                context=model.get('context_length')
                if type(context)is not int or input_bound+max_output_tokens>context:raise ValueError('Conservative context bound exceeds model limit')
                if ledger.spent()+reserved>money(usd_cap):raise ValueError('Remaining budget rejected paid request')
                entry_id=digest([str(output.resolve()),plan['plan_hash'],index])
                ledger.reserve(entry_id,sample['sample_id'],reserved,plan['plan_hash'])
                write_json(output/f'request-{index:03}.private.json',{'sample_id':sample['sample_id'],'model':MODEL,'request_hash':digest(body),
                            'reserved_usd':str(reserved),'reasoning_requested':'reasoning' in body,'price_limits':body['provider']['max_price'],'input_token_bound':input_bound,'max_output_tokens':max_output_tokens,'status':'reserved_before_network'})
                receipt={'sample_id':sample['sample_id'],'status':'failed_or_uncertain','reserved_usd':str(reserved),'budget_debit_usd':str(reserved),'actual_cost_usd':None}
                try:
                    response=await client.post('chat/completions',json=body)
                    # Persist raw bodies privately even for failed HTTP/model responses.
                    try:raw=response.json()
                    except ValueError:raw={'unparsed_response':response.text}
                    def redact_response(value):
                        # Preserve numeric billing strings; raw records are private.
                        # Credentials are never retained even if an error body echoes one.
                        if isinstance(value,str):return value.replace(key,'[REDACTED]')
                        if isinstance(value,list):return [redact_response(v) for v in value]
                        if isinstance(value,dict):return {k:redact_response(v) for k,v in value.items()}
                        return value
                    raw=redact_response(raw)
                    write_json(output/f'response-{index:03}.private.json',raw)
                    receipt['response_hash']=digest(raw)
                    response.raise_for_status()
                    if raw.get('model')!=MODEL:raise ValueError('Response model differs from pinned request')
                    usage=raw.get('usage',{});actual=money(usage['cost']) if usage.get('cost')is not None else None
                    receipt.update(usage=usage,actual_cost_usd=str(actual) if actual is not None else None,budget_debit_usd=str(actual if actual is not None else reserved))
                    debit+=actual if actual is not None else reserved
                    if ledger.spent()-reserved+(actual if actual is not None else reserved)>money(usd_cap) or actual is not None and actual>reserved:raise ValueError('Provider cost exceeded reservation; stop before more paid calls')
                    choice=raw['choices'][0]
                    if choice.get('finish_reason')!='stop':raise ValueError('Incomplete frontier response')
                    review=validate_review(json.loads(choice['message']['content']),sample)
                    receipt.update(status='validated',review=review.model_dump());results.append({'sample_id':sample['sample_id'],**review.model_dump()})
                finally:
                    write_json(output/f'receipt-{index:03}.private.json',receipt)
                    ledger.receipt(entry_id,receipt)
                atomic(output/'frontier-results.private.json',{'schema_version':'artifact-judge-1.0','model':MODEL,'calibrated':False,'budget_debit_usd':str(debit),'results':results})
    return {'status':'completed','completed_calls':len(results),'budget_debit_usd':str(debit),'model':MODEL,'calibrated':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path)
    parser.add_argument('--queue',type=Path);parser.add_argument('--out',type=Path);parser.add_argument('--env-file',type=Path);parser.add_argument('--max-calls',type=int);parser.add_argument('--max-output-tokens',type=int);parser.add_argument('--usd-cap');parser.add_argument('--ledger',type=Path);parser.add_argument('--metadata-file',type=Path);parser.add_argument('--local-results',type=Path);parser.add_argument('--oracle-labels',type=Path);parser.add_argument('--execute',action='store_true');parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    try:
        config=json.loads(args.config.read_text()) if args.config else {}
        allowed={'queue','out','env_file','max_calls','max_output_tokens','usd_cap','model','local_results','oracle_labels','ledger'}
        if set(config)-allowed or config.get('model',MODEL)!=MODEL:raise ValueError('Unsupported config/model; execution requires CLI --execute')
        def option(name,default=None):return getattr(args,name,None) if getattr(args,name,None)is not None else config.get(name,default)
        if not option('queue') or not option('out'):raise ValueError('Queue and output paths required')
        result=asyncio.run(execute_review(option('queue'),option('out'),option('env_file','.env.judge'),execute=args.execute,usd_cap=option('usd_cap'),
            max_calls=option('max_calls',20),max_output_tokens=option('max_output_tokens',4096),resume=args.resume,metadata_file=args.metadata_file,
            local_results_file=option('local_results'),oracle_file=option('oracle_labels'),ledger_file=option('ledger')))
        print(json.dumps(result))
    except Exception as exc:parser.exit(1,f'Frontier review stopped ({type(exc).__name__}); no automatic paid retry; inspect private records locally.\n')
