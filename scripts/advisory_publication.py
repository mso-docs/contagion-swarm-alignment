"""Closed advisory summaries; reviewer text and source evidence remain loopback-only."""
import json
from pathlib import Path
from typing import Literal
from pydantic import Field

from contagion.config import digest
from contagion.publication import Redactor,sensitive_values
from contagion.research_publication import Closed
from contagion.review import ReviewResult,validate_review


class AdvisoryRow(Closed):
    id:str=Field(pattern=r'^[a-f0-9]{16}$')
    batch_id:str=Field(pattern=r'^[a-f0-9]{16}$')
    sample_id:str=Field(pattern=r'^[a-f0-9]{16}$')
    judge_model:str=Field(max_length=160)
    stage:Literal['local_advisory','frontier_spotcheck']
    behavior:Literal['compliant','violation','refusal','ambiguous','unscorable']
    confidence:float=Field(ge=0,le=1)
    needs_human_review:bool
    evidence_count:int=Field(ge=0,le=12)
    calibrated:Literal[False]=False


def batches(source):
    source=Path(source)
    for directory in sorted(source.glob('primary-artifact-judge-*')):
        result=directory/'review/judge-results.private.json'
        if result.is_file():yield directory,result,'local_advisory'
    for directory in sorted(source.glob('frontier-spotcheck-*')):
        result=directory/'frontier-results.private.json'
        if result.is_file():yield directory,result,'frontier_spotcheck'


def batch_id(directory):return digest(Path(directory).name)[:16]


def summaries(source,env):
    redact=Redactor(sensitive_values(env));rows=[]
    for directory,path,stage in batches(source):
        raw=json.loads(path.read_text());model=raw.get('model')
        if not model and stage=='local_advisory':model=json.loads((directory/'review/judge-config.private.json').read_text())['model']
        seen=set()
        for item in raw['results']:
            if item['sample_id'] in seen:raise ValueError('Duplicate advisory sample')
            seen.add(item['sample_id']);review=ReviewResult(**{k:v for k,v in item.items() if k!='sample_id'})
            rows.append(AdvisoryRow(id=digest([directory.name,item['sample_id']])[:16],batch_id=batch_id(directory),sample_id=item['sample_id'],
                judge_model=redact(model),stage=stage,behavior=review.behavior,confidence=review.confidence,
                needs_human_review=review.needs_human_review,evidence_count=len(review.evidence_event_ids)))
    return rows


def detail(source,batch,sample_id,env):
    redact=Redactor(sensitive_values(env))
    for directory,path,stage in batches(source):
        if batch_id(directory)!=batch:continue
        raw=json.loads(path.read_text());result=next((r for r in raw['results'] if r['sample_id']==sample_id),None)
        if result is None:raise ValueError('Unknown advisory sample')
        if stage=='local_advisory':
            plan=json.loads((directory/'judge-plan.private.json').read_text());queue=Path(plan['queue']).resolve()
            private=Path(source).resolve()
            if private not in queue.parents:raise ValueError('Unapproved review input')
            original=next(r for r in json.loads((queue/'review_inputs.json').read_text())['samples'] if r['sample_id']==sample_id)
            from judge_artifact_queue import sample_input
            evidence=sample_input(original)
        else:evidence=next(r for r in json.loads((directory/'inputs.private.json').read_text())['samples'] if r['sample_id']==sample_id)
        validated=validate_review({k:v for k,v in result.items() if k!='sample_id'},evidence)
        def clean(value):
            if isinstance(value,str):return redact(value)
            if isinstance(value,list):return [clean(v) for v in value]
            if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
            return value
        return clean({'sample_id':sample_id,'stage':stage,'calibrated':False,'task':evidence['task'],'round':evidence['round'],
                      'events':evidence['events'],'judgment':validated.model_dump()})
    raise ValueError('Unknown advisory batch')
