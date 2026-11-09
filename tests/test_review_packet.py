import importlib
from pathlib import Path
import pytest


def test_review_packet_refuses_mixed_scientific_pdf_versions(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    module=importlib.import_module('prepare_review_packet')
    data={k:'a'*64 for k in ['authoring_source_sha256','evidence_sha256','rq3_followup_sha256','pointer_audit_sha256',
                            'human_audit_sha256','submission_snapshot_sha256','notebook_source_sha256','analysis_script_sha256','bibliography_sha256']}
    classic={**data,'typeface_variant':'classic','pdf_sha256':'b'*64};template={**data,'typeface_variant':'template','pdf_sha256':'c'*64}
    assert module.validate_pair(classic,template)==data
    with pytest.raises(ValueError,match='scientific source'):
        module.validate_pair(classic,{**template,'human_audit_sha256':'d'*64})
    with pytest.raises(ValueError,match='distinct'):
        module.validate_pair(classic,{**template,'pdf_sha256':classic['pdf_sha256']})
