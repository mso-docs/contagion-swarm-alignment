"""Package reviewed-source candidates; never deploys, merges or submits anything."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

from run_pilot import ROOT


def validate_pair(classic,template):
    if classic.get('typeface_variant')!='classic' or template.get('typeface_variant')!='template':raise ValueError('Need both explicit font variants')
    scientific=('authoring_source_sha256','evidence_sha256','rq3_followup_sha256','pointer_audit_sha256',
                'human_audit_sha256','submission_snapshot_sha256','notebook_source_sha256','analysis_script_sha256','bibliography_sha256')
    if any(not classic.get(k) or classic[k]!=template.get(k) for k in scientific):raise ValueError('PDF variants do not share the same scientific source')
    if classic.get('pdf_sha256')==template.get('pdf_sha256'):raise ValueError('Font variants must have distinct verified PDF files')
    return {key:classic[key] for key in scientific}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(output,classic,template,artifact):
    from submission_audit import audit
    from publication_readiness import inspect
    from research_bundle import build
    output=Path(output);classic=Path(classic);template=Path(template);artifact=Path(artifact)
    if (ROOT/'results').resolve() not in output.resolve().parents or output.exists():raise ValueError('Use a fresh private review directory under results')
    dirty=subprocess.run(['git','status','--porcelain'],cwd=ROOT,capture_output=True,text=True,check=True).stdout
    if dirty.strip():raise ValueError('Commit validated source before creating the final review packet')
    from security_guard import check
    if check(ROOT,'worktree')!=0:raise ValueError('Source archive failed the publication privacy guard')
    for paper in (classic,template):
        if audit(paper)['status']!='automated_checks_passed_manual_review_pending':raise ValueError('Paper is stale or failed automatic checks')
    manifests=[json.loads((paper/'build_manifest.json').read_text()) for paper in (classic,template)]
    evidence=validate_pair(*manifests);site=inspect(ROOT/'dashboard',artifact)
    output.mkdir(parents=True)
    for paper,name in [(classic,'paper-classic.pdf'),(template,'paper-template.pdf')]:shutil.copyfile(paper/'paper.pdf',output/name)
    revision=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    subprocess.run(['git','archive','--format=tar.gz','--output',str((output/'source-code.tar.gz').resolve()),revision],cwd=ROOT,check=True)
    build(output/'research-bundle',paper=template,snapshot=ROOT/'report/data/submission_snapshot')
    with zipfile.ZipFile(output/'pages-preview.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(artifact.rglob('*')):
            if path.is_file():archive.write(path,str(path.relative_to(artifact)))
    (output/'REVIEW.md').write_text(
        '# Final author review packet\n\n'
        'Open paper-classic.pdf for the requested LaTeX serif. '
        'paper-template.pdf uses the official template typefaces. Both share the same source and numerical evidence.\n\n'
        'The source archive contains the exact committed tree without Git history or ignored runtime/private files. '
        'The research bundle reproduces figures and validated supplements offline. '
        'The Pages ZIP is a static, privacy-checked preview; it has not been deployed.\n\n'
        'Review claims, citations, figures, exclusions, ethical limitations and the selected font/template before submission. '
        'Run counts are not independent sample sizes. Benchmark adaptations and mocks are labeled separately. '
        'Live collection outside the paper cutoff does not revise this paper automatically.\n\n'
        'Actual GitHub publication and hackathon submission remain operator actions. No submission was performed.\n')
    files={str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
    report={'schema_version':'author-review-packet-1.0','code_revision':revision,'scientific_inputs':evidence,
            'paper_variants':{m['typeface_variant']:{k:m[k] for k in ('pdf_sha256','main_text_pages','total_pages','abstract_words','pdf_font_names')} for m in manifests},
            'site_technical_status':site['technical_status'],'site_asset_count':site['artifact_files'],
            'source_privacy_validation':'passed','source_archive_scope':'Exact committed tree; Git history and ignored runtime/private files excluded.',
            'files_sha256':files,'author_review_completed':False,'public_access_verified':False,
            'hackathon_submission_performed':False,'automatic_claims_include_future_runs':False}
    (output/'review-manifest.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--classic',type=Path,default=ROOT/'results/paper-classic-final')
    parser.add_argument('--template',type=Path,default=ROOT/'results/paper-template-final');parser.add_argument('--artifact',type=Path,required=True)
    args=parser.parse_args();result=prepare(args.out,args.classic,args.template,args.artifact)
    print('Author review packet prepared for commit',result['code_revision'][:12],'; no deployment or submission.')
