"""Read-only submission checks; manual scientific/template review stays explicit."""
import argparse
import hashlib
import json
from pathlib import Path
from build_paper import inspect_pdf,validate_rq3_followup
from run_pilot import ROOT


def audit(directory):
    directory=Path(directory);checks=inspect_pdf(directory/'paper.pdf',directory/'paper.log',directory/'paper.tex')
    manifest=json.loads((directory/'build_manifest.json').read_text())
    files={'latex_source_sha256':ROOT/'report/paper.tex','bibliography_sha256':ROOT/'report/sources.bib','analysis_script_sha256':ROOT/'scripts/paper_analysis.py','notebook_source_sha256':ROOT/'notebooks/paper_figures.ipynb',
           'rq3_followup_sha256':ROOT/'report/data/rq3_followup.json','build_script_sha256':ROOT/'scripts/build_paper.py'}
    stale=[key for key,path in files.items() if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest.get(key)]
    validate_rq3_followup(json.loads((ROOT/'report/data/rq3_followup.json').read_text()),(ROOT/'report/paper.tex').read_text())
    checks.update(status='stale_build' if stale else 'automated_checks_passed_manual_review_pending',stale_inputs=stale,
        guidelines='https://apartresearch.com/sprints/swarm-alignment-2026',
        deadline='2026-11-08 23:59 AoE = 2026-11-09 06:59 America/New_York',
        manual_requirements=['Author reviews all claims, citations and selected figures.','Side-by-side comparison with current official template; LaTeX is a reconstructed layout.',
                             'Confirm public reproducibility links resolve to reviewed code/data revision.','Complete human artifact audit and disclose remaining unadjudicated outcomes.',
                             'Submit the PDF through the official form and retain confirmation.'],
        research_status={'rq1':'Compact temporal finding; topology causality unresolved.','rq2':'Original catalog recall undefined; intermediate patch follow-up is a separate post-hoc endpoint.',
                         'rq3':'Separate64-run follow-up completed; zero attempts/state violations/refusals, four case clusters; no refusal-bypass conclusion.','neural':'Reference checkpoint only; no swarm mechanistic claim.'})
    return checks


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--paper-dir',type=Path,default=ROOT/'results/paper-draft');p.add_argument('--out',type=Path);a=p.parse_args()
    result=audit(a.paper_dir)
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(result['status']);print('Main text:',result['main_text_pages'],'pages; abstract:',result['abstract_words'],'words; manual review/submission not inferred.')
