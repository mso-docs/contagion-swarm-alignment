"""Freeze separately completed protocol4 RQ3 numerical evidence; never pools compact runs."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

from contagion.storage import verify,write_json

FIELDS=['run_id','backend','model','model_digest','worker','freeze_hash','family','case','seed','topology',
        'condition','executor','context','phase','status','completed_calls','http_attempts',
        'attempted_forbidden','actual_state_violation','refusal_rate','task_success_rate']


def freeze(analysis,source,output):
    analysis=Path(analysis);source=Path(source);data=json.loads(analysis.read_text());rows=data['rows']
    if len(rows)!=64 or data['completed']!=64 or data['coverage']['mock_attempts'] or data['failed_or_exhausted']:raise ValueError('Follow-up must be the complete live64-run matrix')
    keys={(r['case'],r['seed'],r['topology'],r['condition'],r['executor'],r['context']) for r in rows}
    expected=set(itertools.product(range(4),[13001],['single','complete'],['none','benign_override'],['deny','permissive_simulator'],['matched_reset','natural_history']))
    if keys!=expected or len({r['run_id'] for r in rows})!=64:raise ValueError('Incomplete/duplicate follow-up matrix')
    if any(r['backend']!='ollama' or r['phase']!='confirmatory' or r['family']!='record' or r['status']!='completed' for r in rows):raise ValueError('Mixed evidence')
    seals={};source_hashes=set()
    for row in rows:
        name=row['run_id']
        if Path(name).name!=name:raise ValueError('Unapproved run ID')
        root=source/name
        if not verify(root):raise ValueError('Run integrity failure')
        seal=hashlib.sha256((root/'checksum.sha256').read_bytes()).hexdigest()
        if data['source_seal_sha256'].get(name)!=seal:raise ValueError('Analysis seal mismatch')
        manifest=json.loads((root/'manifest.json').read_text());outcome=json.loads((root/'outcome.json').read_text())
        if manifest['completed_model_calls']!=row['completed_calls'] or manifest['http_attempts']!=row['http_attempts']:raise ValueError('Call accounting mismatch')
        for key in ['attempted_forbidden','actual_state_violation','refusal_rate','task_success_rate']:
            if outcome[key]!=row[key]:raise ValueError('Outcome mismatch')
        source_hashes.add(manifest['source_hash']);seals[name]=seal
    if len(source_hashes)!=1:raise ValueError('Mixed controller sources')
    result={'schema_version':'rq3-followup-evidence-1.0','protocol':'4.0-confirmatory','analysis_sha256':hashlib.sha256(analysis.read_bytes()).hexdigest(),
            'analysis_script_sha256':data['analysis_script_sha256'],'source_hash':next(iter(source_hashes)),
            'complete_runs':64,'responses':sum(r['completed_calls'] for r in rows),'case_clusters':4,'seeds':[13001],
            'attempting_runs':sum(r['attempted_forbidden'] for r in rows),'state_violating_runs':sum(r['actual_state_violation'] for r in rows),
            'runs_with_refusal':sum(r['refusal_rate']>0 for r in rows),'mean_task_success':sum(r['task_success_rate'] for r in rows)/64,
            'context_counts':{c:sum(r['context']==c for r in rows) for c in ['matched_reset','natural_history']},
            'source_seal_sha256':seals,'rows':[{k:r[k] for k in FIELDS} for r in rows],
            'limitations':['Separate from compact protocol2.6 and8development RQ3 runs;4integration prechecks excluded.',
                          'Four fixed case clusters and one seed; population confidence intervals suppressed.',
                          'No individual refusals means no refusal-bypass claim.',
                          'Matched-reset is an identity-only control; natural histories retain an information-structure confound.',
                          'No independent human adjudication or same-model neural explanation established.']}
    if result['responses']!=320:raise ValueError('Unexpected follow-up call count')
    write_json(Path(output),result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--analysis',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=freeze(a.analysis,a.source,a.out);print('Separate RQ3 freeze:',result['complete_runs'],'runs /',result['responses'],'responses; prechecks excluded.')
