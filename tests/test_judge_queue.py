import asyncio
import importlib
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_primary_judge_is_frozen_and_stop_prevents_inference(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'));module=importlib.import_module('queue_judge')
    queue=tmp_path/'inputs';queue.mkdir();(queue/'review_inputs.json').write_text('{"samples":[{"sample_id":"fixture"}]}')
    prior=tmp_path/'prior';prior.mkdir();(prior/'followup-state.json').write_text('{"status":"running"}')
    root=tmp_path/'judge';record=module.prepare(root,queue,prior,'mock-judge','a'*64)
    assert record['planned_calls']==1 and record['calibrated'] is False
    (root/'STOP').touch()
    with pytest.raises(RuntimeError,match='Operator stop'):module.run(root)
    state=json.loads((root/'queue-state.json').read_text());assert state['completed_calls']==0 and state['status']=='stopped'


def test_review_queue_mutation_blocks_before_inference(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'));module=importlib.import_module('queue_judge')
    queue=tmp_path/'inputs';queue.mkdir();(queue/'review_inputs.json').write_text('{"samples":[{"sample_id":"one"}]}')
    root=tmp_path/'judge';module.prepare(root,queue,tmp_path/'prior','mock-judge','a'*64)
    (queue/'review_inputs.json').write_text('{"samples":[{"sample_id":"changed"}]}')
    with pytest.raises(ValueError,match='queue changed'):module.run(root)


def test_unpinned_local_judge_cannot_start(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'));module=importlib.import_module('judge_artifact_queue')
    queue=tmp_path/'inputs';queue.mkdir();(queue/'review_inputs.json').write_text('{"samples":[{"sample_id":"fixture"}]}')
    env=tmp_path/'env';env.write_text('CONTAGION_BASE_URL=http://127.0.0.1:11835\n')
    with pytest.raises(ValueError,match='Pin local worker'):asyncio.run(module.run(queue,tmp_path/'out','mock-judge',env,api='ollama',worker='primary'))
    assert not (tmp_path/'out').exists()


def test_judge_resume_reuses_validated_responses_and_counts_failed_calls(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'));module=importlib.import_module('judge_artifact_queue')
    from contagion.models import ModelResponse
    from contagion.events import read_events
    queue=tmp_path/'inputs';queue.mkdir()
    rows=[{'sample_id':str(i),'task_instruction':'No forbidden update','task_input':{},'round':1,'observed_messages':[],
           'response_event_id':'event-'+str(i),'response':'{}'} for i in range(2)]
    (queue/'review_inputs.json').write_text(json.dumps({'samples':rows}));env=tmp_path/'env';env.write_text('CONTAGION_BASE_URL=https://example.invalid/v1\n')
    class Fake:
        calls=0
        def __init__(self,*a,**k):self.audit=None
        async def close(self):pass
        async def chat(self,messages,config):
            Fake.calls+=1;self.audit('http_attempt',{'attempt':1})
            if Fake.calls==2:raise RuntimeError('fixture transport failure')
            sample=json.loads(messages[-1]['content'])
            return ModelResponse(content=json.dumps({'behavior':'ambiguous','evidence_event_ids':[sample['final_event_id']],
              'rubric_reason':'Insufficient evidence','confidence':.2,'needs_human_review':True}))
    monkeypatch.setattr(module,'HTTPProvider',Fake)
    out=tmp_path/'out'
    with pytest.raises(RuntimeError):asyncio.run(module.run(queue,out,'fixture-judge',env,max_calls=2,max_attempts=3))
    first=(out/'response-000-attempt-001.private.json').read_bytes()
    assert asyncio.run(module.run(queue,out,'fixture-judge',env,max_calls=2,max_attempts=3,resume=True))==2
    assert Fake.calls==3 and module.attempt_count(out)==3
    assert (out/'response-000-attempt-001.private.json').read_bytes()==first
    ids=[e['event_id'] for p in (out/'sessions').glob('*.jsonl') for e in read_events(p)]
    assert len(ids)==len(set(ids))
