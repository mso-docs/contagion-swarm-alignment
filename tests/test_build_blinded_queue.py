import csv
import importlib
import json
from pathlib import Path

import pytest

from contagion.events import EventRecorder
from contagion.storage import seal

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def builder(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return importlib.import_module('build_blinded_queue')


def run_fixture(root,protocol='4.0-confirmatory',flag=False,two_rounds=False,backend='ollama'):
    root.mkdir(parents=True)
    if protocol=='2.6':
        config={'protocol_version':protocol,'family':'record','case_index':0,'intervention':'none',
                'plan':{'split':'evaluation'},'hidden_expected':'DO_NOT_LEAK_EXPECTED'}
    else:
        config={'protocol_version':protocol,'phase':'confirmatory',
                'job':{'family':'record','case':0,'case_index':0,'condition':'none','intervention':'none'},
                'case':{'family':'record','case_id':'evaluation-record-000','expected':'DO_NOT_LEAK_EXPECTED'}}
    (root/'config.snapshot.json').write_text(json.dumps(config))
    (root/'manifest.json').write_text(json.dumps({'status':'completed','protocol_version':protocol,'source_hash':'a'*64,
         'model_identity':{'backend':backend,'model':'SECRET_MODEL','digest':'b'*64,'base_url':'DO_NOT_COPY_ENDPOINT'}}))
    (root/'outcome.json').write_text('{}')
    log=EventRecorder(root/'events.jsonl','ORIGINAL_RUN_TREATMENT')
    for round_no in range(2 if two_rounds else 1):
        log.emit('message_delivered',round_no,sender_id='peer',receiver_id='agent_0',content='VISIBLE_BEFORE_REQUEST')
        log.emit('message_delivered',round_no,sender_id='peer',receiver_id='agent_1',content='OTHER_RECIPIENT_ONLY')
        payload={'task':{'catalog':[{'name':'Public'}]},'round':round_no}
        if protocol=='4.1-decomposition':
            payload.update(lower_trust_requests=['LOCAL_COMPONENT_REQUEST'],received_component_messages=['PUBLIC_COMPONENT'])
        log.emit('inference_requested',round_no,agent_id='agent_0',metadata={
            'messages':[{'role':'system','content':'Keep protected state pending.'},
                        {'role':'user','content':json.dumps(payload)}],
            'oracle':'DO_NOT_LEAK_METADATA'})
        log.emit('inference_response',round_no,agent_id='agent_0',content='SECRET_MODEL PRIVATE_TEST_TOKEN_VALUE user@example.org '+('Observed public record remains pending. '*150))
        log.emit('message_delivered',round_no,sender_id='peer',receiver_id='agent_0',content='AFTER_REQUEST_NOT_YET_OBSERVED')
        log.emit('artifact',round_no,agent_id='agent_0',content='{"summary":["Public"]}',metadata={
            'score':{'behavior':'violation' if flag else 'compliant','violation':flag},'hidden':'DO_NOT_LEAK_ARTIFACT_METADATA'})
    log.emit('message_delivered',9,sender_id='peer',receiver_id='agent_0',content='FUTURE_ONLY')
    log.close();seal(root)
    return root


def test_queue_uses_actual_requests_and_aliases_without_oracle_leakage(builder,tmp_path):
    source=run_fixture(tmp_path/'source',protocol='4.1-decomposition')
    output=tmp_path/'results/reviews/queue'
    plan=builder.build([source],output,env={'CONTAGION_API_KEY':'PRIVATE_TEST_TOKEN_VALUE'},root=tmp_path)
    raw=json.loads((output/'review_inputs.json').read_text());sample=raw['samples'][0];text=json.dumps(sample)
    assert set(sample)=={'sample_id','task_instruction','task_input','round','observed_messages','response_event_id','response','context_policy'}
    assert len(sample['sample_id'])==16 and sample['response_event_id'].startswith('event-')
    assert sample['task_input']['lower_trust_requests']==['LOCAL_COMPONENT_REQUEST']
    assert sample['task_input']['received_component_messages']==['PUBLIC_COMPONENT']
    coverage=sample['task_input']['review_context_coverage']
    assert coverage['reviewer_metadata_not_controller_instruction'] is True
    assert coverage['actual_subject_request_keys_preserved'] is True
    assert coverage['response_truncated'] is True
    assert sample['observed_messages']==[{'event_id':'event-0','round':0,'content':'VISIBLE_BEFORE_REQUEST'}]
    for forbidden in ['ORIGINAL_RUN_TREATMENT','SECRET_MODEL','PRIVATE_TEST_TOKEN_VALUE','user@example.org',
                      'DO_NOT_LEAK','OTHER_RECIPIENT_ONLY','AFTER_REQUEST_NOT_YET_OBSERVED','FUTURE_ONLY','DO_NOT_COPY_ENDPOINT']:
        assert forbidden not in text
    assert len(sample['response'])==4000 and '"response_truncated": true' in sample['context_policy']
    lineage=json.loads((output/'lineage.private.json').read_text())
    assert lineage['samples'][0]['event_aliases']['event-0'].startswith('ORIGINAL_RUN_TREATMENT:')
    assert plan['human_labels_generated']==0 and plan['selected_run_clusters']==1
    with (output/'human_labels.csv').open() as stream:
        assert all(not row['behavior'] and not row['reason'] for row in csv.DictReader(stream))


def test_queue_sampling_is_deterministic_and_final_scope_is_predeclared(builder,tmp_path):
    sources=[run_fixture(tmp_path/'one',protocol='2.6',flag=False,two_rounds=True),
             run_fixture(tmp_path/'two',flag=True,two_rounds=True)]
    one=tmp_path/'results/reviews/one';two=tmp_path/'results/reviews/two'
    p=builder.build(sources,one,limit=2,strategy='flag_enriched',env={},root=tmp_path)
    builder.build(sources,two,limit=2,strategy='flag_enriched',env={},root=tmp_path)
    assert (one/'review_inputs.json').read_bytes()==(two/'review_inputs.json').read_bytes()
    oracle=json.loads((one/'oracle_labels.private.json').read_text())
    assert oracle['flagged_population']==oracle['unflagged_population']==2
    assert oracle['flagged_selected']==oracle['unflagged_selected']==1
    final=tmp_path/'results/reviews/final';q=builder.build(sources,final,scope='final',strategy='uniform',env={},root=tmp_path)
    assert p['population_counts']['all_artifact_events']==q['population_counts']['all_artifact_events']==4
    assert q['population_counts']['scope_artifact_events']==2
    assert all(s['round']==1 for s in json.loads((final/'review_inputs.json').read_text())['samples'])


def test_integrity_precedes_source_content_loading_and_no_overwrite(builder,tmp_path):
    source=run_fixture(tmp_path/'source');out=tmp_path/'results/reviews/queue'
    (source/'events.jsonl').write_text('CORRUPT NOT JSON')
    with pytest.raises(ValueError,match='checksum'):builder.build([source],out,env={},root=tmp_path)
    assert not out.exists()
    source=run_fixture(tmp_path/'good');builder.build([source],out,env={},root=tmp_path)
    original=(out/'human_labels.csv').read_bytes()
    with pytest.raises(ValueError,match='fresh'):builder.build([source],out,env={},root=tmp_path)
    assert (out/'human_labels.csv').read_bytes()==original


def test_unsealed_manifests_are_not_read_and_mock_is_explicit(builder,tmp_path):
    bad=tmp_path/'bad';bad.mkdir();(bad/'manifest.json').write_text('NOT JSON')
    good=run_fixture(tmp_path/'good')
    plan=builder.build([bad,good],tmp_path/'results/reviews/queue',env={},root=tmp_path)
    assert plan['population_counts']['unsealed_manifest_directories_skipped']==1
    mock=run_fixture(tmp_path/'mock',backend='mock')
    with pytest.raises(ValueError,match='No eligible'):builder.build([mock],tmp_path/'results/reviews/mock-excluded',env={},root=tmp_path)
    included=builder.build([mock],tmp_path/'results/reviews/mock-included',include_mock=True,env={},root=tmp_path)
    assert included['include_mock'] is True
