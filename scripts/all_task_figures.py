"""Offline inventory visuals for every published task; behavioral cohorts stay separate."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def inventory(root=None):
    root=Path(root) if root is not None else ROOT/('results/dashboard-live/data' if (ROOT/'results/dashboard-live/data/research.json').exists() else 'dashboard/data')
    rows=[];hashes={}
    for filename,kind in [('results.json','legacy'),('research.json','study'),('repositories.json','repository')]:
        path=Path(root)/filename
        if not path.exists():continue
        blob=path.read_bytes();data=json.loads(blob);hashes[filename]=hashlib.sha256(blob).hexdigest()
        for r in data.get('studies' if kind=='study' else 'runs',[]):
            rows.append({'id':kind+':'+r['id'],'model':r['model'],'backend':r['backend'],
                'protocol':r['protocol_version'] if kind=='legacy' else r['protocol'],
                'task':'legacy_summary' if kind=='legacy' else r['task_family'],
                'status':r['status'],'calls':r['completed_calls'] if kind=='legacy' else r['calls'],
                'runtime':r['duration_seconds'] if kind=='legacy' else r['runtime'],
                'rounds':r['rounds'],'source':kind})
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('Duplicate inventory rows')
    return rows,hashes


def generate(output):
    import os
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import os
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    import matplotlib.pyplot as plt
    import pandas as pd
    import seaborn as sns
    rows,hashes=inventory();frame=pd.DataFrame(rows);live=frame[frame.backend.ne('mock')].copy()
    if live.empty:raise ValueError('No live data for inventory')
    out=Path(output);out.mkdir(parents=True,exist_ok=True);sns.set_theme(style='whitegrid',context='paper')
    figures=[]
    def save(fig,name):
        fig.tight_layout()
        for ext in ['png','svg','pdf']:
            path=out/(name+'.'+ext);fig.savefig(path,dpi=180,bbox_inches='tight');figures.append(path.name)
        plt.close(fig)
    counts=live.groupby(['model','task'],observed=True).size().unstack(fill_value=0)
    fig,ax=plt.subplots(figsize=(10,3.8));sns.heatmap(counts,annot=True,fmt='d',cmap='Blues',linewidths=2,ax=ax,cbar_kws={'label':'Recorded attempts'})
    ax.set(title='Live model coverage across all recorded task families',xlabel='Task family',ylabel='Model tag');save(fig,'all_task_coverage')
    fig,ax=plt.subplots(figsize=(9,3.7));status=live.assign(completed=live.status.eq('completed')).groupby(['task','completed'],observed=True).size().unstack(fill_value=0).reindex(columns=[True,False],fill_value=0)
    status.columns=['Completed','Failed / exhausted'];status.plot.bar(stacked=True,color=['#3182bd','#dc8f39'],ax=ax,rot=20)
    ax.set(title='Completion coverage; incomplete attempts remain visible',xlabel='Task family',ylabel='Attempt count');ax.legend(title='Status',frameon=False);save(fig,'all_task_completion')
    fig,ax=plt.subplots(figsize=(9,4.4));sns.scatterplot(data=live,x='calls',y='runtime',hue='model',style='task',alpha=.65,ax=ax)
    ax.set(title='Every live attempt: response count versus runtime',xlabel='Returned responses',ylabel='Wall time (seconds; includes pauses)');ax.legend(bbox_to_anchor=(1.02,1),loc='upper left',frameon=False,fontsize=8);save(fig,'all_task_runtime')
    frame.to_csv(out/'inventory.csv',index=False)
    manifest={'source_sha256':hashes,'live_attempts':len(live),'mock_attempts':int(frame.backend.eq('mock').sum()),
        'live_model_tags':int(live.model.nunique()),'live_task_families':int(live.task.nunique()),'files':figures,
        'limitations':['Inventory counts do not pool behavioral scores.','Models/protocols/tasks differ; this is not a controlled model ranking.',
            'Unsealed running attempts are not published until validated.','Runtime includes controller, setup and thermal effects.']}
    (out/'inventory_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();result=generate(args.out);print('Live inventory:',result['live_attempts'],'attempts,',result['live_model_tags'],'models,',result['live_task_families'],'task families')
