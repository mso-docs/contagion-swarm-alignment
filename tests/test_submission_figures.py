"""Publication checks keep dependent trajectories and pending utility explicit."""
import copy
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_temporal_heatmap_preserves_each_run_and_exposure(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    from paper_analysis import temporal_patch_rows
    data=json.loads((ROOT/'report/data/compact_evidence.json').read_text())
    rows=temporal_patch_rows(data)
    assert len(rows)==6
    assert sum(sum(r['violations']) for r in rows)==17
    assert sum(r['direct_deliveries'] for r in rows)==20
    assert all(r['violations'][0]==0 and r['violations'][-1]==0 for r in rows)
    data=copy.deepcopy(data)
    next(r for r in data['runs'] if r['family']=='patch' and r['status']=='completed' and r['condition']=='benign_override')['round_downstream_violations']=[9,0,0,0,0]
    with pytest.raises(ValueError,match='five-round'):temporal_patch_rows(data)


def fixture():
    rows=[];mapping=[];samples=[];seals={}
    for case in range(8):
        for seed in [101,102]:
            for defense in ['plain','source_attribution']:
                for condition in ['none','benign_override']:
                    i=len(rows);name=str(i);seal=f'{i:064x}'
                    rows.append({'status':'completed','phase':'evaluation','backend':'ollama','case':f'case{case}','seed':seed,'defense':defense,'intervention':condition,'attempt_id':name,'cohort':'same','rounds':15,'topology':'ring','final_downstream_violation_rate':0.,'any_round_downstream_violation':False})
                    mapping.append({'sample_id':name,'task_id':f'case{case}','seed':seed,'defense':defense,'condition':condition,'phase':'evaluation','protocol':'3.3-repository-safeguard','source_seal_sha256':seal})
                    samples.append({'sample_id':name,'review_complete':True,'quality_precision':None,'golden_recall':0.})
                    seals[name]=seal
    return {'schema_version':'primary-long-analysis-1.0','status':'completed_registered_batch','mock_attempts':0,'unmatched_completed_runs':[],'evaluation_runs':64,'rows':rows,'source_seal_sha256':seals},mapping,{'samples':samples}


def test_safeguard_requires_human_labels_and_preserves_undefined_empty_precision(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    from safeguard_figure import paired_inputs
    analysis,mapping,quality=fixture();blocks=paired_inputs(analysis,mapping,quality)
    assert len(blocks)==16
    assert all(r['quality_precision'] is None for arms in blocks for r in arms.values())
    quality['samples'][0]['review_complete']=False
    with pytest.raises(ValueError,match='Human quality'):paired_inputs(analysis,mapping,quality)


def test_safeguard_rejects_partial_mock_unknown_and_wrong_run_seals(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    from safeguard_figure import paired_inputs
    analysis,mapping,quality=fixture();analysis['mock_attempts']=1
    with pytest.raises(ValueError,match='Mock'):paired_inputs(analysis,mapping,quality)
    analysis,mapping,quality=fixture();analysis['rows'].pop()
    with pytest.raises(ValueError,match='all64'):paired_inputs(analysis,mapping,quality)
    analysis,mapping,quality=fixture();analysis['rows'][0]['final_downstream_violation_rate']=None
    with pytest.raises(ValueError,match='Unknown boundary'):paired_inputs(analysis,mapping,quality)
    analysis,mapping,quality=fixture();mapping[0]['source_seal_sha256']=mapping[1]['source_seal_sha256']
    with pytest.raises(ValueError,match='another run seal'):paired_inputs(analysis,mapping,quality)
