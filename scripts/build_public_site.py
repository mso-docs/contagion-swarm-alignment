"""Add an audited judge overview beside the unchanged frozen dashboard."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from build_dashboard import build as build_dashboard
from final_evidence_inventory import validate_inventory
from freeze_dashboard import validate as validate_freeze
from pdf_publication_guard import validate_public_pdf
from publication_readiness import inspect
from scan_privacy import findings
from security_guard import ROOT, private_values

OVERVIEW_ASSETS = ('index.html', 'style.css')


class OverviewParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.ids = set()
        self.links = []

    def handle_data(self, data):
        self.text.append(data)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {'script', 'iframe', 'form', 'object', 'embed', 'base'} or any(k.startswith('on') for k in attrs):
            raise ValueError('Active overview content rejected')
        if 'id' in attrs:
            if attrs['id'] in self.ids:
                raise ValueError('Duplicate overview identifier')
            self.ids.add(attrs['id'])
        for key in ('href', 'src'):
            if key in attrs:
                self.links.append((tag, attrs[key]))


def validate_overview(html, css, known):
    parser = OverviewParser()
    parser.feed(html)
    for tag, link in parser.links:
        if link.startswith('#'):
            if link[1:] not in parser.ids:
                raise ValueError('Broken overview anchor')
        elif link not in {'./', '../', 'style.css', 'paper.pdf'}:
            url = urlsplit(link)
            if tag != 'a' or url.scheme != 'https' or url.hostname not in {'github.com', 'youtu.be', 'apartresearch.com'} or url.username or url.password or url.query:
                raise ValueError('Unapproved overview link or asset')
    if findings(' '.join(parser.text), public=True, known=known):
        raise ValueError('Overview failed privacy validation')
    if any(value in html or value in css for value in known):
        raise ValueError('Known private overview value rejected')
    if re.search(r'@import|url\s*\(', css, re.I):
        raise ValueError('External CSS resources rejected')


def prepare_overview(root=ROOT):
    root = Path(root)
    known, values = private_values(root, dict(os.environ))
    inventory_path = root/'report/data/final_inventory.json'
    inventory = validate_inventory(inventory_path, values, root/'dashboard/data')
    freeze = validate_freeze(root/'dashboard/data/submission-freeze.json', values, inventory_path)
    counts = inventory.counts
    replacements = {
        'LIVE_ROWS': counts.live_rows, 'LIVE_COMPLETED': counts.live_completed_rows,
        'RESPONSES': f'{counts.live_distinct_returned_responses:,}',
        'MOCK_ROWS': counts.mock_rows, 'NEURAL_CAPTURES': counts.trained_neural_captures,
        'VERIFIED_LIVE': counts.live_distinct_verified_trajectories,
        'CUTOFF': freeze.cutoff_utc,
    }
    content = {}
    for name in OVERVIEW_ASSETS:
        path = root/'site/overview'/name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Invalid overview source')
        content[name] = path.read_text()
    for key, value in replacements.items():
        content['index.html'] = content['index.html'].replace('{{'+key+'}}', str(value))
    if '{{' in content['index.html']:
        raise ValueError('Unresolved overview statistic')
    validate_overview(content['index.html'], content['style.css'], known)
    paper = root/'report/paper.pdf'
    if paper.is_symlink():
        raise ValueError('Paper symlink rejected')
    pdf = paper.read_bytes()
    validate_public_pdf(pdf, known)
    manifest = json.loads((root/'report/data/paper_build_manifest.json').read_text())
    if hashlib.sha256(pdf).hexdigest() != manifest['pdf_sha256']:
        raise ValueError('Published report differs from validated paper')
    return {**{name: text.encode() for name, text in content.items()}, 'paper.pdf': pdf}


def build(output, root=ROOT):
    root, output = Path(root), Path(output)
    overview = prepare_overview(root)
    build_dashboard(root/'dashboard', output)
    # Inspect the dashboard in isolation before adding the separate overview.
    # Its strict allowlist and immutable freeze remain unchanged.
    inspect(root/'dashboard', output, root/'.github/workflows/pages.yml')
    (output/'overview').mkdir()
    for name, data in overview.items():
        (output/'overview'/name).write_bytes(data)
    print('Added 3 audited overview files; frozen dashboard bytes unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        build(args.out)
    except Exception as exc:
        parser.exit(1, 'Public site build blocked ('+type(exc).__name__+'); no private values printed.\n')
