"""Reduce advisory-judge review effort with a blinded, stratified human subsample.

All machine judgments remain provisional. This creates blank human labels; it
does not certify or silently clear either selected or unselected artifacts.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re

from contagion.review import validate_review
from contagion.storage import write_json
from build_review_workspace import build as build_workspace
from judge_artifact_queue import sample_input
from run_pilot import ROOT


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_sources(queue,judge):
    queue=Path(queue);raw=json.loads((queue/'review_inputs.json').read_text())
    inputs=raw['samples'];oracle=json.loads((queue/'oracle_labels.private.json').read_text());judged=json.loads(Path(judge).read_text())
    def index(rows):
        result={}
        for row in rows:
            key=row['sample_id']
            if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',key) or key in result:raise ValueError('Invalid or duplicate review sample')
            result[key]=row
        return result
    samples=index(inputs);truth=index(oracle['labels']);predictions=index(judged['results'])
    if not samples or len(samples)>256 or set(samples)!=set(truth) or set(samples)!=set(predictions):raise ValueError('Require matching complete input/oracle/judge coverage')
    validated={}
    for key,row in samples.items():
        if type(truth[key]['violation']) is not bool or truth[key]['behavior'] not in {'compliant','violation','refusal','ambiguous','unscorable'}:raise ValueError('Invalid oracle behavior')
        value={k:v for k,v in predictions[key].items() if k!='sample_id'}
        result=validate_review(value,sample_input(row))
        validated[key]={'sample_id':key,**result.model_dump()}
    return raw,samples,oracle,truth,validated


def validate_secondary(samples,path):
    if path is None:return {}
    raw=json.loads(Path(path).read_text());result={}
    if not isinstance(raw.get('results'),list) or not raw['results']:raise ValueError('Secondary judge needs a nonempty declared subset')
    for row in raw['results']:
        key=row['sample_id']
        if not isinstance(key,str) or key not in samples or key in result:raise ValueError('Unknown or duplicate secondary judge sample')
        value={k:v for k,v in row.items() if k!='sample_id'}
        result[key]={'sample_id':key,**validate_review(value,sample_input(samples[key])).model_dump()}
    return result


def reasons(oracle,judge,second=None):
    reviewers=[judge]+([second] if second is not None else []);result=[]
    if second is not None and judge['behavior']!=second['behavior']:result.append('cross_model_disagreement')
    if any(r['behavior'] in {'ambiguous','unscorable'} for r in reviewers):result.append('abstention')
    if any(r['behavior']!=oracle['behavior'] or (r['behavior']=='violation')!=oracle['violation'] for r in reviewers):result.append('disagreement')
    if oracle['violation'] or any(r['behavior']=='violation' for r in reviewers):result.append('high_impact_flag')
    return result


def stratum(oracle,judge,second=None):
    flags=reasons(oracle,judge,second)
    for name in ['cross_model_disagreement','abstention','disagreement','high_impact_flag']:
        if name in flags:return name
    return 'agreeing_unflagged'


def select(samples,truth,predictions,limit=16,seed=2408,secondary=None):
    if not 4<=limit<=16:raise ValueError('Human triage cap must be4..16')
    secondary=secondary or {}
    priority=(['cross_model_disagreement'] if secondary else [])+['disagreement','abstention','high_impact_flag','agreeing_unflagged']
    buckets={name:[] for name in priority}
    order=lambda key:hashlib.sha256((str(seed)+':'+key).encode()).hexdigest()
    for key in samples:buckets[stratum(truth[key],predictions[key],secondary.get(key))].append(key)
    for rows in buckets.values():rows.sort(key=order)
    quota=({'cross_model_disagreement':max(1,limit*3//8),'disagreement':max(1,limit*3//16),
            'abstention':max(1,limit//8),'high_impact_flag':max(1,limit//16),'agreeing_unflagged':max(1,limit//4)}
           if secondary else
           {'disagreement':max(1,limit*3//8),'abstention':max(1,limit*3//16),
            'high_impact_flag':max(1,limit*3//16),'agreeing_unflagged':max(1,limit//4)})
    selected=[]
    # Reserve random agreeing/unflagged controls before allocating risk strata.
    for name in ['agreeing_unflagged',*[n for n in priority if n!='agreeing_unflagged']]:
        selected.extend(buckets[name][:min(quota[name],limit-len(selected))])
    remainder=[key for name in priority for key in buckets[name] if key not in selected]
    selected.extend(remainder[:max(0,limit-len(selected))])
    # Shuffle display order so the private stratum order does not unblind reviewers.
    selected.sort(key=lambda key:hashlib.sha256(('display:'+str(seed)+':'+key).encode()).hexdigest())
    return selected,buckets


def triage(queue,judge,output,limit=16,seed=2408,root=ROOT,second_judge=None):
    queue=Path(queue);judge=Path(judge);output=Path(output).resolve();root=Path(root)
    if (root/'results/reviews').resolve() not in output.parents:raise ValueError('Triage outputs must remain in ignored results/reviews')
    if output.exists():raise ValueError('Use a fresh triage directory; existing human work is never overwritten')
    raw,samples,oracle,truth,predictions=validate_sources(queue,judge)
    secondary=validate_secondary(samples,second_judge)
    selected,buckets=select(samples,truth,predictions,limit,seed,secondary);output.mkdir(parents=True)
    write_json(output/'review_inputs.json',{'schema_version':raw.get('schema_version','blinded-artifact-audit-1.1'),'samples':[samples[key] for key in selected]})
    selected_oracle={k:v for k,v in oracle.items() if k!='labels'}
    selected_oracle.update(labels=[truth[key] for key in selected],parent_queue_samples=len(samples),
        sampling='Judge-informed stratified human triage from an already enriched audit; not population representative.',
        selected_samples=len(selected),parent_flagged_selected=oracle.get('flagged_selected'),
        parent_unflagged_selected=oracle.get('unflagged_selected'),
        flagged_selected=sum(truth[key]['violation'] for key in selected),
        unflagged_selected=sum(not truth[key]['violation'] for key in selected))
    write_json(output/'oracle_labels.private.json',selected_oracle)
    with (output/'human_labels.csv').open('x',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['sample_id','behavior','reason']);writer.writerows((key,'','') for key in selected)
    write_json(output/'judge-results.private.json',{'schema_version':'artifact-judge-1.0','calibrated':False,
        'source_judge_sha256':sha(judge),'results':[predictions[key] for key in selected]})
    if second_judge is not None:
        covered=[key for key in selected if key in secondary]
        write_json(output/'second-judge-results.private.json',{'schema_version':'artifact-judge-1.0','calibrated':False,
            'source_judge_sha256':sha(second_judge),'coverage_policy':'predeclared_partial_spotcheck',
            'parent_secondary_samples':len(secondary),'parent_queue_samples':len(samples),'covered_sample_ids':covered,
            'results':[secondary[key] for key in covered]})
    selection={name:{'eligible':len(keys),'selected':sum(key in selected for key in keys),
                     'omitted':sum(key not in selected for key in keys)} for name,keys in buckets.items()}
    write_json(output/'selection.private.json',{'schema_version':'human-triage-selection-1.0','seed':seed,'human_cap':limit,
        'parent_inputs_sha256':sha(queue/'review_inputs.json'),'parent_oracle_sha256':sha(queue/'oracle_labels.private.json'),
        'parent_judge_sha256':sha(judge),'parent_samples':len(samples),'selected_samples':len(selected),'strata':selection,
        'secondary_judge_sha256':sha(second_judge) if second_judge is not None else None,
        'secondary_coverage':{'parent_reviewed_samples':len(secondary),'parent_samples':len(samples),
                              'selected_reviewed_samples':sum(key in secondary for key in selected),'selected_samples':len(selected)},
        'risk_denominators_overlap':True,
        'risk_denominators':{name:sum(name in reasons(truth[key],predictions[key],secondary.get(key)) for key in samples)
                             for name in ['cross_model_disagreement','disagreement','abstention','high_impact_flag']},
        'assignments':[{'sample_id':key,'stratum':stratum(truth[key],predictions[key],secondary.get(key)),
                        'risk_reasons':reasons(truth[key],predictions[key],secondary.get(key)),
                        'secondary_reviewed':key in secondary,'selected':key in selected} for key in sorted(samples)],
        'limitations':['Judge-informed and flag-enriched selection is not prevalence representative.',
                      'Errors on omitted artifacts remain possible; all unselected samples remain unvalidated.',
                      'Secondary judge coverage is a declared subset, not a second full-queue evaluation.',
                      'Class disagreements select review cases; self-reported confidence is never averaged into a label.',
                      'Triage subset calibration does not establish population judge accuracy.','Humans should not open this private selection/oracle file before blinded review.']})
    def safe(value):
        text=str(value)
        return "'"+text if re.match(r'^\s*[=+@-]|^[\t\r\n]',text) else text
    with (output/'machine-judgments.provisional.private.csv').open('x',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['sample_id','machine_behavior','self_reported_confidence_uncalibrated',
            'needs_human_review','evidence_event_ids','machine_reason','secondary_behavior',
            'secondary_confidence_uncalibrated','secondary_evidence_event_ids','cross_model_class_disagreement',
            'selected_for_human','validation_status'])
        for key in sorted(samples):
            row=predictions[key]
            writer.writerow([safe(value) for value in [key,row['behavior'],row['confidence'],row['needs_human_review'],
                ';'.join(row['evidence_event_ids']),row['rubric_reason'],secondary.get(key,{}).get('behavior',''),
                secondary.get(key,{}).get('confidence',''),';'.join(secondary.get(key,{}).get('evidence_event_ids',[])),
                row['behavior']!=secondary[key]['behavior'] if key in secondary else 'not_compared',
                key in selected,'provisional_not_human_validated']])
    report={'schema_version':'provisional-advisory-review-1.0','machine_reviewed_samples':len(samples),
            'machine_behavior_counts':dict(Counter(r['behavior'] for r in predictions.values())),
            'human_selected_samples':len(selected),'human_labels_generated':0,'human_validated_samples':0,
            'unselected_samples_still_unvalidated':len(samples)-len(selected),'strata':selection,
            'secondary_reviewed_samples':len(secondary),'secondary_behavior_counts':dict(Counter(r['behavior'] for r in secondary.values())),
            'cross_model_compared_samples':len(secondary),
            'cross_model_class_disagreements':sum(predictions[key]['behavior']!=row['behavior'] for key,row in secondary.items()),
            'machine_confidence_status':'Self-report only; uncalibrated, not an alignment probability.',
            'clearance_policy':'Never automatically clear unsafe, ambiguous or unreviewed artifacts.',
            'interpretation':'Machine judgments are provisional triage advice, not independent human findings or general alignment labels.'}
    write_json(output/'machine-review.provisional.private.json',report)
    build_workspace(output,output/'artifact-triage.html',root=root)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--queue',type=Path,required=True);p.add_argument('--judge',type=Path,required=True);p.add_argument('--second-judge',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--limit',type=int,default=16);p.add_argument('--seed',type=int,default=2408);a=p.parse_args()
    result=triage(a.queue,a.judge,a.out,a.limit,a.seed,second_judge=a.second_judge)
    print('Machine-advisory triage prepared:',result['human_selected_samples'],'blank human-review samples from',result['machine_reviewed_samples'],'machine-reviewed artifacts; no human validation claimed.')
