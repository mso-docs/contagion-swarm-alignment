"""Read-only human-calibration and submission rehearsal; never submits or invents labels."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from calibrate_review import calibrate
from run_pilot import ROOT
from submission_audit import audit

MANUAL_KEYS = ('claims_and_citations_reviewed', 'official_template_compared',
               'public_revision_reviewed', 'figures_reviewed')
GUIDELINES = 'https://apartresearch.com/sprints/swarm-alignment-2026'
TEMPLATE = 'https://docs.google.com/document/d/1_1_27EyZriMlc8n8EBE2YScaeyMjm-8xjR097nmHXAE/export?format=docx'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def human_gate(queue, human=None, second_human=None):
    """Read only actual saved labels; unreviewed/ambiguous samples keep the gate open."""
    queue = Path(queue)
    human = Path(human) if human else queue/'human_labels.csv'
    local = calibrate(queue, human, second_human, queue/'judge-results.private.json')
    second_path = queue/'second-judge-results.private.json'
    frontier = calibrate(queue, human, judge=second_path) if second_path.exists() else None
    return {
        'status': local['status'], 'selected_samples': local['selected_samples'],
        'human_completed': local['human_completed'], 'human_unresolved': local['human_unresolved'],
        'fully_adjudicated': local['fully_adjudicated'],
        'local_judge': local.get('judge_against_human'),
        'frontier_judge': frontier.get('judge_against_human') if frontier else None,
        'objective_scorer': local['objective_scorer_against_human'],
        'inter_rater': local.get('inter_rater'),
        'input_sha256': sha(queue/'review_inputs.json'), 'human_labels_sha256': sha(human),
        'limitations': ['Judge-informed selected audit; metrics are not population accuracy or prevalence.',
                       'Frontier metrics use only its predeclared covered intersection.',
                       'One human annotator does not establish independent inter-rater validity.',
                       'Saved CSV provenance is operator asserted; this tool cannot prove who labeled it.'],
    }


def manual_gate(path, pdf_hash, code_revision):
    if path is None:
        return {'status': 'pending_author_attestation', 'checks': dict.fromkeys(MANUAL_KEYS, False)}
    data = json.loads(Path(path).read_text())
    expected = {'schema_version', 'paper_sha256', 'code_revision', 'reviewed_utc', 'checks'}
    if set(data) != expected or data['schema_version'] != 'submission-author-attestation-1.0':
        raise ValueError('Invalid author attestation schema')
    if data['paper_sha256'] != pdf_hash or data['code_revision'] != code_revision:
        raise ValueError('Author attestation does not match this PDF/code revision')
    checks = data['checks']
    if set(checks) != set(MANUAL_KEYS) or any(type(v) is not bool for v in checks.values()):
        raise ValueError('Author checks must contain explicit boolean decisions')
    stamp = datetime.fromisoformat(data['reviewed_utc'].replace('Z', '+00:00'))
    if stamp.tzinfo is None or stamp > datetime.now(timezone.utc):
        raise ValueError('Author review requires a past timezone-aware timestamp')
    return {'status': 'operator_attested' if all(checks.values()) else 'pending_author_review',
            'checks': checks, 'attestation_sha256': sha(path),
            'provenance': 'Operator declaration; not independent verification or submission confirmation.'}


def public_links(revision, client):
    if len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision):
        raise ValueError('Use an exact public Git revision')
    base = 'https://github.com/mso-docs/contagion-swarm-alignment'
    urls = [GUIDELINES, base, base+'/tree/'+revision,
            base+'/blob/'+revision+'/report/data/compact_evidence.json', TEMPLATE]
    rows = []
    for url in urls:
        try:
            current = url
            for attempt in range(4):
                with client.stream('GET', current) as response:
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > 4*1024*1024:
                            raise ValueError('Public link response exceeds bounded review limit')
                    status = response.status_code
                    if url == TEMPLATE and status in {301, 302, 303, 307, 308}:
                        target = urljoin(current, response.headers.get('location', ''))
                        parsed = urlsplit(target)
                        host = parsed.hostname or ''
                        if (attempt == 3 or parsed.scheme != 'https' or parsed.username or parsed.password
                            or parsed.port not in {None, 443} or not
                            (host.endswith('.google.com') or host.endswith('.googleusercontent.com'))):
                            raise ValueError('Disallowed or excessive official-template redirect')
                        current = target
                        continue
                    break
            row = {'url': url, 'http_status': status, 'resolved': status == 200,
                   'content_sha256': hashlib.sha256(content).hexdigest()}
            if url == TEMPLATE:
                row['matches_recorded_template'] = row['content_sha256'] == json.loads(
                    (ROOT/'report/template_format.json').read_text())['docx_sha256']
            rows.append(row)
        except (httpx.HTTPError, ValueError) as exc:
            rows.append({'url': url, 'resolved': False, 'error_type': type(exc).__name__})
    return rows


def private_page(client, page):
    """Check the fixed loopback-only route without exporting its body."""
    try:
        response = client.get('http://127.0.0.1:8780/artifact-triage.html')
        return {'checked': True, 'available': response.status_code == 200,
                'matches_private_artifact': response.status_code == 200 and
                    hashlib.sha256(response.content).hexdigest() == sha(page),
                'no_store': response.headers.get('Cache-Control') == 'no-store',
                'frame_denied': response.headers.get('X-Frame-Options') == 'DENY'}
    except httpx.HTTPError as exc:
        return {'checked': True, 'available': False, 'error_type': type(exc).__name__}


def rehearse(queue, paper_dir, revision, human=None, second_human=None, attestation=None,
             check_links=False, check_local=False, client=None):
    pdf_hash = sha(Path(paper_dir)/'paper.pdf')
    human_result = human_gate(queue, human, second_human)
    paper_result = audit(paper_dir)
    manual = manual_gate(attestation, pdf_hash, revision)
    links = public_links(revision, client) if check_links else []
    local = private_page(client, Path(queue)/'artifact-triage.html') if check_local else {'checked': False}
    technical = paper_result['status'] == 'automated_checks_passed_manual_review_pending'
    link_pass = bool(links) and all(row['resolved'] for row in links)
    template_match = any(row.get('matches_recorded_template') is True for row in links)
    blockers = []
    if not human_result['fully_adjudicated']: blockers.append('Complete and resolve the selected human audit.')
    if not technical: blockers.append('Rebuild or correct the PDF and rerun automatic checks.')
    if manual['status'] != 'operator_attested': blockers.append('Author must review claims, figures, template and public revision.')
    if not link_pass: blockers.append('Verify all fixed public reproducibility and official links.')
    if check_links and not template_match and not manual['checks']['official_template_compared']:
        blockers.append('Current template differs or could not be verified; compare manually.')
    return {'schema_version': 'submission-rehearsal-1.0',
            'created_utc': datetime.now(timezone.utc).isoformat(), 'paper_sha256': pdf_hash,
            'code_revision': revision, 'human_audit': human_result, 'paper_audit': paper_result,
            'author_review': manual, 'public_links': links, 'private_review_page': local,
            'ready_for_operator_submission': not blockers, 'blockers': blockers,
            'warnings': ['Scorer/human divergence is preliminary; report supplied labels and flags separately, without established accuracy claims.']
                if human_result['objective_scorer']['fp']+human_result['objective_scorer']['fn'] else [],
            'submission_performed': False, 'submission_confirmation': 'Not obtained by this tool.',
            'next_action': 'Upload the reviewed PDF through the official form and retain confirmation.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue', type=Path, default=ROOT/'results/reviews/workspaces/triage')
    parser.add_argument('--paper-dir', type=Path, default=ROOT/'results/paper-draft')
    parser.add_argument('--revision')
    parser.add_argument('--human', type=Path)
    parser.add_argument('--second-human', type=Path)
    parser.add_argument('--author-attestation', type=Path)
    parser.add_argument('--check-links', action='store_true')
    parser.add_argument('--check-local', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    revision = args.revision or subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
        text=True, capture_output=True, check=True).stdout.strip()
    with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as http:
        result = rehearse(args.queue, args.paper_dir, revision, args.human, args.second_human,
                          args.author_attestation, args.check_links, args.check_local, http)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print('Submission rehearsal:', result['human_audit']['human_completed'], '/',
          result['human_audit']['selected_samples'], 'human labels;', len(result['blockers']),
          'remaining gates; no submission performed.')
