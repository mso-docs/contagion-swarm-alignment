"""Execute the figure-review notebook and compile the template-matched LaTeX PDF."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def validate_draft_evidence(data):
    done=[r for r in data['runs'] if r['status']=='completed']
    injected=[r for r in done if r['family']=='patch' and r['condition']=='benign_override']
    if len(done)!=36 or sum(r['responses'] for r in data['runs'])!=941 or len(injected)!=6:
        raise ValueError('Draft narrative no longer matches the evidence freeze')
    if any(r['final_any_violation'] for r in done) or sum(r['any_round_violation'] for r in injected)!=6:
        raise ValueError('Revise transient/final claims before rebuilding the paper')
    if sum(sum(r['round_downstream_violations']) for r in injected)!=17 or sum(r['direct_injection_deliveries'] for r in injected)!=20:
        raise ValueError('Revise temporal/exposure claims before rebuilding')
    if len(data['rq3_development'])!=8 or len(data['neural'])!=6:
        raise ValueError('Revise pilot coverage claims before rebuilding')


def generated_table(data):
    from collections import defaultdict
    rows=defaultdict(list)
    for row in data['runs']:
        if row['status']=='completed':rows[(row['family'],row['condition'])].append(row)
    text=[r'\begin{table}[htbp]\centering\small',r'\caption{Compact held-out counts: any-round and final violations are different endpoints. Mean task success uses final agent artifacts within each run. Each row has one task case and two seeds across three graphs.}',r'\begin{tabular}{llrrrr}\toprule',r'Task & Condition & Runs & Any-round & Final & Task success\\\midrule']
    for (family,condition),items in sorted(rows.items()):
        text.append(f"{family.title()} & {'Control' if condition=='none' else 'Injected'} & {len(items)} & {sum(r['any_round_violation'] for r in items)} & {sum(r['final_any_violation'] for r in items)} & {sum(r['task_success'] for r in items)/len(items):.3f}"+r'\\')
    return '\n'.join([*text,r'\bottomrule\end{tabular}\label{tab:outcomes}\end{table}'])+'\n'


def inspect_pdf(path,log,source):
    from pypdf import PdfReader
    from scan_privacy import findings
    from security_guard import private_values
    reader=PdfReader(path);text='\n'.join(page.extract_text() or '' for page in reader.pages).replace('’',"'")
    match=re.search(r'MAIN_TEXT_PAGES=(\d+)',Path(log).read_text())
    if not match:raise ValueError('Main-text page count missing')
    main_pages=int(match.group(1))
    abstract=Path(source).read_text().split(r'\begin{abstract}',1)[1].split(r'\end{abstract}',1)[0]
    words=len(abstract.split())
    if main_pages>8 or not 150<=words<=250:raise ValueError('Submission length limit exceeded')
    for page in reader.pages:
        if abs(float(page.mediabox.width)-612)>1 or abs(float(page.mediabox.height)-792)>1:raise ValueError('Expected US Letter PDF')
    required=["Mackenzie O'Brien",'Mac Labs AI','Abstract','References','Dual-Use']
    if any(value not in text for value in required):raise ValueError('Required paper content missing')
    known,_=private_values(ROOT,dict(os.environ))
    if findings(text,public=False) or any(value in text for value in known):raise ValueError('PDF extracted-text privacy gate failed')
    if any(value in text for value in ['PROJECT TITLE','Author name 1','TODO','TBD','??']):raise ValueError('Unresolved draft placeholder/reference')
    return {'main_text_pages':main_pages,'total_pages':len(reader.pages),'abstract_words':words,'paper_size':'US Letter',
            'privacy_extracted_text_passed':True,'author':'Mackenzie O\'Brien','affiliation':'Independent AI Researcher, Mac Labs AI',
            'status':'research draft; human scientific review pending'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'results/paper-draft')
    parser.add_argument('--compiler',type=Path,default=ROOT/'.cache/report-tools/tectonic')
    parser.add_argument('--skip-notebook',action='store_true')
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    os.environ['CONTAGION_PAPER_OUT']=str(out)
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'));os.environ.setdefault('IPYTHONDIR',str(ROOT/'.cache/ipython'))
    if not args.skip_notebook:
        import nbformat
        from nbclient import NotebookClient
        from jupyter_client import KernelManager
        notebook=nbformat.read(ROOT/'notebooks/paper_figures.ipynb',as_version=4)
        # Short, private IPC paths avoid both global kernelspec changes and TCP listeners.
        from tempfile import TemporaryDirectory
        (ROOT/'.cache').mkdir(exist_ok=True)
        with TemporaryDirectory(prefix='paper-ipc-',dir=ROOT/'.cache') as kernel_dir:
            km=KernelManager(kernel_name='python3',transport='ipc',ip=str(Path(kernel_dir)/'k'))
            km.kernel_spec.argv=[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}']
            try:
                NotebookClient(notebook,km=km,timeout=600,resources={'metadata':{'path':str(ROOT)}}).execute()
            finally:
                if km.has_kernel:km.shutdown_kernel(now=True)
                km.cleanup_resources()
        notebook.metadata['contagion_source_sha256']=hashlib.sha256((ROOT/'notebooks/paper_figures.ipynb').read_bytes()).hexdigest()
        nbformat.write(notebook,out/'paper_figures.executed.ipynb')
    evidence=ROOT/'report/data/compact_evidence.json';data=json.loads(evidence.read_text());validate_draft_evidence(data)
    figures=out/'figures';manifest=json.loads((figures/'figure_manifest.json').read_text())
    if manifest['evidence_sha256']!=hashlib.sha256(evidence.read_bytes()).hexdigest():raise ValueError('Notebook figures do not match evidence freeze')
    if manifest.get('analysis_script_sha256')!=hashlib.sha256((ROOT/'scripts/paper_analysis.py').read_bytes()).hexdigest():raise ValueError('Rerun notebook after analysis code changes')
    for name,want in manifest['files'].items():
        if Path(name).name!=name or hashlib.sha256((figures/name).read_bytes()).hexdigest()!=want:raise ValueError('Figure integrity failure')
    for name in ['paper.tex','sources.bib']:shutil.copyfile(ROOT/'report'/name,out/name)
    (out/'generated_results.tex').write_text(generated_table(data))
    fonts=out/'fonts';fonts.mkdir(exist_ok=True)
    if not (fonts/'OldStandard-Bold.ttf').exists():
        import httpx
        with httpx.Client(timeout=30,follow_redirects=True) as client:
            for name in ['OldStandard-Bold.ttf','OFL.txt']:
                response=client.get('https://raw.githubusercontent.com/google/fonts/main/ofl/oldstandardtt/'+name);response.raise_for_status();(fonts/name).write_bytes(response.content)
    with (out/'compile.private.log').open('w') as log:
        subprocess.run([str(args.compiler.resolve()),'--untrusted','--keep-logs','--outdir',str(out),str(out/'paper.tex')],cwd=out,stdout=log,stderr=log,check=True,timeout=600)
    quality=inspect_pdf(out/'paper.pdf',out/'paper.log',out/'paper.tex')
    quality.update(evidence_sha256=manifest['evidence_sha256'],pdf_sha256=hashlib.sha256((out/'paper.pdf').read_bytes()).hexdigest(),
                   latex_source_sha256=hashlib.sha256((out/'paper.tex').read_bytes()).hexdigest(),figure_manifest_sha256=hashlib.sha256((figures/'figure_manifest.json').read_bytes()).hexdigest())
    from importlib.metadata import distributions
    quality['installed_versions']={d.metadata['Name']:d.version for d in distributions() if d.metadata.get('Name')}
    quality['notebook_source_sha256']=hashlib.sha256((ROOT/'notebooks/paper_figures.ipynb').read_bytes()).hexdigest()
    quality['analysis_script_sha256']=hashlib.sha256((ROOT/'scripts/paper_analysis.py').read_bytes()).hexdigest()
    quality['bibliography_sha256']=hashlib.sha256((ROOT/'report/sources.bib').read_bytes()).hexdigest()
    quality['font_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in fonts.glob('*.ttf')}
    (out/'build_manifest.json').write_text(json.dumps(quality,indent=2)+'\n')
    print('LaTeX PDF built:',quality['main_text_pages'],'main-text pages,',quality['total_pages'],'total pages,',quality['abstract_words'],'abstract words. Human review remains required.')


if __name__=='__main__':main()
