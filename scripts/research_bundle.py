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
from security_guard import private_values
from scan_privacy import scan_blob,findings

ROOT=Path(__file__).resolve().parents[1]
TEXT_FILES=[
    'README.md','AGENTS.md','CONTAGION_AGENT_MVP_SPEC.md','pyproject.toml','requirements.lock.txt',
    'report/paper.tex','report/sources.bib','report/template_format.json','report/RESEARCH_READINESS.md',
    'report/data/compact_evidence.json','report/data/rq3_followup.json',
    'notebooks/paper_figures.ipynb',
    'scripts/paper_analysis.py','scripts/build_paper.py',
    'scripts/execute_notebook.py','scripts/submission_audit.py','scripts/run_pilot.py',
    'scripts/security_guard.py','scripts/scan_privacy.py','scripts/repository_publication.py','scripts/freeze_rq3_followup.py','scripts/research_bundle.py',
]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean_checkout_smoke(source):
    """Recompute frozen figures from a source-only copy, without inference/network."""
    source=Path(source)
    with TemporaryDirectory(prefix='contagion-offline-smoke-') as temporary:
        root=Path(temporary)
        for name in ['src','scripts','report','notebooks']:
            if (source/name).is_dir():shutil.copytree(source/name,root/name)
        env=dict(os.environ,PYTHONPATH=str(root/'src'),MPLCONFIGDIR=str(root/'mpl-cache'),
                 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        with (root/'smoke.log').open('w') as log:
            subprocess.run([sys.executable,str(root/'scripts/paper_analysis.py'),'figures',
                '--evidence',str(root/'report/data/compact_evidence.json'),'--out',str(root/'figures')],
                cwd=root,env=env,stdout=log,stderr=log,check=True,timeout=120)
        manifest=json.loads((root/'figures/figure_manifest.json').read_text())
        if manifest['evidence_sha256']!=sha(root/'report/data/compact_evidence.json'):raise ValueError('Smoke used a different evidence freeze')
        return {'status':'passed','completed_primary_runs':manifest['complete_runs'],'generated_figure_files':len(manifest['files']),
                'environment':'Existing installed analysis dependencies; fresh dependency installation not tested.',
                'scope':'Source-only temporary copy; offline figure generation; no inference or raw logs.'}


def build(output,paper=ROOT/'results/paper-draft',root=ROOT,smoke=True):
    root=Path(root).resolve();output=Path(output).resolve();paper=Path(paper).resolve()
    if (root/'results').resolve() not in output.parents:raise ValueError('Bundle output must remain under ignored results')
    if output.exists():raise ValueError('Use a fresh output directory')
    from submission_audit import audit
    audit_result=audit(paper)
    if audit_result['status']=='stale_build':raise ValueError('Rebuild stale paper before packaging')
    build_manifest=json.loads((paper/'build_manifest.json').read_text())
    if sha(paper/'paper.pdf')!=build_manifest['pdf_sha256']:raise ValueError('PDF differs from its recorded build')
    known,_=private_values(ROOT,dict(os.environ));output.mkdir(parents=True)
    source_files=[*TEXT_FILES,*[str(p.relative_to(root)) for p in sorted((root/'src/contagion').glob('*.py'))]]
    copied=[]
    def copy(source,target,binary=False):
        source=Path(source)
        if source.is_symlink() or not source.is_file():raise ValueError('Missing or symlink bundle input')
        if not binary:
            blob=source.read_bytes()
            if scan_blob(blob,public=source.suffix in {'.json','.ipynb'},known=known):raise ValueError('Bundle input failed privacy lint')
        destination=output/target;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination);copied.append(target)
    for name in source_files:copy(root/name,name)
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
              'offline_smoke':smoke_result,'files':{name:sha(output/name) for name in sorted(copied)},
              'pending':['Independent human adjudication and judge calibration.','Final official-template comparison and author scientific review.',
                         'Verify public links resolve to a reviewed revision.','Submit via official form and retain confirmation.'],
              'limitations':['Only frozen compact evidence is packaged; ongoing experiments remain separate.',
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
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--paper-dir',type=Path,default=ROOT/'results/paper-draft');p.add_argument('--skip-smoke',action='store_true');a=p.parse_args()
    result=build(a.out,a.paper_dir,smoke=not a.skip_smoke)
    print('Research bundle prepared:',len(result['files']),'allowlisted files; offline smoke',result['offline_smoke']['status'],'; human review/submission remain pending.')
