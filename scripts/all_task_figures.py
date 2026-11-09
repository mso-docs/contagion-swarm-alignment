"""Offline inventory visuals for every published task; behavioral cohorts stay separate."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def default_data_root():
    # A submission freeze is authoritative even if an old live cache remains.
    if (ROOT/'dashboard/data/submission-freeze.json').is_file():
        return ROOT/'dashboard/data'
    return ROOT/('results/dashboard-live/data' if (ROOT/'results/dashboard-live/data/research.json').exists() else 'dashboard/data')


def inventory(root=None):
    root=Path(root) if root is not None else default_data_root()
    freeze=root/'submission-freeze.json'
    if freeze.exists():
        from freeze_dashboard import validate
        validate(freeze)
    rows=[];hashes={}
    for filename,kind in [('results.json','legacy'),('research.json','study'),('repositories.json','repository'),('followups.json','confirmatory')]:
        path=root/filename
        if not path.exists():continue
        blob=path.read_bytes();data=json.loads(blob);hashes[filename]=hashlib.sha256(blob).hexdigest()
        sources=[(kind,data.get('studies' if kind=='study' else 'runs',[]))]
        if filename=='followups.json':
            sources.extend((name,data.get(name,[])) for name in ['multidomain','diversity'])
        for source,values in sources:
            for r in values:
                rows.append({'id':source+':'+r['id'],'model':r['model'],'backend':r['backend'],
                    'protocol':r.get('protocol_version') if source=='legacy' else r['protocol'],
                    'task':r.get('domain',r.get('task_family','catalog')),
                    'status':r['status'],'calls':r.get('completed_calls') if source=='legacy' else r['calls'],
                    'runtime':r.get('duration_seconds') if source=='legacy' else r.get('runtime_seconds',r.get('runtime')),
                    'rounds':r.get('rounds'),'source':source,'phase':r.get('phase',r.get('split')),
                    'condition':r.get('arm',r.get('intervention')),'topology':r.get('topology'),
                    'agent_count':r.get('agent_count',len(r.get('agents',[])) or None),
                    'memory_policy':r.get('memory_policy'),'context_selection':r.get('context_selection')})
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('Duplicate inventory rows')
    return rows,hashes


def coverage_counts(rows):
    """Include mock-only families as explicit zero live coverage, never missing cells."""
    tasks=sorted({r['task'] for r in rows})
    return {task:{'live':sum(r['task']==task and r['backend']!='mock' for r in rows),
                  'mock':sum(r['task']==task and r['backend']=='mock' for r in rows)} for task in tasks}


def generate(output, data_root=None):
    import os
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import pandas as pd
    import seaborn as sns
    rows,hashes=inventory(data_root);frame=pd.DataFrame(rows);live=frame[frame.backend.ne('mock')].copy()
    coverage=coverage_counts(rows);tasks=list(coverage)
    if live.empty:raise ValueError('No live data for inventory')
    out=Path(output);out.mkdir(parents=True,exist_ok=True);sns.set_theme(style='whitegrid',context='paper')
    figures=[]
    def save(fig,name):
        fig.tight_layout()
        for ext in ['png','svg','pdf']:
            path=out/(name+'.'+ext);fig.savefig(path,dpi=180,bbox_inches='tight');figures.append(path.name)
        plt.close(fig)
    counts=live.groupby(['model','task'],observed=True).size().unstack(fill_value=0).reindex(columns=tasks,fill_value=0)
    fig,ax=plt.subplots(figsize=(12,4.8));sns.heatmap(counts,annot=True,fmt='d',cmap='Blues',linewidths=2,ax=ax,cbar_kws={'label':'Recorded attempts'})
    ax.set_xticklabels([task.replace('_','\n',1)+('\n(mock only; 0 live)' if not coverage[task]['live'] else '') for task in tasks],rotation=30,ha='right',fontsize=9)
    ax.tick_params(axis='y',rotation=0,labelsize=9)
    ax.set(title='Live model coverage across all recorded task families',xlabel='Task family · zeros show no live evidence',ylabel='Model tag');save(fig,'all_task_coverage')
    fig,ax=plt.subplots(figsize=(9,3.7));status=live.assign(completed=live.status.eq('completed')).groupby(['task','completed'],observed=True).size().unstack(fill_value=0).reindex(index=tasks,columns=[True,False],fill_value=0)
    status.columns=['Completed','Failed / exhausted'];status.plot.barh(stacked=True,color=['#3182bd','#dc8f39'],ax=ax)
    for container in ax.containers:ax.bar_label(container,labels=[str(int(v)) if v>=8 else '' for v in container.datavalues],label_type='center',fontsize=10,color='white')
    for i,(_,row) in enumerate(status.iterrows()):
        total=int(row.sum())
        if total<8:
            label='0 live · mock only' if not total else f"{int(row['Completed'])} complete / {int(row['Failed / exhausted'])} incomplete"
            ax.text(total+1,i,label,va='center',fontsize=8,color='#555555')
    ax.set_xlim(0,max(1,status.sum(axis=1).max())*1.08)
    ax.set(title='Completion coverage; incomplete attempts remain visible',ylabel='Task family',xlabel='Attempt count');ax.legend(title='Status',frameon=False);save(fig,'all_task_completion')
    fig,ax=plt.subplots(figsize=(9,4.4));sns.scatterplot(data=live,x='calls',y='runtime',hue='model',style='task',alpha=.65,ax=ax)
    ax.set_xscale('symlog',linthresh=10);ax.set_yscale('symlog',linthresh=10)
    ax.set(title='Every live attempt · symmetric-log axes reveal short and long runs',xlabel='Returned responses',ylabel='Wall time (seconds; includes pauses)');ax.legend(bbox_to_anchor=(1.02,1),loc='upper left',frameon=False,fontsize=8);save(fig,'all_task_runtime')
    frame.to_csv(out/'inventory.csv',index=False)
    manifest={'source_sha256':hashes,'live_attempts':len(live),'mock_attempts':int(frame.backend.eq('mock').sum()),
        'live_model_tags':int(live.model.nunique()),'live_task_families':int(live.task.nunique()),'all_task_families':len(tasks),'task_coverage':coverage,'files':figures,
        'limitations':['Counts are published index rows, not deduplicated independent trajectories; consult final_inventory.json for seal-based reconciliation.','Inventory counts do not pool behavioral scores.','Models/protocols/tasks differ; this is not a controlled model ranking.',
            'Unsealed running attempts are not published until validated.','Runtime includes controller, setup and thermal effects.']}
    (out/'inventory_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();result=generate(args.out);print('Live inventory:',result['live_attempts'],'attempts,',result['live_model_tags'],'models,',result['live_task_families'],'task families')
