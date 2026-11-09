"""Protocol3.7 paired boundary analysis; static task utility remains unvalidated."""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

from analyze_primary_long import artifact_boundary,contrasts,outcomes_from_events,uncertainty
from contagion.config import digest
from contagion.storage import verify,write_json
import large_study_acceptance_v37

ROOT=Path(__file__).resolve().parents[1]


def cutoff_time(value):
    when=datetime.fromisoformat(value.replace('Z','+00:00'))
    if when.tzinfo is None or when>datetime.now(timezone.utc):raise ValueError('Explicit timezone-aware current/past cutoff required')
    return when


def safe_uncertainty(comparisons):
    result=uncertainty(comparisons)
    keys=('cohort','comparison_type','defense','intervention','rounds','topology')
    for row in result:
        selected=[r for r in comparisons if all(r.get(k)==row.get(k) for k in keys)]
        for field,cluster in [('project_cluster_uncertainty','project'),('conditional_case_uncertainty','case')]:
            groups=defaultdict(list)
            for value in selected:
                if value.get(row['metric']) is not None:groups[value[cluster]].append(float(value[row['metric']]))
            means=[sum(values)/len(values) for values in groups.values()]
            if row[field]['interval'] is not None and means and min(means)==max(means):
                row[field].update(interval=None,status='no_observed_cluster_variation',
                    interpretation='Point estimate retained; a degenerate empirical bootstrap is not evidence of equivalence or safety.')
    return result


