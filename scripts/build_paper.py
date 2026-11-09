"""Execute the figure-review notebook and compile the checked LaTeX research PDF."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
CLASSIC_MAIN = r'\setmainfont{lmroman10-regular.otf}[BoldFont=lmroman10-bold.otf,ItalicFont=lmroman10-italic.otf,BoldItalicFont=lmroman10-bolditalic.otf]'
CLASSIC_TITLE = r'\newfontfamily\titlefont{lmroman10-bold.otf}'
TEMPLATE_MAIN = r'\setmainfont{Arial}'
TEMPLATE_TITLE = r'\newfontfamily\titlefont{OldStandard-Bold.ttf}[Path=fonts/]'


def render_typeface(source, typeface='classic'):
    """Only the two font declarations differ between compiled variants."""
    if typeface not in {'classic', 'template'}: raise ValueError('Unknown paper typeface variant')
    for marker in (CLASSIC_MAIN, CLASSIC_TITLE):
        if source.count(marker) != 1: raise ValueError('Expected canonical classic font declaration once')
    if typeface == 'classic': return source
    return source.replace(CLASSIC_MAIN, TEMPLATE_MAIN).replace(CLASSIC_TITLE, TEMPLATE_TITLE)


def pdf_font_names(path):
    from pypdf import PdfReader
    return sorted({str(font.get_object().get('/BaseFont', '')) for page in PdfReader(path).pages
                   for font in page.get('/Resources', {}).get('/Font', {}).values()})


def validate_pdf_typeface(names, typeface):
    if typeface not in {'classic', 'template'}: raise ValueError('Unknown paper typeface variant')
    required = ('LMRoman10-Regular', 'LMRoman10-Bold') if typeface == 'classic' else ('Arial', 'OldStandard')
    if not all(any(want in name for name in names) for want in required):
        raise ValueError('Embedded PDF fonts do not match the declared typeface')
    return names


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


def validate_rq3_followup(data,narrative=None):
    """Validate the separate numeric freeze offline; original raw logs are not required."""
    import itertools
    from collections import Counter
    if data.get('schema_version')!='rq3-followup-evidence-1.0' or data.get('protocol')!='4.0-confirmatory':
        raise ValueError('Unknown separate RQ3 freeze')
    rows=data.get('rows')
    if not isinstance(rows,list) or len(rows)!=64:raise ValueError('Separate RQ3 needs64 unique completed rows')
    required={'run_id','backend','model','model_digest','worker','freeze_hash','family','case','seed','topology',
              'condition','executor','context','phase','status','completed_calls','http_attempts',
              'attempted_forbidden','actual_state_violation','refusal_rate','task_success_rate'}
    ids=set();matrix=set();identities=set()
    for row in rows:
        if not isinstance(row,dict) or not required<=row.keys():raise ValueError('Incomplete separate RQ3 row')
        name=row['run_id']
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',name) or name in ids:
            raise ValueError('Duplicate or invalid separate RQ3 run ID')
        ids.add(name)
        if any(row[k]!=v for k,v in {'backend':'ollama','worker':'primary','family':'record','phase':'confirmatory','status':'completed'}.items()):
            raise ValueError('Separate RQ3 contains non-confirmatory or non-live evidence')
        if type(row['case']) is not int or type(row['seed']) is not int:raise ValueError('Invalid case or seed')
        if type(row['completed_calls']) is not int or row['completed_calls']!=5 or type(row['http_attempts']) is not int or row['http_attempts']!=5:
            raise ValueError('Separate RQ3 requires five calls per run')
        if any(type(row[k]) is not bool for k in ['attempted_forbidden','actual_state_violation']):raise ValueError('Invalid RQ3 behavior flag')
        for key in ['refusal_rate','task_success_rate']:
            if type(row[key]) not in {int,float} or not math.isfinite(row[key]) or not 0<=row[key]<=1:raise ValueError('Invalid RQ3 rate')
        if not isinstance(row['model'],str) or not row['model']:raise ValueError('Missing RQ3 model')
        for key in ['model_digest','freeze_hash']:
            if not isinstance(row[key],str) or not re.fullmatch(r'[a-f0-9]{64}',row[key]):raise ValueError('Invalid RQ3 provenance digest')
        matrix.add((row['case'],row['seed'],row['topology'],row['condition'],row['executor'],row['context']))
        identities.add((row['model'],row['model_digest'],row['freeze_hash'],row['worker']))
    expected=set(itertools.product(range(4),[13001],['single','complete'],['none','benign_override'],
                                   ['deny','permissive_simulator'],['matched_reset','natural_history']))
    if matrix!=expected or len(identities)!=1:raise ValueError('Separate RQ3 matrix or model cohort mismatch')
    seals=data.get('source_seal_sha256')
    if not isinstance(seals,dict) or set(seals)!=ids or any(not isinstance(v,str) or not re.fullmatch(r'[a-f0-9]{64}',v) for v in seals.values()):
        raise ValueError('Separate RQ3 source seal coverage mismatch')
    for key in ['analysis_sha256','analysis_script_sha256','source_hash']:
        if not isinstance(data.get(key),str) or not re.fullmatch(r'[a-f0-9]{64}',data[key]):raise ValueError('Invalid separate RQ3 provenance')
    derived={'complete_runs':len(rows),'responses':sum(r['completed_calls'] for r in rows),'case_clusters':len({r['case'] for r in rows}),
             'attempting_runs':sum(r['attempted_forbidden'] for r in rows),'state_violating_runs':sum(r['actual_state_violation'] for r in rows),
             'runs_with_refusal':sum(r['refusal_rate']>0 for r in rows)}
    if any(type(data.get(k)) is not int or data[k]!=v for k,v in derived.items()):raise ValueError('Separate RQ3 header counts disagree with rows')
    mean=sum(r['task_success_rate'] for r in rows)/len(rows)
    if type(data.get('mean_task_success')) not in {int,float} or not math.isclose(data['mean_task_success'],mean,rel_tol=0,abs_tol=1e-12):
        raise ValueError('Separate RQ3 task-success header disagrees with rows')
    if data.get('seeds')!=[13001] or data.get('context_counts')!=dict(Counter(r['context'] for r in rows)):
        raise ValueError('Separate RQ3 design header mismatch')
    if any(derived[k] for k in ['attempting_runs','state_violating_runs','runs_with_refusal']) or mean!=1:
        raise ValueError('Revise separate RQ3 null narrative before rebuilding')
    if narrative is not None:
        marker=r'\subsection{Separately frozen responsibility follow-up}'
        if marker not in narrative:raise ValueError('Separate RQ3 narrative missing')
        section=narrative.split(marker,1)[1].split(r'\section{',1)[0]
        count=re.search(r'adds\s+(\d+)\s+held-out\s+record\s+runs\s*\((\d+)\s+responses\)',section)
        null=re.search(r'All\s+(\d+)\s+runs\s+completed\s+with\s+exact\s+final\s+task\s+success\s+([0-9.]+)\s+and\s+zero\s+protected-update\s+attempts,\s+simulator\s+state\s+violations\s+or\s+scored\s+refusals',section)
        if not count or tuple(map(int,count.groups()))!=(derived['complete_runs'],derived['responses']) or not null or int(null[1])!=len(rows) or float(null[2])!=mean:
            raise ValueError('Separate RQ3 narrative counts disagree with freeze')
    return {**derived,'mean_task_success':mean}


def generated_table(data):
    from collections import defaultdict
    rows=defaultdict(list)
    for row in data['runs']:
        if row['status']=='completed':rows[(row['family'],row['condition'])].append(row)
    text=[r'\begin{table}[htbp]\centering\small',r'\caption{Compact held-out counts from the strict scorer: any-round and final violations are different endpoints. Mean task success uses exact final artifacts, including canonical path format. Each row has one task case and two seeds across three graphs.}',r'\begin{tabular}{llrrrr}\toprule',r'Task & Condition & Runs & Any-round & Final & Task success\\\midrule']
    for (family,condition),items in sorted(rows.items()):
        text.append(f"{family.title()} & {'Control' if condition=='none' else 'Injected'} & {len(items)} & {sum(r['any_round_violation'] for r in items)} & {sum(r['final_any_violation'] for r in items)} & {sum(r['task_success'] for r in items)/len(items):.3f}"+r'\\')
    return '\n'.join([*text,r'\bottomrule\end{tabular}\label{tab:outcomes}\end{table}'])+'\n'


def validate_secondary_figure_inputs(manifest,root=ROOT):
    inputs=manifest.get('secondary_inputs_sha256',{})
    expected={'report/data/patch_pointer_audit.json'}
    if set(inputs)!=expected:raise ValueError('Rerun figure notebook with the declared secondary evidence input')
    for name,want in inputs.items():
        if hashlib.sha256((Path(root)/name).read_bytes()).hexdigest()!=want:
            raise ValueError('Secondary figure input changed after notebook execution')


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
    parser.add_argument('--typeface',choices=['classic','template'],default='classic')
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
    followup=ROOT/'report/data/rq3_followup.json'
    validate_rq3_followup(json.loads(followup.read_text()),(ROOT/'report/paper.tex').read_text())
    figures=out/'figures';manifest=json.loads((figures/'figure_manifest.json').read_text())
    if manifest['evidence_sha256']!=hashlib.sha256(evidence.read_bytes()).hexdigest():raise ValueError('Notebook figures do not match evidence freeze')
    if manifest.get('analysis_script_sha256')!=hashlib.sha256((ROOT/'scripts/paper_analysis.py').read_bytes()).hexdigest():raise ValueError('Rerun notebook after analysis code changes')
    validate_secondary_figure_inputs(manifest)
    for name,want in manifest['files'].items():
        if Path(name).name!=name or hashlib.sha256((figures/name).read_bytes()).hexdigest()!=want:raise ValueError('Figure integrity failure')
    authoring_source=(ROOT/'report/paper.tex').read_text()
    (out/'paper.tex').write_text(render_typeface(authoring_source,args.typeface))
    shutil.copyfile(ROOT/'report/sources.bib',out/'sources.bib')
    (out/'generated_results.tex').write_text(generated_table(data))
    from paper_supplement import render
    supplement,supplement_hashes=render(ROOT)
    (out/'generated_supplement.tex').write_text(supplement)
    fonts=out/'fonts';fonts.mkdir(exist_ok=True)
    needs_template_font=args.typeface=='template'
    cached_fonts=ROOT/'results/paper-template-bf217d7/fonts'
    if needs_template_font:
        for name in ['OldStandard-Bold.ttf','OFL.txt']:
            if not (fonts/name).exists() and (cached_fonts/name).is_file():
                shutil.copyfile(cached_fonts/name,fonts/name)
    if needs_template_font and not (fonts/'OldStandard-Bold.ttf').exists():
        import httpx
        with httpx.Client(timeout=30,follow_redirects=True) as client:
            for name in ['OldStandard-Bold.ttf','OFL.txt']:
                response=client.get('https://raw.githubusercontent.com/google/fonts/main/ofl/oldstandardtt/'+name);response.raise_for_status();(fonts/name).write_bytes(response.content)
    with (out/'compile.private.log').open('w') as log:
        subprocess.run([str(args.compiler.resolve()),'--untrusted','--keep-logs','--outdir',str(out),str(out/'paper.tex')],cwd=out,stdout=log,stderr=log,check=True,timeout=600)
    quality=inspect_pdf(out/'paper.pdf',out/'paper.log',out/'paper.tex')
    quality.update(evidence_sha256=manifest['evidence_sha256'],pdf_sha256=hashlib.sha256((out/'paper.pdf').read_bytes()).hexdigest(),
                   latex_source_sha256=hashlib.sha256((out/'paper.tex').read_bytes()).hexdigest(),figure_manifest_sha256=hashlib.sha256((figures/'figure_manifest.json').read_bytes()).hexdigest())
    quality['schema_version']='paper-build-2.0'
    quality['authoring_source_sha256']=hashlib.sha256((ROOT/'report/paper.tex').read_bytes()).hexdigest()
    quality['compiledlatex_source_sha256']=quality['latex_source_sha256']
    quality['typeface_variant']=args.typeface
    from importlib.metadata import distributions
    quality['installed_versions']={d.metadata['Name']:d.version for d in distributions() if d.metadata.get('Name')}
    quality['notebook_source_sha256']=hashlib.sha256((ROOT/'notebooks/paper_figures.ipynb').read_bytes()).hexdigest()
    quality['analysis_script_sha256']=hashlib.sha256((ROOT/'scripts/paper_analysis.py').read_bytes()).hexdigest()
    quality['bibliography_sha256']=hashlib.sha256((ROOT/'report/sources.bib').read_bytes()).hexdigest()
    quality['rq3_followup_sha256']=hashlib.sha256(followup.read_bytes()).hexdigest()
    quality['build_script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    quality.update(supplement_hashes)
    quality['font_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in fonts.glob('*.ttf')} if needs_template_font else {}
    quality['pdf_font_names']=validate_pdf_typeface(pdf_font_names(out/'paper.pdf'),args.typeface)
    quality['typeface']='Official template Arial/Old Standard' if needs_template_font else 'Latin Modern Roman; author-requested template typeface override'
    (out/'build_manifest.json').write_text(json.dumps(quality,indent=2)+'\n')
    print('LaTeX PDF built:',quality['main_text_pages'],'main-text pages,',quality['total_pages'],'total pages,',quality['abstract_words'],'abstract words. Human review remains required.')


if __name__=='__main__':main()
