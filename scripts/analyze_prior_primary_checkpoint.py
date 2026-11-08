"""Descriptive cutoff analysis of complete blocks in an unfinished protocol3.3 study."""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path

from analyze_primary_long import contrasts,outcomes_from_events
from contagion.config import digest
from contagion.events import read_events
from contagion.storage import verify,write_json
from contagion.topology import study_adjacency
from run_pilot import ROOT

PROTOCOL='3.3-repository-safeguard'
ARMS={('plain','none'),('plain','benign_override'),('source_attribution','none'),('source_attribution','benign_override')}


def _plan(queue):
    from primary_long_queue import validate_plan
    return validate_plan(queue)


def _task(plan,job):
    from primary_long_queue import load_payload
    return load_payload(plan,job)[0]


def when(value):
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:raise ValueError('Timezone-aware timestamp required')
    return parsed


def block_key(job):return (job['task_id'],job['seed'],job['rounds'],job['topology'])


def analyze(queue,cutoff,source=None):
    queue=Path(queue);limit=when(cutoff)
    if limit>datetime.now(timezone.utc):raise ValueError('Cutoff must be current or past')
    plan=_plan(queue)
    if plan.get('protocol_version')!=PROTOCOL or len(plan['jobs'])!=plan['planned_runs']:raise ValueError('Wrong prior study protocol or schedule')
    source=Path(source) if source else ROOT/'results/repository-runs'/queue.name
    registered=defaultdict(dict)
    for index,job in enumerate(plan['jobs']):
        if job['phase']!='evaluation':continue
        arm=(job['defense'],job['intervention']);group=registered[block_key(job)]
        if arm in group:raise ValueError('Duplicate registered factorial arm')
        group[arm]=index
    if not registered or any(set(group)!=ARMS for group in registered.values()):raise ValueError('Registered four-arm comparison is incomplete')
    tasks={job['task_id']:_task(plan,job) for job in plan['jobs']}
    rows=[];excluded=[];seals={};observed_jobs=set();completed_seen=set()
    returned=physical=failures=unsealed=sealed_completed=0;runtime=event_span=0.0
    for root in sorted(source.glob('job-*/*')):
        if not root.is_dir():continue
        if root.is_symlink() or root.parent.is_symlink():raise ValueError('Unsafe attempt reference')
        try:index=int(root.parent.name.removeprefix('job-'));job=plan['jobs'][index]
        except (ValueError,IndexError):raise ValueError('Unknown prior allocation job') from None
        if index<0 or root.parent.name!=f'job-{index:03}':raise ValueError('Unknown prior allocation index')
        observed_jobs.add(index);identity=digest([root.parent.name,root.name])[:20];event_file=root/'events.jsonl'
        events=[];malformed=False
        if event_file.is_symlink():raise ValueError('Unsafe event reference')
        if event_file.is_file():
            for line in event_file.read_text().splitlines():
                try:events.append(json.loads(line))
                except ValueError:malformed=True;break
        attempts=sum(e.get('event_type')=='http_attempt' for e in events)
        responses=sum(e.get('event_type')=='inference_response' for e in events)
        physical+=attempts;returned+=responses
        files=('manifest.json','checksum.sha256','config.snapshot.json','outcome.json','events.jsonl')
        if not all((root/name).is_file() for name in files):
            unsealed+=1;times=[when(e['timestamp_utc']) for e in events if e.get('timestamp_utc')]
            span=max(0,(max(times)-min(times)).total_seconds()) if times else 0;event_span+=span
            excluded.append({'attempt_id':identity,'job_index':index,'reason':'unsealed_attempt_not_behavioral_negative',
                             'recorded_http_attempts':attempts,'returned_calls':responses,'observed_event_span_seconds':span})
            continue
        if any((root/name).is_symlink() for name in files) or malformed or not verify(root):raise ValueError('Prior attempt seal or JSONL integrity failed')
        manifest=json.loads((root/'manifest.json').read_text());config=json.loads((root/'config.snapshot.json').read_text())
        model=manifest['model_identity'];task=tasks[job['task_id']]
        if (manifest.get('protocol_version')!=PROTOCOL or config.get('protocol_version')!=PROTOCOL
            or manifest.get('plan_hash')!=plan['plan_hash'] or config.get('registry_freeze_hash')!=plan['plan_hash']
            or manifest.get('source_hash')!=plan['source_hash'] or config.get('source_hash')!=plan['source_hash']
            or manifest.get('source_unchanged_on_exit') is not True
            or manifest.get('controller_hash')!=plan['dependencies']['primary_repository_runner.py']
            or config.get('controller_hash')!=manifest['controller_hash']):raise ValueError('Prior attempt source/controller provenance mismatch')
        if (model.get('backend')!='ollama' or model.get('model')!=plan['model'] or model.get('digest')!=plan['model_digest']
            or model.get('worker_label')!='primary' or config.get('model_identity')!=model):raise ValueError('Prior model/worker identity mismatch')
        if (any(config.get(key)!=job[key] for key in ('task_id','phase','rounds','topology','seed','defense','intervention'))
            or config.get('task_metadata')!=task):raise ValueError('Prior run differs from registered assignment or pinned task')
        if manifest.get('graph')!=study_adjacency(job['topology'],5):raise ValueError('Prior topology differs from assignment')
        if (manifest.get('completed_model_calls')!=responses or manifest.get('http_attempts')!=attempts
            or manifest.get('parse_failures')!=sum(e.get('event_type')=='parse_failure' for e in events)):
            raise ValueError('Prior manifest/event counters disagree')
        duration=manifest.get('duration_seconds')
        if type(duration) not in {float,int} or not math.isfinite(duration) or duration<0:raise ValueError('Invalid prior runtime')
        runtime+=duration;seals[identity]=hashlib.sha256((root/'checksum.sha256').read_bytes()).hexdigest()
        ended=when(manifest['ended_utc']);complete=manifest['status']=='completed'
        if manifest['status'] not in {'completed','failed','budget_exhausted'}:raise ValueError('Unknown prior attempt status')
        if not complete:
            failures+=1;excluded.append({'attempt_id':identity,'job_index':index,'reason':'failed_or_exhausted_not_behavioral_negative',
                                        'runtime_seconds':duration,'recorded_http_attempts':attempts,'returned_calls':responses});continue
        if index in completed_seen:raise ValueError('Duplicate prior completed job')
        completed_seen.add(index);sealed_completed+=1
        expected=[(f'agent_{a}',r) for r in range(job['rounds']) for a in range(5)]
        if responses!=job['calls'] or attempts!=responses or manifest['parse_failures']:
            raise ValueError('Completed prior call coverage mismatch')
        for kind in ('inference_requested','inference_response','artifact'):
            if [(e.get('agent_id'),e.get('round')) for e in events if e.get('event_type')==kind]!=expected:
                raise ValueError('Completed prior artifact/request coverage mismatch')
        if ended>limit:
            excluded.append({'attempt_id':identity,'job_index':index,'reason':'ended_after_cutoff'});continue
        if job['phase']!='evaluation':
            excluded.append({'attempt_id':identity,'job_index':index,'reason':'integration_precheck_not_heldout_evaluation'});continue
        cohort=digest({'plan':plan['plan_hash'],'protocol':PROTOCOL,'source':manifest['source_hash'],
                       'identity':model,'controller':manifest['controller_hash']})
        temporal=[]
        from analyze_primary_long import artifact_boundary
        for r in range(job['rounds']):
            artifacts=[e for e in events if e.get('event_type')=='artifact' and e.get('round')==r and e.get('agent_id')!='agent_0']
            flags=[artifact_boundary(e.get('content')) for e in artifacts]
            temporal.append({'round':r,'downstream_artifacts':len(flags),'known_downstream_flags':sum(v is not None for v in flags),
                             'positive_downstream_flags':sum(v is True for v in flags),
                             'delivered_messages':sum(e.get('event_type')=='message_delivered' and e.get('round')==r for e in events)})
        rows.append({'job_index':index,'attempt_id':identity,'case':job['task_id'],'project':task['repository'],
                     'dataset':task.get('dataset','withmartian/code-review-benchmark'),'task_kind':'code_review',
                     'seed':job['seed'],'rounds':job['rounds'],'topology':job['topology'],'defense':job['defense'],
                     'intervention':job['intervention'],'phase':'evaluation','status':'completed','cohort':cohort,
                     'backend':'ollama','model':model['model'],'model_digest':model['digest'],'worker':'primary',
                     'runtime_seconds':duration,'returned_calls':responses,'http_attempts':attempts,'temporal':temporal,
                     **outcomes_from_events(events,job['rounds'],True)})
    eligible={row['job_index'] for row in rows}
    selected_blocks={key for key,group in registered.items() if set(group.values())<=eligible}
    selected=[]
    for row in rows:
        key=(row['case'],row['seed'],row['rounds'],row['topology'])
        if key in selected_blocks:selected.append(row)
        else:excluded.append({'attempt_id':row['attempt_id'],'job_index':row['job_index'],'reason':'incomplete_four_arm_block_at_cutoff'})
    treatment,safeguard,did,unmatched=contrasts(selected)
    if unmatched:raise ValueError('Selected checkpoint contains an unmatched arm')
    return {'schema_version':'prior-primary-checkpoint-1.0','protocol':PROTOCOL,
            'analysis_scope':'completed_four_arm_blocks_at_cutoff_descriptive','cutoff_utc':limit.isoformat(),
            'study_status':'partial_or_timing_censored_checkpoint_not_completed_study',
            'planned_runs':plan['planned_runs'],'planned_calls':plan['planned_calls'],
            'selected_completed_runs':len(selected),'evaluation_runs':len(selected),
            'case_seed_blocks':len(selected_blocks),'case_clusters':len({r['case'] for r in selected}),
            'project_clusters':len({r['project'] for r in selected}),'source_families':len({r['dataset'] for r in selected}),
            'all_observed_completed_attempts':sealed_completed,'all_observed_failed_sealed_attempts':failures,
            'all_observed_unsealed_attempts':unsealed,'all_observed_recorded_http_attempts':physical,
            'all_observed_returned_calls':returned,'all_observed_sealed_runtime_seconds':runtime,
            'all_observed_unsealed_event_span_seconds':event_span,'registered_jobs_without_observed_attempt':len(plan['jobs'])-len(observed_jobs),
            'exclusions':excluded,'rows':selected,'treatment_contrasts':treatment,'safeguard_contrasts':safeguard,
            'difference_in_differences':did,'uncertainty':[],'quality_precision':None,'quality_recall':None,
            'quality_status':'awaiting_independent_reference_adjudication','official_benchmark_score':False,
            'source_plan_hash':plan['plan_hash'],'source_seal_sha256':seals,
            'analysis_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'limitations':['Cutoff-selected completed blocks are timing-censored descriptive evidence, not the registered full study.',
                           'Runtime and call totals describe all observed attempts, including attempts after the evidence cutoff.',
                           'Unsealed call counts are observed lower bounds; their full duration and possible in-flight requests remain unknown.',
                           'Operational boundary signals are not validated semantic quality, collusion, intent or general alignment.',
                           'Cases, seeds, arms and source-project identifiers are dependent; no uncertainty interval or population claim is made.',
                           'The safeguard bundles source provenance, formatting and reminders; no isolated mechanism is identified.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--queue',type=Path,required=True)
    parser.add_argument('--cutoff',required=True);parser.add_argument('--source',type=Path);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    if args.out.exists() or (ROOT/'results').resolve() not in args.out.resolve().parents:parser.error('Use a fresh private output under results')
    result=analyze(args.queue,args.cutoff,args.source);args.out.parent.mkdir(parents=True,exist_ok=True);write_json(args.out,result)
    print('Prior-primary checkpoint:',result['evaluation_runs'],'runs in',result['case_seed_blocks'],'complete blocks; full-study and utility claims remain unavailable.')
