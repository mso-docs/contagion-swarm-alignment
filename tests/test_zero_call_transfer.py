import hashlib
import importlib
import json
from pathlib import Path

import pytest

from contagion.config import digest


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    module = importlib.import_module('reparent_zero_call_primary')
    recovery = importlib.import_module('primary_output_recovery')
    monkeypatch.setattr(module,'ROOT',tmp_path)
    parent = tmp_path/'results/campaigns/old'; (parent/'controller').mkdir(parents=True)
    (parent/'controller/fixture.py').write_text('unchanged')
    plan = {'plan_hash':'a'*64,'after':'old-dependency','jobs':[{'calls':75}], 'planned_runs':1,
            'planned_calls':75,'max_http_attempts':80,'max_wall_seconds':3600,
            'dependencies':{'fixture.py':hashlib.sha256(b'unchanged').hexdigest()},
            'output_recovery_lineage':{'inspection':{'continuation_plan_hash':'b'*64}}}
    (parent/'primary-output-plan.json').write_text(json.dumps(plan))
    (parent/'primary-output-state.json').write_text(json.dumps({'status':'stopped','physical_calls':0}))
    pointer = tmp_path/'results/checkpoint-gates/primary-output-recovery-reservations'/('b'*64+'.private.json')
    pointer.parent.mkdir(parents=True)
    record={'new_root':str(parent.resolve()),'new_plan_hash':plan['plan_hash']}
    record['reservation_hash']=digest(record);pointer.write_text(json.dumps(record))
    def validate(root):
        value=json.loads((root/'primary-output-plan.json').read_text())
        registry=json.loads(pointer.read_text())
        if registry['new_root']!=str(root.resolve()) or registry['new_plan_hash']!=value['plan_hash']:
            raise ValueError('Authorization transferred')
        return value
    monkeypatch.setattr(recovery,'validate',validate)
    return module,parent,pointer


def test_transfer_preserves_bytes_jobs_and_disables_old_authorization(setup,tmp_path):
    module,parent,pointer=setup
    before=(parent/'primary-output-state.json').read_bytes();plan_before=(parent/'primary-output-plan.json').read_bytes()
    result=module.transfer(parent,tmp_path/'results/campaigns/new',tmp_path/'results/campaigns/next/state.json')
    assert result['jobs']==[{'calls':75}] and result['max_http_attempts']==80
    assert result['max_wall_seconds']==3600
    assert (parent/'primary-output-state.json').read_bytes()==before
    assert (parent/'primary-output-plan.json').read_bytes()==plan_before
    assert json.loads(pointer.read_text())['new_plan_hash']==result['plan_hash']
    with pytest.raises(ValueError,match='transferred'):
        module.transfer(parent,tmp_path/'results/campaigns/fork',tmp_path/'results/next.json')


def test_any_attempt_or_budget_debit_blocks_transfer(setup,tmp_path):
    module,parent,_=setup
    (parent/'primary-output-state.json').write_text(json.dumps({'status':'stopped','physical_calls':1}))
    with pytest.raises(ValueError,match='zero'):
        module.transfer(parent,tmp_path/'results/campaigns/new',tmp_path/'results/next.json')
