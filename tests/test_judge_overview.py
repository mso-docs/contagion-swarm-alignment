"""The new presentation surface must preserve the evidence and privacy boundary."""
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return importlib.import_module('build_public_site')


def test_overview_rejects_private_text_and_active_content(module):
    html = (ROOT/'site/overview/index.html').read_text()
    css = (ROOT/'site/overview/style.css').read_text()
    module.validate_overview(html, css, set())
    with pytest.raises(ValueError, match='privacy'):
        module.validate_overview(html.replace('</main>', '<p>private-host-fixture</p></main>'), css, {'private-host-fixture'})
    with pytest.raises(ValueError, match='Active'):
        module.validate_overview(html+'<script>fetch("private")</script>', css, set())
    with pytest.raises(ValueError, match='Unapproved'):
        module.validate_overview(html.replace('href="paper.pdf"', 'href="/paper.pdf"'), css, set())


def test_overview_uses_frozen_counts_and_exact_audited_pdf(module):
    content = module.prepare_overview()
    html = content['index.html'].decode()
    assert '{{' not in html
    assert '<strong>583</strong>' in html
    assert '<strong>14,622</strong>' in html
    assert content['paper.pdf'] == (ROOT/'report/paper.pdf').read_bytes()
    assert set(content) == {'index.html', 'style.css', 'paper.pdf'}


def test_composed_build_preserves_every_dashboard_file(module, tmp_path):
    output = tmp_path/'public'
    module.build(output)
    expected = module.inspect.__globals__['expected_assets'](ROOT/'dashboard')
    actual = {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}
    assert actual == expected | {'overview/index.html', 'overview/style.css', 'overview/paper.pdf'}
    for name in expected - {'.nojekyll'}:
        assert (output/name).read_bytes() == (ROOT/'dashboard'/name).read_bytes()


def test_overview_preview_serves_only_approved_routes(module, tmp_path):
    from http.server import ThreadingHTTPServer
    from threading import Thread
    import httpx
    preview = importlib.import_module('serve_public_site')
    (tmp_path/'overview').mkdir()
    (tmp_path/'overview/index.html').write_text('reviewed overview')
    (tmp_path/'.env').write_text('unreviewed private data')
    server = ThreadingHTTPServer(('127.0.0.1', 0), preview.site_handler(tmp_path, {'overview/index.html'}))
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}', trust_env=False) as client:
            assert client.get('/overview/').text == 'reviewed overview'
            assert client.get('/.env').status_code == 404
            assert client.get('/api/private').status_code == 404
            assert client.get('/overview/', headers={'Host': 'foreign.invalid'}).status_code == 403
    finally:
        server.shutdown()
        worker.join()
        server.server_close()
