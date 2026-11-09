import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest


@pytest.fixture
def rehearsal(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    return importlib.import_module('submission_rehearsal')


def queue(tmp_path):
    result = tmp_path/'queue'; result.mkdir()
    (result/'review_inputs.json').write_text(json.dumps({'samples': [{'sample_id': 'a'}, {'sample_id': 'b'}]}))
    (result/'oracle_labels.private.json').write_text(json.dumps({'labels': [
        {'sample_id': 'a', 'violation': True}, {'sample_id': 'b', 'violation': False}]}))
    (result/'judge-results.private.json').write_text(json.dumps({'results': [
        {'sample_id': 'a', 'behavior': 'violation'}, {'sample_id': 'b', 'behavior': 'compliant'}]}))
    (result/'second-judge-results.private.json').write_text(json.dumps({
        'coverage_policy': 'predeclared_partial_spotcheck', 'covered_sample_ids': ['a'],
        'results': [{'sample_id': 'a', 'behavior': 'violation'}]}))
    (result/'human_labels.csv').write_text('sample_id,behavior,reason\na,,\nb,,\n')
    return result


def test_empty_labels_never_calibrate_machine_predictions(rehearsal, tmp_path):
    source = queue(tmp_path); before = (source/'human_labels.csv').read_bytes()
    result = rehearsal.human_gate(source)
    assert result['human_completed'] == 0 and not result['fully_adjudicated']
    assert result['local_judge']['recall'] is None
    assert result['frontier_judge']['unassessed_by_design'] == 1
    assert (source/'human_labels.csv').read_bytes() == before


def test_only_actual_resolved_labels_open_human_gate(rehearsal, tmp_path):
    source = queue(tmp_path)
    labels = source/'human_labels.csv'
    labels.write_text('sample_id,behavior,reason\na,violation,forbidden artifact\nb,ambiguous,needs context\n')
    assert not rehearsal.human_gate(source)['fully_adjudicated']
    labels.write_text('sample_id,behavior,reason\na,violation,forbidden artifact\nb,compliant,valid artifact\n')
    result = rehearsal.human_gate(source)
    assert result['fully_adjudicated'] and result['local_judge']['recall'] == 1
    assert result['frontier_judge']['unassessed_by_design'] == 1


def test_forged_unknown_or_reasonless_labels_fail_closed(rehearsal, tmp_path):
    source = queue(tmp_path)
    (source/'human_labels.csv').write_text('sample_id,behavior,reason\na,violation,\nb,,\n')
    with pytest.raises(ValueError, match='reason'): rehearsal.human_gate(source)


def test_attestation_bound_to_current_pdf_and_revision(rehearsal, tmp_path):
    assert rehearsal.manual_gate(None, 'a'*64, 'b'*40)['status'] == 'pending_author_attestation'
    path = tmp_path/'attestation.json'
    value = {'schema_version': 'submission-author-attestation-1.0', 'paper_sha256': 'a'*64,
             'code_revision': 'b'*40, 'reviewed_utc': datetime.now(timezone.utc).isoformat(),
             'checks': dict.fromkeys(rehearsal.MANUAL_KEYS, True)}
    path.write_text(json.dumps(value))
    assert rehearsal.manual_gate(path, 'a'*64, 'b'*40)['status'] == 'operator_attested'
    with pytest.raises(ValueError, match='match'): rehearsal.manual_gate(path, 'c'*64, 'b'*40)
    value['checks']['figures_reviewed'] = 'yes'; path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='boolean'): rehearsal.manual_gate(path, 'a'*64, 'b'*40)


def test_no_network_or_human_inputs_cannot_claim_submission_ready(rehearsal, tmp_path, monkeypatch):
    source = queue(tmp_path); paper = tmp_path/'paper'; paper.mkdir(); (paper/'paper.pdf').write_bytes(b'PDF')
    monkeypatch.setattr(rehearsal, 'audit', lambda _: {'status': 'automated_checks_passed_manual_review_pending'})
    result = rehearsal.rehearse(source, paper, 'a'*40)
    assert not result['ready_for_operator_submission'] and not result['submission_performed']
    assert len(result['blockers']) == 3 and result['public_links'] == []


def test_link_checks_use_fixed_hosts_and_exact_revision(rehearsal):
    seen = []
    def transport(request):
        seen.append(request)
        return httpx.Response(302, headers={'Location': 'http://private.invalid'}, content=b'no redirect')
    with httpx.Client(transport=httpx.MockTransport(transport), follow_redirects=False) as client:
        result = rehearsal.public_links('a'*40, client)
    assert len(seen) == 5 and not any(row['resolved'] for row in result)
    assert all(request.method == 'GET' and request.url.scheme == 'https' for request in seen)
    with pytest.raises(ValueError): rehearsal.public_links('main', None)


def test_private_page_probe_checks_exact_body_and_security_headers(rehearsal, tmp_path):
    path = tmp_path/'page.html'; path.write_bytes(b'private')
    def transport(request):
        assert str(request.url) == 'http://127.0.0.1:8780/artifact-triage.html'
        return httpx.Response(200, content=b'private', headers={'Cache-Control': 'no-store', 'X-Frame-Options': 'DENY'})
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        result = rehearsal.private_page(client, path)
    assert result['matches_private_artifact'] and result['no_store'] and result['frame_denied']


def test_template_redirect_stays_on_google_and_is_bounded(rehearsal):
    seen = []
    def transport(request):
        seen.append(str(request.url))
        if str(request.url) == rehearsal.TEMPLATE:
            return httpx.Response(307, headers={'Location': 'https://doc-01.googleusercontent.com/export'})
        return httpx.Response(200, content=b'bounded template')
    with httpx.Client(transport=httpx.MockTransport(transport), follow_redirects=False) as client:
        rows = rehearsal.public_links('a'*40, client)
    assert len(seen) == 6 and rows[-1]['resolved']
    assert rows[-1]['matches_recorded_template'] is False
