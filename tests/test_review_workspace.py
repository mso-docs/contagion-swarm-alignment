import importlib
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def builder(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return importlib.import_module('build_review_workspace')


def queue(tmp_path,row):
    source=tmp_path/'results/reviews/queue';source.mkdir(parents=True)
    (source/'review_inputs.json').write_text(json.dumps({'samples':[row]}))
    return source


def sample():
    return {'sample_id':'a','task_instruction':'Use original task rules','task_input':{},'round':1,'observed_messages':[],
            'response_event_id':'event1','response':'{"answer":{}}'}


def test_private_workspace_embeds_data_safely_without_labels(builder,tmp_path):
    row=sample();row['response']='</script><script>alert(1)</script>'
    row['oracle']='DO NOT LEAK';row['model']='DO NOT LEAK'
    source=queue(tmp_path,row);target=tmp_path/'results/reviews/workspace/artifacts.html'
    result=builder.build(source,target,root=tmp_path);text=target.read_text()
    assert result['samples']==1 and result['human_labels_generated']==0
    assert 'DO NOT LEAK' not in text
    assert '</script><script>alert(1)' not in text
    assert '\\u003c/script\\u003e' in text
    assert "connect-src 'none'" in text and 'script-src \'sha256-' in text
    assert 'fetch(' not in text and 'localStorage' not in text
    with pytest.raises(FileExistsError):builder.build(source,target,root=tmp_path)


def test_private_workspace_rejects_public_output_and_input_symlink(builder,tmp_path):
    source=queue(tmp_path,sample())
    with pytest.raises(ValueError):builder.build(source,tmp_path/'dashboard/review.html',root=tmp_path)
    target=source/'review_inputs.json';target.rename(source/'actual.json');target.symlink_to(source/'actual.json')
    with pytest.raises(ValueError):builder.read_queue(source,'artifact',tmp_path)


def test_private_workspace_strips_nested_oracle_metadata(builder,tmp_path):
    row=sample();row['observed_messages']=[{'event_id':'a','round':0,'content':'peer','metadata':{'oracle':'HIDDEN'}}]
    source=queue(tmp_path,row)
    result=builder.read_queue(source,'artifact',tmp_path)
    assert result['samples'][0]['observed_messages']==[{'event_id':'a','round':0,'content':'peer'}]


def test_separate_rq3_freeze_has_complete_matrix_and_distinct_denominators():
    from itertools import product
    data=json.loads((ROOT/'report/data/rq3_followup.json').read_text())
    compact=json.loads((ROOT/'report/data/compact_evidence.json').read_text())
    assert data['complete_runs']==64 and data['responses']==320
    assert len([r for r in compact['runs'] if r['status']=='completed'])==36
    assert len(data['source_seal_sha256'])==64
    keys={(r['case'],r['seed'],r['topology'],r['condition'],r['executor'],r['context']) for r in data['rows']}
    assert keys==set(product(range(4),[13001],['single','complete'],['none','benign_override'],['deny','permissive_simulator'],['matched_reset','natural_history']))
    assert data['attempting_runs']==sum(r['attempted_forbidden'] for r in data['rows'])
    assert data['state_violating_runs']==sum(r['actual_state_violation'] for r in data['rows'])
    assert data['runs_with_refusal']==sum(r['refusal_rate']>0 for r in data['rows'])
    assert data['attempting_runs']==data['state_violating_runs']==data['runs_with_refusal']==0
    assert data['mean_task_success']==sum(r['task_success_rate'] for r in data['rows'])/64==1.0
    assert all(r['phase']=='confirmatory' and r['backend']=='ollama' for r in data['rows'])


def test_bundle_is_allowlisted_and_rejects_public_destination(monkeypatch,tmp_path):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    bundle=importlib.import_module('research_bundle')
    assert all(not name.startswith(('results/','.env','review_workspace/')) for name in bundle.TEXT_FILES)
    assert 'report/data/rq3_followup.json' in bundle.TEXT_FILES
    with pytest.raises(ValueError,match='ignored results'):
        bundle.build(tmp_path/'dashboard/bundle',root=tmp_path)
