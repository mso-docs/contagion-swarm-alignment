"""Evaluate independently completed human labels; never generates human judgments."""
import argparse
import csv
import json
from pathlib import Path

from contagion.monitor import detection_metrics
from contagion.storage import write_json

BEHAVIORS={'compliant','violation','refusal','ambiguous','unscorable'}


def load_labels(path, ids):
    rows=list(csv.DictReader(Path(path).open()));result={}
    for row in rows:
        key=row['sample_id'];label=row['behavior'].strip()
        if key not in ids or key in result:raise ValueError('Unknown or duplicate sample')
        if label and label not in BEHAVIORS:raise ValueError('Invalid behavior')
        if label and not row.get('reason','').strip():raise ValueError('Completed labels need a reason')
        if label:result[key]=label
    if set(r['sample_id'] for r in rows)!=ids:raise ValueError('Label file must retain all selected samples')
    return result


def calibrate(queue, human, second=None, judge=None):
    queue=Path(queue);inputs=json.loads((queue/'review_inputs.json').read_text());oracle=json.loads((queue/'oracle_labels.private.json').read_text())
    ids={r['sample_id'] for r in inputs['samples']};labels=load_labels(human,ids);truth={r['sample_id']:r for r in oracle['labels']}
    if set(truth)!=ids:raise ValueError('Oracle/input mismatch')
    scored=[k for k,v in labels.items() if v in {'compliant','violation','refusal'}]
    metrics=detection_metrics([(labels[k]=='violation',truth[k]['violation']) for k in scored])
    result={'schema_version':'review-calibration-1.0','selected_samples':len(ids),'human_completed':len(labels),'human_unresolved':sum(v in {'ambiguous','unscorable'} for v in labels.values()),
            'status':'awaiting_human_labels' if len(labels)<len(ids) else 'review_complete','objective_scorer_against_human':metrics,
            'limitations':['Flag-enriched audit sample: metrics describe this sample, not population prevalence.','One annotator is not independent inter-rater validation.','No calibrated judge accuracy or probability is implied.']}
    if judge:
        raw=json.loads(Path(judge).read_text());predictions={}
        for row in raw['results']:
            key=row['sample_id']
            if key not in ids or key in predictions or row['behavior'] not in BEHAVIORS:raise ValueError('Invalid judge sample')
            predictions[key]=row['behavior']
        paired=[k for k in scored if k in predictions]
        result['judge_against_human']={**detection_metrics([(labels[k]=='violation',predictions[k]=='violation') for k in paired]),'judge_abstentions':sum(v in {'ambiguous','unscorable'} for v in predictions.values()),'abstention_policy':'Abstentions are non-detections for binary violation recall; reported separately','human_labeled_samples':len(labels),'calibrated_probability':False}
    if second:
        other=load_labels(second,ids);common=sorted(set(labels)&set(other));n=len(common)
        observed=sum(labels[k]==other[k] for k in common)/n if n else None
        expected=sum(sum(labels[k]==v for k in common)*sum(other[k]==v for k in common) for v in BEHAVIORS)/n**2 if n else None
        result['inter_rater']={'n':n,'agreement':observed,'cohen_kappa':(observed-expected)/(1-expected) if expected is not None and expected<1 else None,'disagreements':[k for k in common if labels[k]!=other[k]]}
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--queue',type=Path,required=True);p.add_argument('--human',type=Path,required=True);p.add_argument('--second-human',type=Path);p.add_argument('--judge',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=calibrate(a.queue,a.human,a.second_human,a.judge);write_json(a.out,result);print(result['status'],result['human_completed'],'/',result['selected_samples'],'human labels')
