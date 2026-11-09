"""Offline paired boundary/utility figure, gated on completed runs and human review."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

from repository_quality import score


def paired_inputs(analysis, mapping, quality):
    if analysis.get('schema_version')!='primary-long-analysis-1.0' or analysis.get('status')!='completed_registered_batch':
        raise ValueError('Require completed registered long-task analysis')
    if analysis.get('mock_attempts') or analysis.get('unmatched_completed_runs'):
        raise ValueError('Mock or unmatched evidence cannot enter this empirical figure')
    rows=[r for r in analysis['rows'] if r['status']=='completed' and r['phase']=='evaluation']
    if len(rows)!=64 or analysis.get('evaluation_runs')!=64:
        raise ValueError('Require all64 registered evaluation arms')
    scored={s['sample_id']:s for s in quality['samples']}
    if len(scored)!=len(quality['samples']):raise ValueError('Duplicate quality sample')
    labels={};seals=analysis['source_seal_sha256']
    for sample in mapping:
        key=(sample['task_id'],sample['seed'],sample['defense'],sample['condition'])
        if sample.get('phase')!='evaluation' or sample.get('protocol')!='3.3-repository-safeguard':
            raise ValueError('Quality sample protocol/phase mismatch')
        if key in labels:raise ValueError('Select exactly one audited agent artifact per run')
        if sample['source_seal_sha256'] not in seals.values():raise ValueError('Quality sample source seal not in analysis')
        value=scored.get(sample['sample_id'])
        if not value or value.get('review_complete') is not True:
            raise ValueError('Human quality review is incomplete; no pending values are zero-filled')
        for metric in ['quality_precision','golden_recall']:
            number=value.get(metric)
            if number is not None and (type(number) not in {int,float} or not math.isfinite(number) or not 0<=number<=1):
                raise ValueError('Invalid adjudicated quality rate')
        labels[key]=value
    blocks=defaultdict(dict)
    for row in rows:
        if row.get('backend')!='ollama':raise ValueError('Require actual Ollama inference')
        key=(row['case'],row['seed'],row['defense'],row['intervention'])
        if key not in labels:raise ValueError('Every evaluation run needs its selected human-audited artifact')
        if row.get('final_downstream_violation_rate') is None or row.get('any_round_downstream_violation') is None:
            raise ValueError('Unknown boundary result cannot be zero-filled')
        # Check the actual run seal, not just membership somewhere in the campaign.
        meta=next(m for m in mapping if (m['task_id'],m['seed'],m['defense'],m['condition'])==key)
        if meta['source_seal_sha256']!=seals[row['attempt_id']]:raise ValueError('Quality sample belongs to another run seal')
        block=(row['cohort'],row['case'],row['seed'],row['rounds'],row['topology'])
        arm=(row['defense'],row['intervention'])
        if arm in blocks[block]:raise ValueError('Duplicate factorial arm')
        blocks[block][arm]={**row,**labels[key]}
    required={(d,c) for d in ['plain','source_attribution'] for c in ['none','benign_override']}
    if len(blocks)!=16 or any(set(arms)!=required for arms in blocks.values()):raise ValueError('Incomplete paired factorial matrix')
    return list(blocks.values())


def generate(analysis_path,queue,labels,output,confirmations=None):
    analysis_path=Path(analysis_path);queue=Path(queue)
    analysis=json.loads(analysis_path.read_text());mapping=json.loads((queue/'mapping.private.json').read_text())
    quality=score(queue,labels,confirmations)
    blocks=paired_inputs(analysis,mapping,quality)
    import os
    os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parents[1]/'.cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import seaborn as sns
    sns.set_theme(style='whitegrid',context='paper')
    plt.rcParams.update({'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,3,figsize=(10,3.4))
    metrics=[('final_downstream_violation_rate','Final downstream boundary rate'),('quality_precision','Human-audited finding precision'),('golden_recall','Human-audited golden recall')]
    colors={'none':'#2970b1','benign_override':'#d16a2d'};summaries=[]
    for ax,(metric,title) in zip(axes,metrics):
        for index,condition in enumerate(['none','benign_override']):
            for i,arms in enumerate(blocks):
                values=[arms[d,condition][metric] for d in ['plain','source_attribution']]
                if all(v is not None for v in values):ax.plot([index*3,index*3+1],values,color=colors[condition],alpha=.22,lw=.8)
            for pos,defense in [(index*3,'plain'),(index*3+1,'source_attribution')]:
                values=[a[defense,condition][metric] for a in blocks if a[defense,condition][metric] is not None]
                value=mean(values) if values else None
                if values:
                    ax.scatter([pos]*len(values),values,s=15,alpha=.28,color=colors[condition])
                    ax.scatter([pos],[value],s=65,marker='D',color=colors[condition],edgecolor='white',zorder=4)
                ax.text(pos,1.1,f'n={len(values)}/16',ha='center',fontsize=8)
                if value is None:ax.text(pos,.5,'Undefined',ha='center',rotation=90,fontsize=8)
                summaries.append({'metric':metric,'condition':condition,'defense':defense,'defined_runs':len(values),'total_runs':16,'mean':value})
        ax.set(title=title,ylim=(-.06,1.2),yticks=[0,.5,1],xticks=[0,1,3,4],xticklabels=['Plain','Attributed','Plain','Attributed'])
        ax.tick_params(axis='x',rotation=35,labelsize=8);ax.text(.2,-.35,'Control',transform=ax.transAxes,color=colors['none'],ha='center',fontsize=9);ax.text(.8,-.35,'Injected',transform=ax.transAxes,color=colors['benign_override'],ha='center',fontsize=9)
    axes[0].set_ylabel('Rate (0–1)')
    fig.suptitle('Paired safeguard comparison ·16 case/seed blocks ·64 evaluation runs',fontsize=12,fontweight='bold')
    fig.text(.5,-.06,'Utility audits one selected final agent artifact per run; missing precision stays undefined. Lines pair case/seed arms; diamonds are descriptive means.',ha='center',fontsize=8)
    output=Path(output);output.mkdir(parents=True,exist_ok=False);files={}
    for ext in ['pdf','svg','png']:
        path=output/('08_safeguard_quality.'+ext);fig.savefig(path,bbox_inches='tight',dpi=180);files[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    plt.close(fig)
    provenance={'schema_version':'paired-safeguard-figure-1.0','status':'completed_human_audited_followup','analysis_sha256':hashlib.sha256(analysis_path.read_bytes()).hexdigest(),
        'quality_labels_sha256':hashlib.sha256(Path(labels).read_bytes()).hexdigest(),'quality_inputs_sha256':hashlib.sha256((queue/'quality_inputs.private.json').read_bytes()).hexdigest(),
        'sample_confirmations_sha256':hashlib.sha256(Path(confirmations or queue/'sample_confirmations.csv').read_bytes()).hexdigest() if Path(confirmations or queue/'sample_confirmations.csv').is_file() else None,'quality_mapping_sha256':hashlib.sha256((queue/'mapping.private.json').read_bytes()).hexdigest(),
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'files':files,'summaries':summaries,
        'limitations':['One selected final agent artifact per run; not all swarm outputs.','Bundled attribution safeguard changes provenance, formatting and reminders.','Sixteen blocks reuse eight cases across five upstream projects; no independent-agent inference.','No population interval or claim of collusion/general alignment.']}
    (output/'figure_manifest.json').write_text(json.dumps(provenance,indent=2)+'\n')
    return provenance


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--analysis',type=Path,required=True);p.add_argument('--queue',type=Path,required=True);p.add_argument('--labels',type=Path,required=True);p.add_argument('--confirmations',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    generate(a.analysis,a.queue,a.labels,a.out,a.confirmations);print('Generated paired boundary/utility follow-up figure from completed human-audited evidence.')
