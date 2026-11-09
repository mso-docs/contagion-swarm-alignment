"""Publication figures retain measured evidence boundaries and stale-input guards."""
import copy
import hashlib
import importlib
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return importlib.import_module('paper_analysis'),importlib.import_module('build_paper')


def test_reference_heatmap_is_one_capture_per_pinned_model_layer_and_probe(modules):
    analysis,_=modules;data=json.loads((ROOT/'report/data/compact_evidence.json').read_text())
    values=analysis.reference_patch_cells(data)
    assert values['layers']==[0,5,11] and len(values['patch_delta'])==2
    assert sum(map(len,values['patch_delta']))==6
    changed=copy.deepcopy(data);changed['neural'].append(changed['neural'][0])
    with pytest.raises(ValueError,match='six-capture'):analysis.reference_patch_cells(changed)
    changed=copy.deepcopy(data);changed['neural'][0]['model']='different-checkpoint'
    with pytest.raises(ValueError,match='six-capture'):analysis.reference_patch_cells(changed)


def test_undefined_reference_restoration_is_not_imputed_as_zero(modules):
    analysis,_=modules;data=json.loads((ROOT/'report/data/compact_evidence.json').read_text())
    row=data['neural'][0];row['restoration']=None
    values=analysis.reference_patch_cells(data)
    position=values['kinds'].index(row['kind']);layer=values['layers'].index(row['layer'])
    assert values['restoration'][position][layer] is None


def test_secondary_sensitivity_figure_input_is_bound_and_fail_closed(modules,tmp_path):
    _,build=modules;path=tmp_path/'report/data/patch_pointer_audit.json';path.parent.mkdir(parents=True);path.write_text('frozen numeric fixture')
    inputs={'secondary_inputs_sha256':{'report/data/patch_pointer_audit.json':hashlib.sha256(path.read_bytes()).hexdigest()}}
    build.validate_secondary_figure_inputs(inputs,tmp_path)
    path.write_text('changed numeric fixture')
    with pytest.raises(ValueError,match='changed'):build.validate_secondary_figure_inputs(inputs,tmp_path)
    with pytest.raises(ValueError,match='declared secondary'):build.validate_secondary_figure_inputs({},tmp_path)


def test_paired_run_points_require_matched_conditions(modules):
    analysis,_=modules
    paired_run_outcomes=analysis.paired_run_outcomes
    data=json.loads((Path(__file__).resolve().parents[1]/'report/data/compact_evidence.json').read_text())
    pairs=paired_run_outcomes(data)
    assert len(pairs)==18
    assert all(-1<=row['difference']<=1 for row in pairs)
    incomplete=copy.deepcopy(data)
    incomplete['runs'].pop(0)
    with pytest.raises(ValueError,match='Incomplete'):
        paired_run_outcomes(incomplete)
