"""Create an allowlisted research bundle; raw logs, private reviews and env stay out."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory

from contagion.storage import source_fingerprint
from security_guard import private_values,source_configuration_values
from scan_privacy import scan_blob,findings

ROOT=Path(__file__).resolve().parents[1]
TEXT_FILES=[
    'README.md','AGENTS.md','LICENSE','CONTAGION_AGENT_MVP_SPEC.md','pyproject.toml','requirements.lock.txt','requirements-bootstrap.txt',
    'report/paper.tex','report/sources.bib','report/template_format.json','report/RESEARCH_READINESS.md',
    'report/data/compact_evidence.json','report/data/rq3_followup.json',
    'report/data/human_audit.json','report/data/patch_pointer_audit.json',
    'report/data/submission_snapshot/public.json','report/data/submission_snapshot/safeguard.json','report/data/submission_snapshot/RQ_ASSESSMENT.md',
    'notebooks/paper_figures.ipynb',
    'scripts/paper_analysis.py','scripts/build_paper.py',
    'scripts/execute_notebook.py','scripts/submission_audit.py','scripts/run_pilot.py',
    'scripts/security_guard.py','scripts/scan_privacy.py','scripts/repository_publication.py','scripts/freeze_rq3_followup.py','scripts/research_bundle.py',
    'scripts/submission_snapshot.py','scripts/submission_rehearsal.py','scripts/safeguard_figure.py',
    'scripts/patch_pointer_audit.py','scripts/import_human_audit.py','scripts/paper_supplement.py',
    'scripts/calibrate_review.py','scripts/build_review_workspace.py',
    'docs/SUBMISSION_SNAPSHOT.md','docs/SUBMISSION_REHEARSAL.md','docs/RQ_ASSESSMENT.md',
    'docs/SUBMISSION_RUNBOOK.md','docs/SUBMISSION_DEMO.md',
    'docs/PRIMARY_RQ1_VALIDITY.md',
]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_text(blob,suffix,known,values):
    """Check private literals explicitly, including non-public source documents."""
    public=suffix in {'.json','.ipynb'}
    candidate_known=known if public else source_configuration_values(known,values)
    if any(value.encode() in blob for value in candidate_known) or scan_blob(blob,public=public,known=candidate_known):
        raise ValueError('Bundle input failed privacy lint')


def clean_checkout_smoke(source):
    """Recompute frozen figures from a source-only copy, without inference/network."""
    source=Path(source)
    with TemporaryDirectory(prefix='contagion-offline-smoke-') as temporary:
        root=Path(temporary)
        for name in ['src','scripts','report','notebooks']:
            if (source/name).is_dir():shutil.copytree(source/name,root/name)
        env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(root/'src'),str(root/'scripts')]),MPLCONFIGDIR=str(root/'mpl-cache'),
                 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        with (root/'smoke.log').open('w') as log:
            subprocess.run([sys.executable,str(root/'scripts/paper_analysis.py'),'figures',
                '--evidence',str(root/'report/data/compact_evidence.json'),'--out',str(root/'figures')],
                cwd=root,env=env,stdout=log,stderr=log,check=True,timeout=120)
            subprocess.run([sys.executable,'-c','from paper_supplement import render; text, hashes = render(); assert text and hashes'],
                cwd=root,env=env,stdout=log,stderr=log,check=True,timeout=120)
        manifest=json.loads((root/'figures/figure_manifest.json').read_text())
        if manifest['evidence_sha256']!=sha(root/'report/data/compact_evidence.json'):raise ValueError('Smoke used a different evidence freeze')
        return {'status':'passed','completed_primary_runs':manifest['complete_runs'],'generated_figure_files':len(manifest['files']),
                'environment':'Existing installed analysis dependencies; fresh dependency installation not tested.',
                'scope':'Source-only temporary copy; offline figure and validated supplement generation; no inference or raw logs.'}


def build(output,paper=ROOT/'results/paper-draft',root=ROOT,smoke=True,snapshot=None):
    root=Path(root).resolve();output=Path(output).resolve();paper=Path(paper).resolve()
    if (root/'results').resolve() not in output.parents:raise ValueError('Bundle output must remain under ignored results')
    if output.exists():raise ValueError('Use a fresh output directory')
    from submission_snapshot import validate as validate_snapshot
    fixed_snapshot=validate_snapshot(root/'report/data/submission_snapshot')
    from submission_audit import audit
    audit_result=audit(paper)
    if audit_result['status']=='stale_build':raise ValueError('Rebuild stale paper before packaging')
    build_manifest=json.loads((paper/'build_manifest.json').read_text())
    if sha(paper/'paper.pdf')!=build_manifest['pdf_sha256']:raise ValueError('PDF differs from its recorded build')
    known,values=private_values(ROOT,dict(os.environ));output.mkdir(parents=True)
    source_files=[*TEXT_FILES,*[str(p.relative_to(root)) for p in sorted((root/'src/contagion').glob('*.py'))]]
    copied=[]
    def copy(source,target,binary=False):
        source=Path(source)
        if source.is_symlink() or not source.is_file():raise ValueError('Missing or symlink bundle input')
        if not binary:
            blob=source.read_bytes()
            validate_text(blob,source.suffix,known,values)
        destination=output/target;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination);copied.append(target)
    for name in source_files:copy(root/name,name)
    snapshot_provenance=None
    if snapshot is not None:
        validate_snapshot(snapshot)
        for name in ['public.json','safeguard.json','RQ_ASSESSMENT.md']:
            copy(Path(snapshot)/name,'submission-snapshot/'+name)
        snapshot_provenance={name:sha(Path(snapshot)/name) for name in ['public.json','safeguard.json','RQ_ASSESSMENT.md']}
    from pypdf import PdfReader
    if findings('\n'.join(page.extract_text() or '' for page in PdfReader(paper/'paper.pdf').pages),known=known):raise ValueError('PDF privacy check failed')
    copy(paper/'paper.pdf','paper/paper.pdf',binary=True)
    figure_manifest=json.loads((paper/'figures/figure_manifest.json').read_text())
    for name,want in figure_manifest['files'].items():
        if Path(name).name!=name or sha(paper/'figures'/name)!=want:raise ValueError('Figure integrity check failed')
        copy(paper/'figures'/name,'paper/figures/'+name,binary=Path(name).suffix in {'.pdf','.png'})
    copy(paper/'figures/figure_manifest.json','paper/figure_manifest.json')
    for name in ['completed_runs.csv','task_summary.csv']:
        copy(paper/'figures'/name,'paper/'+name)
    versions=build_manifest.get('installed_versions',{})
    (output/'analysis-environment.txt').write_text('\n'.join(name+'=='+version for name,version in sorted(versions.items()))+'\n');copied.append('analysis-environment.txt')
    revision=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
    dirty=bool(subprocess.run(['git','status','--porcelain'],cwd=root,capture_output=True,text=True,check=True).stdout.strip())
    smoke_result=clean_checkout_smoke(output) if smoke else {'status':'not_run'}
    manifest={'schema_version':'research-bundle-1.0','code_revision':revision,'workspace_has_uncommitted_changes':dirty,
              'code_review_status':'Human review pending; revision is not a certification.','source_fingerprint':source_fingerprint(),
              'paper_checks':{k:audit_result[k] for k in ['status','main_text_pages','total_pages','abstract_words']},
              'paper_rendering':{k:build_manifest.get(k) for k in ['typeface_variant','pdf_font_names','authoring_source_sha256','compiledlatex_source_sha256','pdf_sha256']},
              'offline_smoke':smoke_result,'files':{name:sha(output/name) for name in sorted(copied)},
              'supplemental_snapshot_sha256':snapshot_provenance,
              'tracked_snapshot_hash':fixed_snapshot.snapshot_hash,
              'pending':['Broader independent adjudication and rubric reconciliation; selected single-reviewer audit is included.','Final official-template comparison and author scientific review.',
                         'Verify public links resolve to a reviewed revision.','Submit via official form and retain confirmation.'],
              'limitations':['Paper uses frozen compact and separate RQ3 evidence; an optional cutoff snapshot is a separate supplement, not a paper-narrative update.',
                             'No private review inputs, raw events, upstream source diffs, endpoints, credentials or original tensors.',
                             'Exact installed versions describe the build environment; other operating systems may need compatible wheels.']}
    (output/'bundle-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    archive=output.with_suffix('.tar.gz')
    if archive.exists():raise ValueError('Archive already exists')
    with archive.open('xb') as stream,gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as zipped,tarfile.open(fileobj=zipped,mode='w') as tar:
        for path in sorted(output.rglob('*')):
            if not path.is_file():continue
            info=tar.gettarinfo(str(path),arcname=str(path.relative_to(output)));info.mtime=0;info.uid=0;info.gid=0;info.uname='';info.gname=''
            with path.open('rb') as blob:tar.addfile(info,blob)
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--paper-dir',type=Path,default=ROOT/'results/paper-draft');p.add_argument('--skip-smoke',action='store_true');p.add_argument('--snapshot',type=Path);a=p.parse_args()
    result=build(a.out,a.paper_dir,smoke=not a.skip_smoke,snapshot=a.snapshot)
    print('Research bundle prepared:',len(result['files']),'allowlisted files; offline smoke',result['offline_smoke']['status'],'; human review/submission remain pending.')
