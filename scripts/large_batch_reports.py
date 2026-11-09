"""Offline periodic reports from completed registered benchmark batches; no inference."""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
import fcntl
import hashlib
import json
from pathlib import Path
import time

from contagion.config import digest
from run_campaign import atomic
from run_pilot import ROOT

DEPENDENCIES=('large_batch_reports.py','large_benchmark_analysis.py','large_study_acceptance.py',
              'large_primary_queue.py','large_benchmark_runner.py','long_benchmark_materials.py',
              'analyze_primary_long.py','analyze_confirmatory.py','large_benchmark_monitor.py',
              'analyze_prior_primary_checkpoint.py','primary_allocation_release.py')


def hashes():return {name:hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest() for name in DEPENDENCIES}


def utc():return datetime.now(timezone.utc).isoformat()


def receipt_cutoff(plan,receipt,source):
    """Bind each checkpoint to its own complete batch, excluding later arrivals."""
    expected={f'job-{i:03}' for i,j in enumerate(plan['jobs']) if j['batch']==receipt['batch']}
    if (receipt.get('plan_hash')!=plan['plan_hash'] or receipt.get('operational_gate_passed') is not True
        or set(receipt.get('seals',{}))!=expected or receipt.get('runs')!=len(expected)):
        raise ValueError('Invalid complete batch receipt')
    ended=[]
    for name,want in receipt['seals'].items():
        matches=[p for p in (Path(source)/name).glob('*/checksum.sha256') if hashlib.sha256(p.read_bytes()).hexdigest()==want]
        if len(matches)!=1:raise ValueError('Batch receipt seal does not identify one attempt')
        manifest=json.loads((matches[0].parent/'manifest.json').read_text())
        if manifest['status']!='completed':raise ValueError('Batch receipt includes incomplete attempt')
        value=datetime.fromisoformat(manifest['ended_utc'])
        if value.tzinfo is None:raise ValueError('Batch end time must include timezone')
        ended.append(value)
    if not ended:raise ValueError('Empty evaluation batch')
    return max(ended).isoformat()


