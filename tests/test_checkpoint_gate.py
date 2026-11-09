import asyncio
from pathlib import Path
import runpy

import pytest

from contagion.inference import MockProvider
from contagion.studies import StudyPlan,freeze_plan,run_plan
from contagion.tasks import make_case,task_instruction,task_response_schema


def test_record_amendment_is_explicit_and_does_not_constrain_answer_values():
    case=make_case('record','development',14)
    assert 'only the exact name strings' in task_instruction(case,'2.5')
    assert 'only the exact name strings' not in task_instruction(case,'2.4')
    assert task_response_schema(case,'2.5')==task_response_schema(case,'2.4')
    for family in ['catalog','patch','provenance']:
        case=make_case(family)
        assert task_instruction(case,'2.5')==task_instruction(case,'2.4')


def test_gate_callback_is_synchronous_and_allows_observed_intervention_violations(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[1];monkeypatch.syspath_prepend(str(root/'scripts'))
    gate=runpy.run_path(str(root/'scripts/checkpoint_gate.py'))
    plan=StudyPlan(protocol_version='2.5',families=['catalog'],model='mock-v1',max_total_model_calls=50)
    frozen=tmp_path/'freeze.json';freeze_plan(plan,frozen)
    checked=[]
    def callback(path):checked.append(gate['check_run'](path))
    asyncio.run(run_plan(plan,MockProvider(),tmp_path/'raw',frozen,on_run=callback))
    assert len(checked)==2 and checked[1]['outcome']['any_violation']
    path=Path(checked[0]['directory']);(path/'outcome.json').write_text('{}')
    with pytest.raises(gate['CheckpointGateError'],match='integrity'):gate['check_run'](path)


def test_action_contract_keeps_unsafe_values_expressible():
    case=make_case('record','development',14)
    schema=task_response_schema(case,'2.6')['properties']['answer']
    action=schema['properties']['proposed_action']
    assert action['additionalProperties'] is False
    assert action['properties']['operation']=={'type':'string'}
    assert action['properties']['status']=={'type':'string'}
    assert 'Do not add reason' in task_instruction(case,'2.6')
    from contagion.tasks import TaskArtifact,ToyRecordStore,task_score
    artifact=TaskArtifact(answer={'summary':case.expected['summary'],
        'proposed_action':{'operation':'propose_protected_update','status':'approved'}},message='')
    outcome=task_score(case,artifact,ToyRecordStore(True))
    assert outcome['violation'] and outcome['state_violation']
