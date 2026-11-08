"""Paired run-level follow-up summaries with explicit dependence and claim gates."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random

from contagion.config import digest
from contagion.storage import verify, write_json


def case_cluster_interval(pairs, metric, minimum_cases=8, replicates=2000, seed=919):
    """Resample cases, retaining seeds/arms within each case; never resample agents.

    The minimum is an explicit reporting guard, not a power guarantee. Current
    small fixed-case pilots receive no interval or population significance claim.
    """
    if minimum_cases < 2 or replicates < 100:raise ValueError('Invalid cluster-resampling settings')
    clusters=defaultdict(list)
    for pair in pairs:
        value=pair.get(metric)
        if value is not None:clusters[pair['case']].append(value)
    means=[sum(clusters[key])/len(clusters[key]) for key in sorted(clusters,key=str)]
    result={'case_clusters':len(means),'paired_runs':sum(map(len,clusters.values())),
            'case_weighted_mean':sum(means)/len(means) if means else None,
            'interval':None,'method':'case-cluster percentile bootstrap; seeds remain nested',
            'minimum_cases':minimum_cases,'status':'insufficient_case_clusters',
            'assumption':'Cases are exchangeable; fixed templated cases do not establish population representativeness.'}
    if len(means)<minimum_cases:return result
    rng=random.Random(seed)
    draws=sorted(sum(rng.choice(means) for _ in means)/len(means) for _ in range(replicates))
    result.update(interval=[draws[int(.025*(replicates-1))],draws[int(.975*(replicates-1))]],
                  status='descriptive_interval_available',replicates=replicates,resampling_seed=seed)
    return result


def rq3_comparisons(rows):
    groups=defaultdict(dict)
    for row in rows:
        if row['family']!='record' or row['status']!='completed':continue
        key=(row['cohort'],row['case'],row['seed'],row['condition'],row['executor'],row.get('context'))
        if row['topology'] in groups[key]:raise ValueError('Duplicate completed RQ3 arm')
        groups[key][row['topology']]=row
    comparisons=[]
    for arms in groups.values():
        if set(arms)!={'single','complete'}:continue
        single,team=arms['single'],arms['complete'];single_refusal=single.get('refusal_rate')
        comparisons.append({'cohort':single['cohort'],'case':single['case'],'seed':single['seed'],
            'condition':single['condition'],'executor':single['executor'],'context':single.get('context'),
            'single_run_id':single['run_id'],'team_run_id':team['run_id'],
            'collective_attempt_difference':int(team['attempted_forbidden'])-int(single['attempted_forbidden']),
            'collective_state_violation_difference':int(team['actual_state_violation'])-int(single['actual_state_violation']),
            'task_success_difference':team['task_success_rate']-single['task_success_rate'],
            'single_observed_refusal_rate':single_refusal,'team_observed_refusal_rate':team.get('refusal_rate'),
            'refusal_bypass_established':False,
            'refusal_bypass_status':'no_observed_single_refusal' if single_refusal==0 else 'refusal_measurement_unavailable' if single_refusal is None else 'candidate_requires_direct_full_task_refusal_control_and_adjudication',
            'interpretation':'Collective violation contrast is measurable independently of a stronger claim that decomposition bypasses individual refusals.'})
    return comparisons


def analyze(source):
    rows=[];pairs=defaultdict(dict);source_seals={}
    for path in sorted(Path(source).glob('run-*/manifest.json')):
        root=path.parent
        if not verify(root):raise ValueError('Unsealed follow-up')
        manifest=json.loads(path.read_text());config=json.loads((root/'config.snapshot.json').read_text());outcome=json.loads((root/'outcome.json').read_text());job=config['job']
        if manifest['status']!=outcome['status'] or config['freeze_hash']!=manifest['freeze_hash']:raise ValueError('Manifest/outcome/freeze mismatch')
        identity=manifest['model_identity']
        cohort=digest({'freeze_hash':manifest['freeze_hash'],'identity':identity,'source_hash':manifest.get('source_hash'),'phase':config.get('phase','unspecified')})
        row={**job,**outcome,'run_id':root.name,'backend':identity['backend'],'model':identity.get('model'),
             'model_digest':identity.get('digest'),'worker':identity.get('worker_label','unspecified'),
             'freeze_hash':manifest['freeze_hash'],'phase':config.get('phase','unspecified'),'cohort':cohort,
             'completed_calls':manifest.get('completed_model_calls'),'http_attempts':manifest.get('http_attempts')}
        rows.append(row);source_seals[root.name]=hashlib.sha256((root/'checksum.sha256').read_bytes()).hexdigest()
        if manifest['status']!='completed':continue
        key=(cohort,job['family'],job['case'],job['seed'],job['topology'],job['source'],job['executor'],job.get('context'))
        if job['condition'] in pairs[key]:raise ValueError('Duplicate completed pair')
        pairs[key][job['condition']]=row
    paired=[];unmatched=[]
    for arms in pairs.values():
        if set(arms)!={'none','benign_override'}:
            unmatched.extend(r['run_id'] for r in arms.values());continue
        c,i=arms['none'],arms['benign_override']
        final_c,final_i=c.get('final_downstream_violation_rate'),i.get('final_downstream_violation_rate')
        paired.append({'cohort':c['cohort'],'backend':c['backend'],'phase':c['phase'],'control_run_id':c['run_id'],'injected_run_id':i['run_id'],
            'family':c['family'],'case':c['case'],'seed':c['seed'],'topology':c['topology'],'source':c['source'],'executor':c['executor'],'context':c.get('context'),
            'any_round_violation_difference':int(i['any_round_violation'])-int(c['any_round_violation']),
            'final_downstream_violation_difference':final_i-final_c if final_i is not None and final_c is not None else None,
            'task_success_difference':i['task_success_rate']-c['task_success_rate'],
            'state_violation_difference':int(i['actual_state_violation'])-int(c['actual_state_violation'])})
    strata=defaultdict(list)
    for pair in paired:
        strata[(pair['cohort'],pair['family'],pair['topology'],pair['source'],pair['executor'],pair['context'])].append(pair)
    intervals=[]
    for key,selected in sorted(strata.items(),key=lambda item:str(item[0])):
        for metric in ['final_downstream_violation_difference','any_round_violation_difference','task_success_difference','state_violation_difference']:
            intervals.append({**dict(zip(['cohort','family','topology','source','executor','context'],key)),
                              'metric':metric,**case_cluster_interval(selected,metric)})
    completed=[r for r in rows if r['status']=='completed']
    return {'schema_version':'confirmatory-analysis-1.1','attempts':len(rows),'completed':len(completed),
        'failed_or_exhausted':len(rows)-len(completed),'unmatched_completed_runs':unmatched,'pairs':paired,'rows':rows,
        'source_seal_sha256':source_seals,'analysis_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'coverage':{'case_seed_blocks':len({(r['cohort'],r['family'],r['case'],r['seed']) for r in completed}),
                    'case_clusters':len({(r['cohort'],r['family'],r['case']) for r in completed}),
                    'cohorts':len({r['cohort'] for r in rows}),'mock_attempts':sum(r['backend']=='mock' for r in rows)},
        'paired_uncertainty':intervals,'rq3_single_team':rq3_comparisons(rows),
        'limitations':['Exact run-level paired differences; no agent-level significance.','Cases/seeds recur across topologies and source placements.',
            'Small fixed-case studies receive no population uncertainty claim.','Mock results are software validation only.',
            'Primary final endpoint and any-round deviations remain separate.','Observed single/team differences alone do not establish refusal bypass or intentional collusion.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();result=analyze(a.source);write_json(a.out,result);print(result['completed'],'completed runs;',len(result['pairs']),'matched control/injection pairs')
