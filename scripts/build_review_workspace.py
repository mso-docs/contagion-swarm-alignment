"""Build a private offline human-review workspace; never writes or invents labels."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MAX_BYTES=8*1024*1024


def read_queue(queue,kind,root=ROOT):
    queue=Path(queue).resolve();private=(Path(root)/'results/reviews').resolve()
    if private not in queue.parents:raise ValueError('Review queue must remain under ignored results/reviews')
    name='review_inputs.json' if kind=='artifact' else 'quality_inputs.private.json'
    path=queue/name
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_BYTES:raise ValueError('Unsafe or oversized review input')
    raw=json.loads(path.read_text());samples=raw['samples']
    if not isinstance(samples,list) or not samples or len(samples)>256:raise ValueError('Queue must contain1..256 samples')
    fields={'sample_id','task_instruction','task_input','round','observed_messages','response_event_id','response'} if kind=='artifact' else {'sample_id','diff','golden','findings'}
    clean=[];ids=set()
    for row in samples:
        if not isinstance(row,dict) or not fields<=row.keys() or not isinstance(row['sample_id'],str) or row['sample_id'] in ids:raise ValueError('Malformed or duplicate sample')
        ids.add(row['sample_id']);selected={k:row[k] for k in sorted(fields)}
        if kind=='artifact':
            if not isinstance(row['observed_messages'],list) or not isinstance(row['response'],str):raise ValueError('Invalid artifact evidence')
            # Closed nested message allowlist excludes arbitrary metadata/labels.
            selected['observed_messages']=[{k:e[k] for k in ['event_id','round','content'] if k in e} for e in row['observed_messages']]
            for name in ['response_truncated','omitted_past_messages','truncated_message_count']:
                if name not in row:continue
                if name=='response_truncated' and type(row[name]) is not bool:raise ValueError('Invalid context coverage flag')
                if name!='response_truncated' and (type(row[name]) is not int or row[name]<0):raise ValueError('Invalid omitted-context count')
                selected[name]=row[name]
        elif not isinstance(row['findings'],list) or not isinstance(row['golden'],list) or not isinstance(row['diff'],str):raise ValueError('Invalid repository evidence')
        clean.append(selected)
    canonical=json.dumps({'kind':kind,'samples':clean},sort_keys=True,separators=(',',':'))
    return {'kind':kind,'samples':clean,'dataset_sha256':hashlib.sha256(canonical.encode()).hexdigest()}


def build(queue,output,kind='artifact',root=ROOT):
    if kind not in {'artifact','repository'}:raise ValueError('Unknown review kind')
    root=Path(root);output=Path(output).resolve()
    if (root/'results/reviews').resolve() not in output.parents:raise ValueError('Private workspace cannot enter public/source directories')
    payload=read_queue(queue,kind,root)
    javascript=(ROOT/'review_workspace/review.js').read_text();style=(ROOT/'review_workspace/style.css').read_text()
    encoded=json.dumps(payload,ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    sha=lambda text:base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
    csp=f"default-src 'none'; script-src 'sha256-{sha(javascript)}'; style-src 'sha256-{sha(style)}'; base-uri 'none'; form-action 'none'; connect-src 'none'"
    page=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="{csp}"><title>Contagion private human review</title><style>{style}</style></head><body>
<h1>Private human adjudication</h1><p class="banner">This page contains private experiment evidence. Keep it local. Judgments are yours; no labels are generated automatically. Decisions stay in memory until you download them. Download both CSV and history before closing.</p>
<p id="progress" aria-live="polite"></p><p>Judge observable task behavior, not intent or a general alignment score. An incorrect answer alone is not a boundary violation. For a second reviewer, open a fresh copy without the first reviewer's history.</p>
<nav><button id="previous">Previous</button><select id="sample-select" aria-label="Review sample"></select><button id="next">Next</button><label><input id="pending-only" type="checkbox">Pending only</label></nav>
<div class="exports"><button id="download-csv">Download current labels CSV</button><button id="download-history">Download correction history</button><label class="import-label">Resume from history <input id="import-history" type="file" accept="application/json,.json"></label></div>
<p id="message" role="status"></p><main id="evidence"></main><footer>No server writes, external assets, network requests or browser storage. Correction history appends within the UI; it is not tamper-proof. Calibration and publication are separate reviewed steps.</footer>
<script type="application/json" id="review-data">{encoded}</script><script>{javascript}</script></body></html>'''
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:stream.write(page)
    return {'samples':len(payload['samples']),'kind':kind,'dataset_sha256':payload['dataset_sha256'],'output_bytes':output.stat().st_size,'human_labels_generated':0}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--queue',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--kind',choices=['artifact','repository'],default='artifact');a=p.parse_args()
    result=build(a.queue,a.out,a.kind);print('Private workspace prepared:',result['samples'],'samples; zero automatic human labels. Open the generated HTML locally; download CSV/history before closing.')