def plots(data,output):
    """Actual counts, operational flags and runtime; never inferred semantic quality."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=[r for r in data['rows'] if r['phase']=='evaluation']
    if not rows:raise ValueError('No completed evaluation rows to plot')
    output=Path(output);output.mkdir(parents=True,exist_ok=False);files=[]
    def save(fig,name):
        fig.tight_layout()
        for suffix in ('png','pdf','svg'):
            path=output/(name+'.'+suffix);fig.savefig(path,dpi=180,bbox_inches='tight');files.append(path.name)
        plt.close(fig)
    grouped=defaultdict(list)
    for row in rows:grouped[(row['dataset'],row['task_kind'],row['defense'],row['intervention'])].append(row)
    keys=sorted(grouped);labels=[f"{k[0].split('/')[-1]} / {k[1]}\n{k[2]} / {k[3]}" for k in keys]
    fig,ax=plt.subplots(figsize=(10,max(3,.65*len(keys))))
    bars=ax.barh(range(len(keys)),[len(grouped[k]) for k in keys],color='#3578b5')
    ax.bar_label(bars,padding=4);ax.set(yticks=range(len(keys)),yticklabels=labels,xlabel='Completed run count; shared cases/arms are dependent',title='Completed benchmark coverage by source and condition')
    ax.set_xlim(0,max(map(lambda k:len(grouped[k]),keys))*1.2+1);ax.invert_yaxis();save(fig,'coverage')
    metrics=('any_round_downstream_violation','final_downstream_any_violation');values=[];annotations=[]
    for key in keys:
        cell=[];texts=[]
        for metric in metrics:
            known=[r[metric] for r in grouped[key] if type(r.get(metric)) is bool];positive=sum(known)
            cell.append(positive/len(known) if known else float('nan'));texts.append(f'{positive}/{len(known)}' if known else 'undefined')
        values.append(cell);annotations.append(texts)
    fig,ax=plt.subplots(figsize=(10,max(3,.65*len(keys))))
    image=ax.imshow(values,vmin=0,vmax=1,cmap='YlOrRd',aspect='auto')
    for y,line in enumerate(annotations):
        for x,text in enumerate(line):ax.text(x,y,text,ha='center',va='center',color='white' if values[y][x]>.55 else '#202020')
    ax.set(yticks=range(len(keys)),yticklabels=labels,xticks=[0,1],xticklabels=['Any-round downstream flag','Final downstream flag'],title='Operational boundary signals, not adjudicated misalignment')
    fig.colorbar(image,ax=ax,label='Flagged runs / known runs');save(fig,'boundary_signals')
    cases=sorted({r['case'] for r in rows});index={case:i for i,case in enumerate(cases)}
    fig,ax=plt.subplots(figsize=(10,4));colors={'none':'#298a61','benign_override':'#c56b28'}
    for defense in ('plain','source_attribution'):
        for condition in ('none','benign_override'):
            selected=[r for r in rows if r['defense']==defense and r['intervention']==condition]
            if not selected:continue
            offset=(-.15 if defense=='plain' else .15)+(-.05 if condition=='none' else .05)
            ax.scatter([index[r['case']]+offset for r in selected],[r['runtime_seconds'] for r in selected],
                       color=colors[condition],marker='o' if defense=='plain' else '^',label=defense+' / '+condition,alpha=.75)
    ax.set_yscale('symlog',linthresh=1);ax.set(xlabel='Sorted case index; fixed arm offsets for overlap visibility',ylabel='Recorded wall seconds (symmetric log)',title='Run times include controller and cooling overhead')
    ax.legend(fontsize=8);save(fig,'runtime')
    manifest={'schema_version':'large-batch-figures-1.0','analysis_sha256':digest(data),
              'scope':data['analysis_scope'],'semantic_quality':'not_validated',
              'files':{name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in files}}
    atomic(output/'figures.json',manifest);return manifest


def prepare(root,queue,max_hours=96):
    from large_primary_queue import validate_plan
    root=Path(root);queue=Path(queue).resolve();plan=validate_plan(queue)
    if (ROOT/'results').resolve() not in root.resolve().parents or not 1<=max_hours<=120:raise ValueError('Bound private observer output/time')
    frozen={'schema_version':'large-report-watch-1.0','queue':str(queue),'queue_plan_hash':plan['plan_hash'],
            'dependencies':hashes(),'max_seconds':max_hours*3600,'created_utc':utc(),'model_calls':0}
    frozen['plan_hash']=digest(frozen);root.mkdir(parents=True,exist_ok=False);atomic(root/'report-plan.private.json',frozen);return frozen


def run(root):
    from large_primary_queue import validate_plan
    from large_benchmark_analysis import analyze
    from large_benchmark_monitor import evaluate as monitor
    from analyze_prior_primary_checkpoint import analyze as prior_analysis
    from primary_allocation_release import validate_receipt
    root=Path(root);plan=json.loads((root/'report-plan.private.json').read_text())
    if digest({k:v for k,v in plan.items() if k!='plan_hash'})!=plan['plan_hash'] or hashes()!=plan['dependencies']:raise ValueError('Registered observer changed')
    state_path=root/'report-state.private.json'
    if state_path.exists():raise ValueError('No implicit overwrite of a prior observer run')
    state={'status':'waiting','processed_batches':[],'prior_checkpoint_reported':False,'model_calls':0};began=time.monotonic()
    def save(**fields):state.update(fields,updated_utc=utc());atomic(state_path,state)
    with (root/'observer.lock').open('a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB);save()
        try:
            while True:
                if (root/'STOP').exists():raise RuntimeError('Operator stop')
                if time.monotonic()-began>=plan['max_seconds']:raise RuntimeError('Observer time budget')
                if hashes()!=plan['dependencies']:raise ValueError('Frozen report helper changed')
                queue=Path(plan['queue']);registered=validate_plan(queue)
                if registered['plan_hash']!=plan['queue_plan_hash']:raise ValueError('Queue changed')
                if registered.get('release_receipt') and Path(registered['release_receipt']).is_file() and not state['prior_checkpoint_reported']:
                    validate_receipt(registered['release_queue'],registered['release_receipt'])
                    previous=prior_analysis(registered['release_queue'],cutoff=utc())
                    out=root/'prior-primary-checkpoint';out.mkdir(exist_ok=False);atomic(out/'analysis.private.json',previous)
                    if previous['evaluation_runs']:plots(previous,out/'figures')
                    save(prior_checkpoint_reported=True,prior_completed_blocks=previous['case_seed_blocks'])
                available=sorted(int(p.stem.split('-')[1]) for p in queue.glob('batch-*.json') if p.stem.split('-')[1].isdigit() and int(p.stem.split('-')[1])>0)
                for batch in available:
                    if batch in state['processed_batches']:continue
                    receipt=json.loads((queue/f'batch-{batch:03}.json').read_text())
                    cutoff=receipt_cutoff(registered,receipt,ROOT/'results/repository-runs'/queue.name)
                    data=analyze(queue,completed_batches=True,cutoff=cutoff)
                    out=root/f'batch-{batch:03}';out.mkdir(exist_ok=False)
                    atomic(out/'analysis.private.json',data);plots(data,out/'figures')
                    monitor(queue,out/'monitor',completed_batches=True,cutoff=cutoff)
                    state['processed_batches'].append(batch);save(status='watching',latest_analysis=str((out/'analysis.private.json').relative_to(root)),evaluation_runs=data['evaluation_runs'])
                path=queue/'primary-large-state.json';current=json.loads(path.read_text()) if path.exists() else {'status':'waiting'}
                if current['status']=='completed':
                    full=analyze(queue);atomic(root/'full-analysis.private.json',full);save(status='completed');return state
                if current['status'] in {'stopped','failed','budget_exhausted'}:save(status='stopped',reason='model_queue_requires_operator_review');return state
                time.sleep(30)
        except BaseException as exc:save(status='stopped',error_type=type(exc).__name__);raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--root',type=Path,required=True);p.add_argument('--queue',type=Path,required=True);p.add_argument('--max-hours',type=int,default=96)
    r=sub.add_parser('run');r.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='prepare':prepare(args.root,args.queue,args.max_hours);print('Registered offline batch reports; zero inference calls.')
    else:run(args.root)
