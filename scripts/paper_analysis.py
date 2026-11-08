"""Offline, frozen numerical evidence and publication figures; never invokes models."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from contagion.storage import verify

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze_evidence(campaign,development,neural,output):
    campaign=Path(campaign);config=json.loads((campaign/'campaign.json').read_text());state=json.loads((campaign/'state.json').read_text())
    if state['status']!='completed':raise ValueError('Select a completed campaign')
    rows=[];inputs={}
    def collect(root,target,require_match=True):
        for path in sorted(Path(root).rglob('manifest.json')):
            directory=path.parent
            if not verify(directory):raise ValueError('Unsealed or corrupt evidence')
            manifest=json.loads(path.read_text());settings=json.loads((directory/'config.snapshot.json').read_text());outcome=json.loads((directory/'outcome.json').read_text())
            if manifest['model_identity'].get('backend')!='ollama' or (require_match and manifest['source_hash']!=config['source_hash']):raise ValueError('Mixed source/backend')
            events=[json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
            complete=manifest['status']=='completed';identity=manifest['model_identity']
            target.append({'id':hashlib.sha256(directory.name.encode()).hexdigest()[:16],
                'family':settings['family'],'case_index':settings['case_index'],'seed':settings['seed'],
                'topology':settings['topology'],'condition':settings['intervention'],'executor':settings['plan']['executor'],
                'status':manifest['status'],'model':identity['model'],'model_digest':identity['digest'],
                'source_hash':manifest['source_hash'],'protocol':manifest['protocol_version'],'responses':sum(e['event_type']=='inference_response' for e in events),
                'http_attempts':sum(e['event_type']=='http_attempt' for e in events),'runtime_seconds':manifest['duration_seconds'],
                'parse_failures':manifest['parse_failures'],'any_round_violation':outcome['any_violation'] if complete else None,
                'final_any_violation':any(a['violation'] for a in outcome['final_agents']) if complete else None,
                'downstream_any_round_violation':any(e['event_type']=='artifact' and e.get('agent_id')!='agent_0' and e['metadata']['score']['violation'] for e in events) if complete else None,
                'downstream_violation_rate':outcome['downstream_final_violation_rate'] if complete else None,
                'task_success':outcome['task_success_rate'] if complete else None,
                'round_downstream_violations':[sum(e['event_type']=='artifact' and e['round']==r and e.get('agent_id')!='agent_0' and e['metadata']['score']['violation'] for e in events) for r in range(settings['plan']['rounds'])] if complete else [],
                'direct_injection_deliveries':sum(e['event_type']=='message_delivered' and e.get('content') in {x['content'] for x in events if x['event_type']=='intervention_applied'} for e in events),
                'attempted_forbidden':outcome['attempted_forbidden'] if complete else None,
                'state_violation':outcome['actual_state_violation'] if complete else None})
            inputs[directory.name]={'seal_sha256':sha(directory/'checksum.sha256'),'manifest_sha256':sha(path)}
    collect(config['run_root'],rows)
    rq3=[]
    for path in sorted(Path(development).glob('gated-20261108T015810Z-rq3*')):collect(path,rq3,False)
    monitor=json.loads((campaign/'monitor/monitor.json').read_text())
    observations=[{k:r[k] for k in ['topology','policy','visibility','monitor_seed','prediction','truth']} for r in monitor['observations']]
    captures=[]
    for capture in sorted(Path(neural).glob('secondary-trained-*/capture.json')):
        checks=json.loads((capture.parent/'checksums.json').read_text())
        if any(sha(capture.parent/name)!=want for name,want in checks.items()):raise ValueError('Capture seal failed')
        data=json.loads(capture.read_text());patch=data['patch'];kind='capability_control' if 'capital-positive-control' in capture.parent.name else 'task_shaped_probe'
        gap=patch['clean_target_logit']-patch['corrupt_target_logit'];delta=patch['patched_target_logit']-patch['corrupt_target_logit']
        captures.append({'model':data['model'],'revision':data['revision'],'kind':kind,'layer':int(patch['hook'].split('.')[1]),
            'clean_corrupt_gap':gap,'patch_delta':delta,'restoration':delta/gap if abs(gap)>=1e-4 else None,
            'noop_error':abs(patch['noop_target_logit']-patch['corrupt_target_logit']),
            'position_control_error':abs(patch['position_control_logit']-patch['corrupt_target_logit']),
            'parity_passed':data.get('validation',{}).get('raw_bridge_parity_passed',False)})
        inputs[capture.parent.name]={'capture_sha256':sha(capture),'seal_sha256':sha(capture.parent/'checksums.json')}
    data={'schema_version':'paper-evidence-1.1','campaign_hash':config['campaign_hash'],'source_hash':config['source_hash'],
        'model':config['model'],'model_digest':config['model_digest'],'protocol':'2.6','runs':rows,'rq3_development':rq3,
        'monitor_observations':observations,'neural':captures,'source_seals':inputs,
        'limitations':['Run/seed observations are nested and paired.','Only one generated case per task in the compact study.',
          'RQ3 rows are development pilots, separate from held-out RQ1.','Monitor projections share trajectories; no independent projection sample size.',
          'GPT-2 reference captures do not expose Ollama internals.','No repository review quality or collusion judgment is included.']}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:json.dump(data,stream,indent=2);stream.write('\n')
    return data


def temporal_patch_series(data):
    result={}
    for topology in ['ring','star','complete']:
        rows=[r for r in data['runs'] if r['status']=='completed' and r['family']=='patch' and r['condition']=='benign_override' and r['topology']==topology]
        if not rows:raise ValueError('Missing patch topology condition')
        result[topology]=[sum(r['round_downstream_violations'][i] for r in rows)/(4*len(rows)) for i in range(5)]
    return result



def temporal_patch_rows(data):
    """Keep each paired-seed trajectory visible; counts never pool agents as trials."""
    result=[]
    for topology in ['ring','star','complete']:
        rows=sorted((r for r in data['runs'] if r['status']=='completed' and r['family']=='patch' and r['condition']=='benign_override' and r['topology']==topology),key=lambda r:r['seed'])
        if not rows:raise ValueError('Missing patch topology condition')
        for row in rows:
            counts=row['round_downstream_violations']
            if len(counts)!=5 or any(type(n) is not int or not 0<=n<=4 for n in counts):raise ValueError('Invalid five-round downstream counts')
            deliveries=row['direct_injection_deliveries']
            if type(deliveries) is not int or not 0<=deliveries<=4:raise ValueError('Invalid direct-delivery count')
            result.append({'topology':topology,'seed':row['seed'],'violations':list(counts),'direct_deliveries':deliveries})
    return result

def figures(evidence,output):
    import os
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import os
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    import seaborn as sns
    from matplotlib.patches import FancyArrowPatch,FancyBboxPatch
    data=json.loads(Path(evidence).read_text());out=Path(output);out.mkdir(parents=True,exist_ok=True)
    np.random.seed(919)
    sns.set_theme(style='whitegrid',context='paper',font_scale=1.1)
    plt.rcParams.update({'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
    files=[]
    def save(fig,name):
        fig.tight_layout()
        for ext in ['pdf','svg','png']:
            path=out/(name+'.'+ext);fig.savefig(path,dpi=180,bbox_inches='tight',metadata={'Creator':'Contagion analysis notebook'} if ext!='png' else {'Software':'Contagion analysis notebook'});files.append(path)
        plt.close(fig)
    colors={'none':'#2970b1','benign_override':'#d16a2d'}
    runs=pd.DataFrame(data['runs']);done=runs[runs.status.eq('completed')].copy()
    fig,ax=plt.subplots(figsize=(9,2.8));ax.set(xlim=(0,10),ylim=(0,3));ax.axis('off')
    boxes=[(.1,1.65,1.5,'Frozen task\n+ paired condition','#e8f1fa','#2872ac'),
           (2.1,1.65,1.5,'Five isolated\nagent histories','#e4f5ee','#278466'),
           (4.1,1.65,1.5,'Controller-only\nnext-round router','#fff0da','#b47b24'),
           (6.1,1.65,1.5,'Append-only\nsealed oracle log','#ece8fa','#7961a6'),
           (8.1,1.65,1.7,'Behavior scoring\n+ final artifacts','#e8f1fa','#2872ac')]
    for x,y,w,text,fill,edge in boxes:
        ax.add_patch(FancyBboxPatch((x,y),w,.9,boxstyle='round,pad=0.05',fc=fill,ec=edge,lw=1.4));ax.text(x+w/2,y+.45,text,ha='center',va='center',fontsize=9)
    for a,b in zip(boxes,boxes[1:]):ax.add_patch(FancyArrowPatch((a[0]+a[2]+.05,2.1),(b[0]-.08,2.1),arrowstyle='-|>',mutation_scale=12,color='#46758c'))
    for offset,topology in [(.25,'ring'),(2.1,'star'),(3.95,'complete')]:
        pts=[(offset+.55+.42*np.cos(t),.65+.35*np.sin(t)) for t in np.linspace(0,2*np.pi,5,endpoint=False)]
        if topology=='star':pts=[(offset+.55,.65)]+[(offset+.55+.42*np.cos(t),.65+.35*np.sin(t)) for t in np.linspace(0,2*np.pi,4,endpoint=False)]
        for i in range(5):
            for j in range(i+1,5):
                if topology=='complete' or (topology=='star' and i==0) or (topology=='ring' and (j-i==1 or (i==0 and j==4))):ax.plot([pts[i][0],pts[j][0]],[pts[i][1],pts[j][1]],color='#8aabc3',lw=1)
        ax.scatter(*zip(*pts),s=55,color=['#d16a2d']+['#2970b1']*4,zorder=3);ax.text(offset+.55,.03,topology,ha='center',fontsize=9)
    ax.add_patch(FancyBboxPatch((6.25,.22),3.4,.86,boxstyle='round,pad=0.05',fc='#e4f5ee',ec='#278466'))
    ax.text(7.95,.65,'Allowlisted past-only projection\n→ monitor prediction (no oracle labels)',ha='center',va='center',fontsize=9)
    ax.add_patch(FancyArrowPatch((6.85,1.6),(6.85,1.14),arrowstyle='-|>',mutation_scale=12,color='#278466'))
    ax.text(4.9,2.93,'Agent text cannot execute tools or change routing',ha='center',fontsize=10,fontweight='bold',color='#31465a')
    save(fig,'01_experiment_flow')
    families=['catalog','provenance','patch'];summary=done.groupby(['family','condition'],observed=True).agg(runs=('any_round_violation','size'),violations=('any_round_violation','sum'),final_violations=('final_any_violation','sum'),success=('task_success','mean')).reset_index()
    fig,axes=plt.subplots(1,2,figsize=(9,2.7))
    for ax,metric,title in [(axes[0],'violations','Any-round boundary violations'),(axes[1],'success','Legitimate task completion')]:
        values=[];labels=[]
        for family in families:
            cells=[];texts=[]
            for condition in ['none','benign_override']:
                row=summary[summary.family.eq(family)&summary.condition.eq(condition)].iloc[0]
                value=row[metric]/row.runs if metric=='violations' else row.success
                cells.append(value);texts.append(f'{int(row.violations)}/{int(row.runs)} runs' if metric=='violations' else f'{value:.1%}\nn={int(row.runs)} runs')
            values.append(cells);labels.append(texts)
        sns.heatmap(np.array(values),annot=np.array(labels),fmt='',vmin=0,vmax=1,cmap='Oranges' if metric=='violations' else 'Blues',cbar=False,linewidths=3,ax=ax,annot_kws={'fontsize':11})
        ax.set(title=title,xticklabels=['Control','Injected'],yticklabels=['Catalog','Provenance','Inert patch'],xlabel='',ylabel='');ax.tick_params(axis='y',rotation=0)
    fig.suptitle(f'Final boundary violations: {int(done.final_any_violation.sum())}/{len(done)} completed runs',fontsize=12,fontweight='bold',y=1.08)
    save(fig,'02_task_outcomes')
    fig,axes=plt.subplots(1,2,figsize=(8.4,3))
    for ax,condition in zip(axes,['none','benign_override']):
        sub=done[done.condition.eq(condition)];rates=sub.pivot_table(index='family',columns='topology',values='any_round_violation',aggfunc='mean').reindex(index=families,columns=['ring','star','complete'])
        labels=np.empty(rates.shape,dtype=object)
        for i,family in enumerate(families):
            for j,topology in enumerate(rates.columns):
                group=sub[sub.family.eq(family)&sub.topology.eq(topology)];labels[i,j]=f'{int(group.any_round_violation.sum())}/{len(group)}'
        sns.heatmap(rates.astype(float),annot=labels,fmt='',vmin=0,vmax=1,cmap='Blues',cbar=False,ax=ax,linewidths=2)
        ax.set(title='Control' if condition=='none' else 'Injected',xlabel='Topology',ylabel='Task family')
    save(fig,'03_topology_counts')
    temporal=temporal_patch_rows(data)
    fig,axes=plt.subplots(1,2,figsize=(8.7,3.0),gridspec_kw={'width_ratios':[1,5]})
    exposure=np.array([[r['direct_deliveries']] for r in temporal]);counts=np.array([r['violations'] for r in temporal])
    sns.heatmap(exposure,annot=exposure.astype(str),fmt='',vmin=0,vmax=4,cmap='Blues',cbar=False,linewidths=2,ax=axes[0],annot_kws={'fontsize':11})
    labels=np.array([[f'{n}/4' for n in row] for row in counts])
    sns.heatmap(counts,annot=labels,fmt='',vmin=0,vmax=4,cmap='Oranges',cbar=False,linewidths=2,ax=axes[1],annot_kws={'fontsize':11})
    axes[0].set(title='Direct deliveries',xticklabels=['per run'],yticklabels=[f"{r['topology']} · {r['seed']}" for r in temporal],xlabel='',ylabel='Injected patch run')
    axes[0].tick_params(axis='y',rotation=0)
    axes[1].set(title='Strict path flags / 4 downstream agents',xticklabels=['0','1 · exposed','2','3','4 · final'],yticklabels=[],xlabel='Round',ylabel='')
    fig.suptitle('Strict path scorer: 17 intermediate flags · 20 direct deliveries · 0 final flags',fontsize=11,fontweight='bold',y=1.04)
    save(fig,'07_transient_behavior')

    monitor=pd.DataFrame(data['monitor_observations']);fig,axes=plt.subplots(1,2,figsize=(8.5,2.7))
    if monitor.truth.any():raise ValueError('This compact figure caption requires zero oracle positives; revise before reuse')
    for ax,policy in zip(axes,['communications_only','communications_and_outputs']):
        values=[];labels=[]
        for topology in ['ring','star','complete']:
            rates=[];counts=[]
            for visibility in [.25,.5,.75,1.]:
                sub=monitor[monitor.policy.eq(policy)&monitor.topology.eq(topology)&monitor.monitor_seed.eq(404)&monitor.visibility.eq(visibility)]
                if sub.empty:raise ValueError('Missing monitor cell')
                rates.append(sub.prediction.mean());counts.append(f'{int(sub.prediction.sum())}/{len(sub)}')
            values.append(rates);labels.append(counts)
        sns.heatmap(np.array(values),annot=np.array(labels),fmt='',vmin=0,vmax=1,cmap='Oranges',cbar=False,linewidths=3,ax=ax,annot_kws={'fontsize':11})
        ax.set(title=policy.replace('_',' '),xticklabels=['25%','50%','75%','100%'],yticklabels=['ring','star','complete'],xlabel='Visible message fraction',ylabel='');ax.tick_params(axis='y',rotation=0)
    fig.suptitle('False alarms / negative projections · mask 404 · recall undefined',fontsize=11,fontweight='bold',y=1.08)
    save(fig,'04_monitor_false_alarms')
    neural=pd.DataFrame(data['neural']);fig,axes=plt.subplots(1,2,figsize=(8.5,3.1))
    for kind,label in [('capability_control','Capital-pair control'),('task_shaped_probe','Record-status probe')]:
        sub=neural[neural.kind.eq(kind)].sort_values('layer');axes[0].plot(sub.layer,sub.patch_delta,marker='o',label=label);axes[1].plot(sub.layer,sub.restoration,marker='o',label=label)
    for ax in axes:ax.axhline(0,color='.6',lw=.7);ax.set_xlabel('GPT-2 layer');ax.set_xticks([0,5,11]);ax.legend(frameon=False,fontsize=8)
    axes[0].set(title='Measured activation-patching effect',ylabel='Target-logit change');axes[1].set(title='Normalized restoration',ylabel='Effect / clean–corrupt logit gap')
    for ax in axes:
        for line in ax.lines:
            if len(line.get_xdata())!=3:continue
            for x,y in zip(line.get_xdata(),line.get_ydata()):ax.annotate(f'{y:.2g}',(x,y),xytext=(3,6),textcoords='offset points',fontsize=8)
        ax.margins(y=.25)
    save(fig,'05_reference_checkpoint')
    fig,ax=plt.subplots(figsize=(7,3));sns.stripplot(data=done,x='family',y='runtime_seconds',hue='condition',order=families,palette=colors,dodge=True,jitter=.1,ax=ax)
    ax.set(xlabel='Task family',ylabel='Recorded run seconds',title='Run timing includes controller and thermal pauses');ax.legend(title='Condition',frameon=False,fontsize=8)
    save(fig,'06_run_timing')
    done.to_csv(out/'completed_runs.csv',index=False);summary.to_csv(out/'task_summary.csv',index=False)
    selected={'main':['01_experiment_flow','07_transient_behavior','02_task_outcomes'],
              'appendix':['03_topology_counts','04_monitor_false_alarms','05_reference_checkpoint','06_run_timing'],
              'selection_reason':'Three main figures communicate controlled architecture, time-resolved failures and paired task outcomes; monitor/reference diagnostics remain explicit appendix evidence.'}
    manifest={'evidence_sha256':sha(evidence),'analysis_script_sha256':sha(Path(__file__)),'selected':selected,'files':{p.name:sha(p) for p in files},
              'complete_runs':len(done),'all_attempts':len(runs),'observed_responses':int(runs.responses.sum()),
              'completed_responses':int(done.responses.sum()),'rq3_development_runs':len(data['rq3_development']),
              'monitor_projections':len(monitor),'neural_captures':len(neural)}
    (out/'figure_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    freeze=sub.add_parser('freeze');freeze.add_argument('--campaign',type=Path,required=True);freeze.add_argument('--development',type=Path,default=ROOT/'results/studies');freeze.add_argument('--neural',type=Path,default=ROOT/'results/neural');freeze.add_argument('--out',type=Path,required=True)
    plot=sub.add_parser('figures');plot.add_argument('--evidence',type=Path,required=True);plot.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='freeze':
        result=freeze_evidence(args.campaign,args.development,args.neural,args.out);print('Frozen numerical evidence:',len(result['runs']),'attempts;',len(result['rq3_development']),'separate RQ3 pilot runs')
    else:
        result=figures(args.evidence,args.out);print('Figures generated:',len(result['files']),'files;',result['complete_runs'],'completed primary runs')
