"""Publication checks use only explicit public assets and preserve project prefixes."""
import importlib
import json
from pathlib import Path
import shutil

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    module=importlib.import_module('publication_readiness')
    source=tmp_path/'dashboard';source.mkdir();(source/'data').mkdir()
    for name in ('index.html','app.js','style.css','widgets.js'):shutil.copyfile(ROOT/'dashboard'/name,source/name)
    for name in ('results','research','repositories','followups'):
        data=json.loads((ROOT/'dashboard/data'/f'{name}.json').read_text())
        for field in ('runs','studies','scenarios','neural','monitor','reviews'):
            if field in data:data[field]=[]
        (source/'data'/f'{name}.json').write_text(json.dumps(data))
    return module,source,tmp_path/'artifact'


def test_allowlist_ignores_secret_trap_and_inspects_public_build(fixture):
    module,source,artifact=fixture
    (source/'.env').write_text('CONTAGION_API_KEY='+'sk-'+'fixture'*8)
    (source/'raw-events.jsonl').write_text('unreviewed private trace')
    module.build(source,artifact);result=module.inspect(source,artifact)
    assert result['technical_status']=='static_artifact_checks_passed'
    assert all(result['workflow_policy'].values())
    assert not (artifact/'.env').exists() and not (artifact/'raw-events.jsonl').exists()
    assert result['deployed'] is False and result['hackathon_submission_performed'] is False


def test_extra_artifact_and_modified_assets_fail_closed(fixture):
    module,source,artifact=fixture;module.build(source,artifact)
    (artifact/'private-events.jsonl').write_text('must never ship')
    with pytest.raises(ValueError,match='allowlist'):module.inspect(source,artifact)
    (artifact/'private-events.jsonl').unlink()
    with (artifact/'app.js').open('a') as stream:stream.write('\n// unreviewed modification')
    with pytest.raises(ValueError,match='changed'):module.inspect(source,artifact)


def test_root_absolute_asset_breaks_project_pages_prefix(fixture):
    module,source,artifact=fixture
    path=source/'index.html';path.write_text(path.read_text().replace('href="style.css"','href="/style.css"'))
    module.build(source,artifact)
    with pytest.raises(ValueError,match='project_prefix_unsafe'):module.inspect(source,artifact)


def test_duplicate_navigation_ids_fail_structural_review(fixture):
    module,source,artifact=fixture
    path=source/'index.html';path.write_text(path.read_text().replace('</main>','<div id="nav-overview"></div></main>'))
    module.build(source,artifact)
    with pytest.raises(ValueError,match='Duplicate'):module.inspect(source,artifact)


def test_workflow_policy_cannot_deploy_a_pull_request(fixture,tmp_path):
    module,_,_=fixture
    path=tmp_path/'pages.yml';path.write_text((ROOT/'.github/workflows/pages.yml').read_text().replace("github.ref == 'refs/heads/main'","github.ref != 'refs/heads/main'"))
    result=module.workflow_checks(path)
    assert result['main_only_deployment'] is False and result['main_only_artifact_upload'] is False
    path.write_text((ROOT/'.github/workflows/pages.yml').read_text().replace("github.ref == 'refs/heads/main'","true || github.ref == 'refs/heads/main'"))
    assert module.workflow_checks(path)['main_only_deployment'] is False


def test_base_allowlist_cannot_expand_to_a_private_file(fixture,monkeypatch):
    module,source,_=fixture;monkeypatch.setattr(module,'ASSETS',(*module.ASSETS,'.env'))
    with pytest.raises(ValueError,match='policy review'):module.expected_assets(source)
