"""Submission freezes bind public bytes and never contact collectors."""
import json
from pathlib import Path
import shutil
import pytest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from freeze_dashboard import create, validate, counts
from build_dashboard import build
from export_live_dashboard import export

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def frozen_source(tmp_path):
    source=tmp_path/'dashboard'
    # Creation tests deliberately start before a freeze; the committed checkpoint
    # is validated separately below rather than silently replacing its manifest.
    shutil.copytree(ROOT/'dashboard',source,ignore=shutil.ignore_patterns('submission-freeze.json'))
    return source


def test_freeze_binds_inventory_and_every_public_byte(frozen_source,tmp_path):
    inventory=ROOT/'report/data/final_inventory.json'
    if not inventory.exists():pytest.skip('Final reconciliation not built')
    result=create(frozen_source,inventory,'2026-11-08T23:59:00Z',True,{})
    assert result.automatic_refresh_enabled is False
    assert result.private_apis_required is False
    assert sum(r.rows for r in result.datasets)==1412
    assert result.trained_checkpoint_captures==72
    assert validate(frozen_source/'data/submission-freeze.json',inventory=inventory)==result
    output=tmp_path/'artifact';build(frozen_source,output)
    assert (output/'data/submission-freeze.json').is_file()
    with pytest.raises(ValueError):create(frozen_source,inventory,'2026-11-08T23:59:00Z',True,{})
    with pytest.raises(ValueError):export(ROOT/'results/dashboard-live/data',frozen_source/'data',{})
    (frozen_source/'app.js').write_text('// changed')
    with pytest.raises(ValueError,match='changed'):validate(frozen_source/'data/submission-freeze.json')


def test_no_implicit_freeze_or_inventory_mismatch(frozen_source,tmp_path):
    inventory=ROOT/'report/data/final_inventory.json'
    if not inventory.exists():pytest.skip('Final reconciliation not built')
    with pytest.raises(ValueError):create(frozen_source,inventory,'2026-11-08T23:59:00Z',False,{})
    data=json.loads(inventory.read_text());data['input_sha256']['results']='0'*64
    changed=tmp_path/'inventory.json';changed.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='Inventory public snapshot input'):create(frozen_source,changed,'2026-11-08T23:59:00Z',True,{})
    assert not (frozen_source/'data/submission-freeze.json').exists()


def test_final_mode_prevents_polling_and_retains_static_interaction():
    source=(ROOT/'dashboard/app.js').read_text()
    assert "dashboardMode.frozen&&dashboardMode.loaded" in source
    assert "if(!dashboardMode.operator||dashboardMode.frozen||dashboardMode.blocked)" in source
    assert "mode=operator" in source
    assert "fetchPublicTrace" in source
    summary=counts(ROOT/'dashboard')
    assert len(summary['datasets'])==6
    assert sum(r.rows for r in summary['datasets'])==1412


def test_committed_freeze_binds_actual_assets_and_inventory():
    manifest=ROOT/'dashboard/data/submission-freeze.json'
    if not manifest.exists():pytest.skip('Final snapshot not frozen yet')
    result=validate(manifest,inventory=ROOT/'report/data/final_inventory.json')
    assert result.state=='submission_frozen' and result.automatic_refresh_enabled is False


def test_staged_modified_asset_cannot_hide_behind_clean_frozen_worktree(monkeypatch,capsys):
    manifest=ROOT/'dashboard/data/submission-freeze.json'
    if not manifest.exists():pytest.skip('Final snapshot not frozen yet')
    import security_guard
    original=security_guard.read_candidate
    monkeypatch.setattr(security_guard,'candidates',lambda root,mode:['dashboard/data/submission-freeze.json'])
    def index_blob(root,name,mode):
        return b'// unsafe staged replacement' if name=='dashboard/app.js' else original(root,name,'worktree')
    monkeypatch.setattr(security_guard,'read_candidate',index_blob)
    assert security_guard.check(ROOT,'staged',env={})==1
    assert 'frozen snapshot closure' in capsys.readouterr().err
