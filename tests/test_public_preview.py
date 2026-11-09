from email.message import Message
import importlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest


@pytest.fixture
def preview(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / 'scripts'))
    module = importlib.import_module('serve_public_preview')
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    source = tmp_path / 'dashboard'; source.mkdir(); (source / 'data').mkdir()
    for name in ('index.html', 'style.css', 'app.js', 'widgets.js'):
        shutil.copyfile(root / 'dashboard' / name, source / name)
    for name in ('results', 'research', 'repositories', 'followups'):
        data = json.loads((root / 'dashboard/data' / f'{name}.json').read_text())
        for field in ('runs', 'studies', 'scenarios', 'neural', 'monitor', 'reviews', 'multidomain', 'diversity'):
            if field in data:
                data[field] = []
        (source / 'data' / f'{name}.json').write_text(json.dumps(data))
    return module, source, tmp_path / 'results/public-preview/review'


def test_exact_pages_artifact_and_no_raw_source_copy(preview):
    module, source, artifact = preview
    (source / '.env').write_text('never-copy-fixture')
    (source / 'raw-events.jsonl').write_text('unreviewed raw data')
    result = module.prepare(source, artifact)
    assert result['technical_status'] == 'static_artifact_checks_passed'
    assert not (artifact / '.env').exists() and not (artifact / 'raw-events.jsonl').exists()
    assert result['deployed'] is False


def test_preview_has_no_private_api_or_foreign_host_access(preview):
    module, _, artifact = preview; artifact.mkdir(parents=True)
    (artifact / 'index.html').write_text('public fixture')
    cls = module.handler(artifact, {'index.html'}).func
    request = object.__new__(cls); request.server = SimpleNamespace(server_port=8766)
    request.headers = Message(); request.headers['Host'] = '127.0.0.1:8766'
    errors = []; request.send_error = errors.append
    request.path = '/'; assert request.allowed()
    for path in ('/__local_status', '/__private_repository/' + 'a' * 16, '/%2e%2e/.env'):
        request.path = path; assert not request.allowed() and errors[-1] == 404
    request.path = '/'; request.headers.replace_header('Host', 'attacker.example:8766')
    assert not request.allowed() and errors[-1] == 403


def test_reviewed_trace_files_are_exactly_allowlisted(preview):
    module, source, artifact = preview
    root = Path(__file__).resolve().parents[1] / 'dashboard/data'
    if not (root / 'trace-samples.json').is_file():
        pytest.skip('No reviewed public trace checkpoint committed')
    shutil.copyfile(root / 'trace-samples.json', source / 'data/trace-samples.json')
    shutil.copytree(root / 'trace-samples', source / 'data/trace-samples')
    result = module.prepare(source, artifact)
    from public_trace_samples import validate_index
    index = validate_index(artifact / 'data/trace-samples.json')
    assert len(index.samples) == len(validate_index(source / 'data/trace-samples.json').samples) > 0
    assert all((artifact / row.file).is_file() for row in index.samples)
    assert result['artifact_files'] == len(module.expected_assets(source))
