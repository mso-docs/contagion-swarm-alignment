import importlib
import json
from pathlib import Path
import pytest


def fixture(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    module=importlib.import_module('advisory_publication');directory=tmp_path/'frontier-spotcheck-fixture';directory.mkdir()
    sample={'sample_id':'a'*16,'task':{'instruction':'Keep original constraints','input':{}},'round':1,'events':[{'event_id':'event-1','round':1,'content':'{}'}],'final_event_id':'event-1'}
    result={'sample_id':'a'*16,'behavior':'ambiguous','evidence_event_ids':['event-1'],'rubric_reason':'Insufficient evidence','confidence':.5,'needs_human_review':True}
    (directory/'inputs.private.json').write_text(json.dumps({'samples':[sample]}));(directory/'frontier-results.private.json').write_text(json.dumps({'model':'fixture-frontier','results':[result]}))
    return module,directory


def test_advisory_export_withholds_text_and_never_claims_human_calibration(tmp_path,monkeypatch):
    module,directory=fixture(tmp_path,monkeypatch);rows=module.summaries(tmp_path,{})
    assert len(rows)==1 and rows[0].calibrated is False
    assert rows[0].evidence_count==1
    blob=rows[0].model_dump_json();assert 'rubric_reason' not in blob and 'Insufficient evidence' not in blob
    d=module.detail(tmp_path,rows[0].batch_id,rows[0].sample_id,{})
    assert d['judgment']['rubric_reason']=='Insufficient evidence' and d['calibrated'] is False


def test_private_judge_detail_rejects_invalid_citations_and_ids(tmp_path,monkeypatch):
    module,directory=fixture(tmp_path,monkeypatch);raw=json.loads((directory/'frontier-results.private.json').read_text());raw['results'][0]['evidence_event_ids']=['future-id'];(directory/'frontier-results.private.json').write_text(json.dumps(raw))
    with pytest.raises(ValueError):module.detail(tmp_path,module.batch_id(directory),'a'*16,{})
    with pytest.raises(ValueError):module.detail(tmp_path,'f'*16,'a'*16,{})
    with pytest.raises(ValueError):module.AdvisoryRow(id='a'*16,batch_id='b'*16,sample_id='c'*16,judge_model='fixture',stage='frontier_spotcheck',behavior='ambiguous',confidence=.5,needs_human_review=True,evidence_count=1,calibrated=True)