def analyze(queue,source=None,completed_batches=False,cutoff=None,allow_mock=False):
    queue=Path(queue);plan=large_study_acceptance_v37._plan(queue);gate=large_study_acceptance_v37.inspect(queue,source)
    failed_checks={c.criterion for c in gate.checks if c.status=='fail'}
    descriptive_failure_scope=completed_batches and failed_checks<={'sealed_attempts','explicit_failed_attempt_resolution','completed_registered_matrix'}
    if gate.harness_status=='blocked' and not descriptive_failure_scope:raise ValueError('Operational failure requires review before outcome analysis')
    if gate.development_source_location_gate!='passed':raise ValueError('Development source-location feasibility gate must pass before held-out analysis')
    if gate.mock_completed_runs and (not allow_mock or gate.live_completed_runs):raise ValueError('Mock/live results require explicit separate mock analysis')
    if completed_batches:
        if cutoff is None:raise ValueError('Completed-batch descriptive mode requires an explicit cutoff')
        limit=cutoff_time(cutoff)
    else:
        if gate.harness_status not in {'operational_checks_passed','operational_checks_passed_with_reviewed_retries'}:raise ValueError('Whole registered matrix incomplete; use explicit completed-batch mode')
        limit=cutoff_time(cutoff) if cutoff else None
    source=Path(source) if source else ROOT/'results/repository-runs'/queue.name
    rows=[];excluded=[];seals={};seen=set();all_runtime=0.0
    for path in sorted(source.glob('job-*/*/events.jsonl')):
        root=path.parent;index=int(root.parent.name.removeprefix('job-'));job=plan['jobs'][index]
        ident=digest([root.parent.name,root.name])[:20]
        if not all((root/f).is_file() for f in ['manifest.json','checksum.sha256','config.snapshot.json','outcome.json']):
            excluded.append({'attempt_id':ident,'reason':'unsealed_attempt'});continue
        if not verify(root):raise ValueError('Source changed after operational acceptance')
        m=json.loads((root/'manifest.json').read_text());c=json.loads((root/'config.snapshot.json').read_text())
        seals[ident]=hashlib.sha256((root/'checksum.sha256').read_bytes()).hexdigest();all_runtime+=m['duration_seconds']
        if limit and datetime.fromisoformat(m['ended_utc'])>limit:
            excluded.append({'attempt_id':ident,'reason':'ended_after_cutoff'});continue
        if m['status']!='completed':
            excluded.append({'attempt_id':ident,'reason':'failed_or_exhausted_not_behavioral_negative'});continue
        if index in seen:raise ValueError('Duplicate completed job')
        seen.add(index);identity=m['model_identity'];task=c['task_metadata']
        events=[json.loads(line) for line in path.read_text().splitlines()]
        cohort=digest({'plan':plan['plan_hash'],'identity':identity,'controller':m['controller_hash'],
                      'dataset':task['dataset'],'task_kind':task['task_kind'],'memory_policy':c['memory_policy']})
        temporal=[]
        for r in range(job['rounds']):
            artifacts=[e for e in events if e.get('event_type')=='artifact' and e.get('round')==r]
            flags=[artifact_boundary(e.get('content')) for e in artifacts if e.get('agent_id')!='agent_0']
            temporal.append({'round':r,'downstream_artifacts':len(flags),'known_downstream_flags':sum(v is not None for v in flags),
                'positive_downstream_flags':sum(v is True for v in flags),'delivered_messages':sum(e.get('event_type')=='message_delivered' and e.get('round')==r for e in events)})
        rows.append({'job_index':index,'attempt_id':ident,'case':job['task_id'],'project':task['project_group'],'dataset':task['dataset'],'task_kind':task['task_kind'],
            'seed':job['seed'],'defense':job['defense'],'intervention':job['intervention'],'phase':job['phase'],'rounds':job['rounds'],'topology':job['topology'],
            'batch':job['batch'],'stage_id':job['stage_id'],'status':'completed','backend':identity['backend'],'model':identity['model'],'model_digest':identity.get('digest'),
            'worker':identity.get('worker_label','unspecified'),'cohort':cohort,'runtime_seconds':m['duration_seconds'],'returned_calls':m['completed_model_calls'],'http_attempts':m['http_attempts'],
            'temporal':temporal,**outcomes_from_events(events,job['rounds'],True)})
    batches=defaultdict(set)
    for index,job in enumerate(plan['jobs']):
        if job['phase']=='evaluation':batches[job['batch']].add(index)
    complete_batches={batch for batch,indices in batches.items() if indices<=seen}
    if completed_batches:
        retained=[]
        for row in rows:
            if row['phase']=='evaluation' and row['batch'] not in complete_batches:
                excluded.append({'attempt_id':row['attempt_id'],'reason':'incomplete_registered_batch_at_cutoff'})
            else:retained.append(row)
        rows=retained
    elif len(seen)!=plan['planned_runs']:
        raise ValueError('Selected cutoff does not include the complete registered matrix')
    evaluation=[r for r in rows if r['phase']=='evaluation']
    if not evaluation:raise ValueError('No complete evaluation batch available at selected cutoff')
    treatment,safeguard,did,unmatched=contrasts(rows)
    if unmatched:raise ValueError('Incomplete four-arm block in selected completed batches')
    cells=defaultdict(list)
    for row in evaluation:cells[(row['cohort'],row['defense'],row['intervention'],row['rounds'],row['topology'])].append(row)
    summary=[]
    for (cohort,defense,intervention,rounds,topology),selected in sorted(cells.items()):
        known=[r for r in selected if r['final_downstream_violation_rate'] is not None]
        summary.append({'cohort':cohort,'defense':defense,'intervention':intervention,'rounds':rounds,'topology':topology,'runs':len(selected),
                        'known_final_runs':len(known),'mean_final_downstream_scorer_rate':sum(r['final_downstream_violation_rate'] for r in known)/len(known) if known else None,
                        'quality_precision':None,'quality_recall':None})
    return {'schema_version':'large-benchmark-analysis-1.0','protocol':'3.7-benchmark-output-budget',
        'analysis_scope':'completed_registered_batches_descriptive' if completed_batches else 'completed_registered_matrix',
        'cutoff_utc':limit.isoformat() if limit else None,'planned_runs':plan['planned_runs'],'selected_completed_runs':len(rows),'evaluation_runs':len(evaluation),
        'completed_batches':sorted(complete_batches),'case_clusters':len({r['case'] for r in evaluation}),'project_clusters':len({r['project'] for r in evaluation}),
        'source_families':len({r['dataset'] for r in evaluation}),'case_seed_blocks':len(did),'backend':'mock' if gate.mock_completed_runs else 'ollama',
        'recorded_http_attempts_all_observed':gate.recorded_http_attempts,'conservative_physical_ledger':gate.physical_calls,'all_sealed_attempt_runtime_seconds':all_runtime,
        'failed_sealed_attempts':gate.failed_sealed_attempts,'unsealed_attempts':gate.unsealed_attempts,'exclusions':excluded,'rows':rows,'cells':summary,
        'treatment_contrasts':treatment,'safeguard_contrasts':safeguard,'difference_in_differences':did,
        'uncertainty':[] if completed_batches else safe_uncertainty([*treatment,*safeguard,*did]),
        'harness_acceptance_status':gate.harness_status,'resolved_retained_attempts':gate.explicitly_resolved_retained_attempts,
        'source_plan_hash':plan['plan_hash'],'source_catalog_hash':plan['catalog_hash'],'source_seal_sha256':seals,'acceptance_report_hash':gate.report_hash,'acceptance_report':gate.model_dump(),
        'analysis_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'quality_precision':None,'quality_recall':None,'quality_status':'awaiting_independent_reference_adjudication','official_benchmark_score':False,
        'limitations':['Completed-batch subsets are timing-censored descriptive checkpoints, not the completed registered full matrix.' if completed_batches else 'The full matrix remains conditional on selected source projects and benchmark adaptations.',
            'Static findings and plans are not executed fixes or official agentic benchmark scores.',
            'Boundary flags are operational scores, not adjudicated misalignment or intentional collusion.',
            'The previous16 compliant human labels do not validate quality or boundary judgments on these new cases.',
            'Semantic utility remains unknown; raw reference judgments are not inferred from empty or numerous findings.',
            'Agent histories retain only two own prior rounds while the original task remains visible.',
            'Attribution bundles formatting, provenance and reminders; ring-only studies cannot estimate topology effects.',
            'Case/seed/arm dependence and shared upstream projects constrain uncertainty; runtime includes all observed sealed attempts.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--queue',type=Path,required=True);p.add_argument('--source',type=Path);p.add_argument('--completed-batches',action='store_true');p.add_argument('--cutoff');p.add_argument('--allow-mock',action='store_true');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if (ROOT/'results').resolve() not in a.out.resolve().parents:p.error('Private analysis must stay under ignored results')
    result=analyze(a.queue,a.source,a.completed_batches,a.cutoff,a.allow_mock);a.out.parent.mkdir(parents=True,exist_ok=True);write_json(a.out,result)
    print(result['analysis_scope'],':',result['evaluation_runs'],'selected runs; quality remains unvalidated.')
