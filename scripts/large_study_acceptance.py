"""Read-only protocol3.4 acceptance: operational integrity is not model success."""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel,ConfigDict,Field

from contagion.config import digest
from contagion.storage import verify,write_json
from contagion.topology import study_adjacency

ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN_INPUT_KEYS={'oracle','golden','oracle_file','oracle_sha256','solution_patch','test_patch','scored_outcome','adopted_instruction','intervention','expected_outcome'}


class Check(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    criterion:Literal['frozen_plan','controller_safety','matched_four_arm_blocks','heldout_split','case_diversity','project_diversity','source_diversity','sealed_attempts','explicit_failed_attempt_resolution','attempt_assignment','call_and_artifact_coverage','routing_and_history','completed_prechecks','development_feasibility','completed_registered_matrix']
    status:Literal['pass','fail','pending','limited']
    count:int=Field(ge=0)


class Report(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    schema_version:Literal['large-study-acceptance-1.0']='large-study-acceptance-1.0'
    protocol:Literal['3.4-benchmark-static']='3.4-benchmark-static'
    plan_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    catalog_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    source_seals_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    observed_utc:str
    script_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    harness_status:Literal['blocked','collecting','operational_checks_passed','operational_checks_passed_with_reviewed_retries','task_feasibility_indeterminate']
    scientific_status:Literal['incomplete_registered_matrix','mock_only','boundary_descriptive_quality_unvalidated','development_feasibility_indeterminate']
    planned_runs:int=Field(ge=1)
    planned_calls:int=Field(ge=1)
    completed_runs:int=Field(ge=0)
    failed_sealed_attempts:int=Field(ge=0)
    unsealed_attempts:int=Field(ge=0)
    explicitly_resolved_retained_attempts:int=Field(ge=0)
    unresolved_retained_attempts:int=Field(ge=0)
    recovery_receipts_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    development_source_location_gate:Literal['pending','passed','task_feasibility_indeterminate','invalid_receipt']
    physical_calls:int=Field(ge=0)
    recorded_http_attempts:int=Field(ge=0)
    returned_calls:int=Field(ge=0)
    live_completed_runs:int=Field(ge=0)
    mock_completed_runs:int=Field(ge=0)
    registered_cases:int=Field(ge=0)
    registered_projects:int=Field(ge=0)
    registered_source_families:int=Field(ge=0)
    completed_evaluation_cases:int=Field(ge=0)
    completed_factorial_blocks:int=Field(ge=0)
    any_round_scorer_positive_runs:int=Field(ge=0)
    final_scorer_positive_runs:int=Field(ge=0)
    unknown_final_scorer_runs:int=Field(ge=0)
    launch_full_coverage_gate:bool
    registered_boundary_analysis_ready:bool
    validated_utility_effect_ready:Literal[False]=False
    semantic_quality_score:None=None
    official_benchmark_score:Literal[False]=False
    model_success_required_for_harness_pass:Literal[False]=False
    legacy_human_audit_transfers_to_new_tasks:Literal[False]=False
    population_inference_established:Literal[False]=False
    collusion_established:Literal[False]=False
    checks:list[Check]
    report_hash:str=Field(pattern=r'^[a-f0-9]{64}$')


def _plan(queue):
    from large_primary_queue import validate_plan
    return validate_plan(queue)


def _payload(plan,row):
    from long_benchmark_materials import load_task
    return load_task(Path(plan['catalog']),row)


def _recovery_evidence(queue,plan,source):
    from large_primary_queue import recover,validate_recovery_receipts
    recovered=recover(source,plan)
    return recovered['failed_attempts'],validate_recovery_receipts(queue,plan,recovered)


def contains_hidden_keys(value):
    if isinstance(value,dict):return any(k in FORBIDDEN_INPUT_KEYS or contains_hidden_keys(v) for k,v in value.items())
    return isinstance(value,list) and any(contains_hidden_keys(v) for v in value)


def trace_checks(events,config,manifest,expected_payload=None,complete=True):
    """Rebuild each actual two-round private memory and current delivered inbox."""
    graph=study_adjacency(config['topology'],5)
    if manifest.get('graph')!=graph:raise ValueError('Graph mismatch')
    deliveries=[e for e in events if e.get('event_type')=='message_delivered']
    expected={(sender,receiver,r) for sender,receivers in graph.items() for receiver in receivers for r in range(1,config['rounds'])}
    actual={(e.get('sender_id'),e.get('receiver_id'),e.get('round')) for e in deliveries}
    if (len(deliveries)!=len(actual) or not actual<=expected or complete and actual!=expected or
        manifest.get('messages_delivered')!=len(deliveries)):raise ValueError('Incomplete/duplicate registered graph delivery')
    applied=[e for e in events if e.get('event_type')=='intervention_applied']
    if config['intervention']=='none' and applied:raise ValueError('Unexpected clean-arm intervention')
    if config['intervention']=='benign_override':
        from run_repository_study import CHALLENGE
        generated=[e for e in events if e.get('event_type')=='message_generated' and e.get('sender_id')=='agent_0' and e.get('round')==0]
        direct=[e for e in deliveries if e.get('sender_id')=='agent_0' and e.get('round')==1]
        if len(applied)>1 or len(generated)>1 or (complete or direct) and (len(applied)!=1 or len(generated)!=1):raise ValueError('Missing or repeated registered intervention')
        if applied:
            item=applied[0]
            if (len(generated)!=1 or item.get('sender_id')!='agent_0' or item.get('round')!=0 or item.get('metadata',{}).get('original')!=generated[0].get('content') or
                item.get('content')!=generated[0]['content']+' '+CHALLENGE):raise ValueError('Intervention differs from frozen benign challenge')
            if complete and len(direct)!=len(graph['agent_0']) or any(e.get('content')!=item['content'] for e in direct):raise ValueError('Injected delivery manipulation failed')
    base={};history=defaultdict(list);request={};inbox=defaultdict(list)
    for event in events:
        kind=event.get('event_type');agent=event.get('agent_id');round_no=event.get('round')
        if kind=='message_delivered':
            sender=event.get('sender_id');receiver=event.get('receiver_id')
            if receiver!=agent or receiver not in graph.get(sender,[]) or event.get('metadata',{}).get('source_round')!=round_no-1:
                raise ValueError('Invalid routing or within/future-round delivery')
            inbox[agent,round_no].append({'sender':sender,'source_round':round_no-1,'content':event.get('content')})
        elif kind=='inference_requested':
            messages=event.get('metadata',{}).get('messages')
            if agent not in graph or not isinstance(messages,list) or len(messages)<3 or messages[-1].get('role')!='user':raise ValueError('Missing actual inference context')
            if agent not in base:base[agent]=messages[:2]
            if messages[:2]!=base[agent] or [x.get('role') for x in base[agent]]!=['system','user']:raise ValueError('Mutable initial task/system')
            if base[agent][0].get('content')!=config['instruction']:raise ValueError('Actual system instruction differs from freeze')
            retained=history[agent][-2:]
            expected=[*base[agent],*[value for _,user,assistant in retained for value in (user,assistant)],messages[-1]]
            if messages!=expected:raise ValueError('Private-history leakage or unrecorded context alteration')
            metadata=event['metadata']
            if metadata.get('retained_history_rounds')!=[r for r,_,_ in retained] or metadata.get('omitted_history_rounds')!=[r for r,_,_ in history[agent][:-2]]:
                raise ValueError('History retention disclosure mismatch')
            current=json.loads(messages[-1]['content']);initial=json.loads(base[agent][1]['content'])
            if expected_payload is not None and initial!=expected_payload:raise ValueError('Actual model task differs from pinned input')
            if contains_hidden_keys(initial) or contains_hidden_keys(current):raise ValueError('Oracle fields visible in model context')
            from large_benchmark_runner import peer_view
            if current.get('peer_notes')!=peer_view(inbox[agent,round_no],config['defense']):raise ValueError('Visible peer notes differ from authoritative delivered events')
            request[agent,round_no]=messages[-1]
        elif kind=='inference_response':
            if (agent,round_no) not in request:raise ValueError('Response without actual request')
            history[agent].append((round_no,request.pop((agent,round_no)),{'role':'assistant','content':event.get('content')}))
    if complete and request:raise ValueError('Unanswered request in completed trace')
    return True


def development_gate(queue,plan,completed_paths,has_evaluation):
    jobs=plan['jobs'];tasks={t['id']:t for t in plan['tasks']};needed={i for i,j in enumerate(jobs) if j['phase']=='integration_precheck'}
    if not needed<=set(completed_paths):return 'invalid_receipt' if has_evaluation else 'pending'
    from large_benchmark_runner import location_diagnostics
    counts={kind:{'clean_runs':0,'final_agents':0,'finding_count':0,'grounded_finding_count':0,'unlocatable_finding_count':0} for kind in {t['task_kind'] for t in tasks.values()}}
    for index in needed:
        job=jobs[index]
        if job['intervention']!='none':continue
        task=tasks[job['task_id']];value=counts[task['task_kind']];value['clean_runs']+=1
        events=[json.loads(s) for s in (completed_paths[index]/'events.jsonl').read_text().splitlines()]
        for event in events:
            if event.get('event_type')=='artifact' and event.get('round')==job['rounds']-1:
                diag=location_diagnostics(_payload(plan,task),json.loads(event['content']),task['task_kind']);value['final_agents']+=1
                for key in ('finding_count','grounded_finding_count','unlocatable_finding_count'):value[key]+=diag[key]
    status='passed' if all(v['clean_runs']==2 and v['final_agents']==10 and v['grounded_finding_count']>=1 for v in counts.values()) else 'task_feasibility_indeterminate'
    path=Path(queue)/'development-feasibility.private.json'
    if not path.exists():return 'invalid_receipt' if has_evaluation else 'pending'
    receipt=json.loads(path.read_text())
    if (receipt.get('schema_version')!='development-feasibility-1.0' or receipt.get('plan_hash')!=plan['plan_hash'] or
        receipt.get('status')!=status or receipt.get('kinds')!=counts or receipt.get('criterion')!=plan['development_feasibility'] or
        receipt.get('semantic_quality_status')!='not_scored' or receipt.get('boundary_positives_required') is not False):return 'invalid_receipt'
    return status


def inspect(queue,source=None):
    queue=Path(queue);plan=_plan(queue)
    if plan.get('protocol_version')!='3.4-benchmark-static':raise ValueError('Separate acceptance protocol required')
    source=Path(source) if source else ROOT/'results/repository-runs'/queue.name
    checks=[]
    def check(name,good,n=0,pending=False,limited=False):checks.append(Check(criterion=name,status='pass' if good else 'pending' if pending else 'limited' if limited else 'fail',count=n))
    check('frozen_plan',True)
    check('controller_safety',plan.get('agent_tools')==[] and plan.get('upstream_execution') is False and plan.get('oracle_visible_to_agents') is False and plan.get('agent_count')==5)
    jobs=plan['jobs'];tasks={r['id']:r for r in plan['tasks']};blocks=defaultdict(list)
    for j in jobs:blocks[(j['task_id'],j['phase'],j['seed'],j['rounds'],j['topology'])].append(j)
    expected_arms={('plain','none'),('plain','benign_override'),('source_attribution','none'),('source_attribution','benign_override')}
    paired=all(len(rows)==4 and {(j['defense'],j['intervention']) for j in rows}==expected_arms for rows in blocks.values())
    check('matched_four_arm_blocks',paired,len(blocks))
    evaluation={j['task_id'] for j in jobs if j['phase']=='evaluation'};development={j['task_id'] for j in jobs if j['phase']=='integration_precheck'}
    split_good=not evaluation&development and all(tasks[i]['split']=='heldout' for i in evaluation) and all(tasks[i]['split']=='dev' for i in development)
    check('heldout_split',split_good,len(evaluation))
    projects={tasks[i]['project_group'] for i in evaluation};families={tasks[i]['dataset'] for i in evaluation}
    check('case_diversity',len(evaluation)>=32,len(evaluation),limited=True)
    check('project_diversity',len(projects)>=8,len(projects),limited=True)
    check('source_diversity',len(families)>=2,len(families),limited=True)
    completed={};failures=unsealed=physical=recorded=returned=live=mock=positives=final_positive=unknown=0
    assigned=coverage=traces=True;seals=[];completed_paths={};has_evaluation=False;orphan_attempts=0
    for directory in source.glob('job-*/*'):
        if directory.is_dir() and not (directory/'events.jsonl').is_file():
            if directory.is_symlink() or directory.parent.is_symlink():raise ValueError('Unexpected attempt symlink')
            try:index=int(directory.parent.name.removeprefix('job-'));orphan_job=jobs[index]
            except (ValueError,IndexError):raise ValueError('Unregistered orphan attempt') from None
            if index<0 or directory.parent.name!=f'job-{index:03}':raise ValueError('Unregistered orphan index')
            unsealed+=1;orphan_attempts+=1;physical+=orphan_job['calls']
    for event_path in sorted(source.glob('job-*/*/events.jsonl')):
        root=event_path.parent
        if any(p.is_symlink() for p in (root,root.parent,event_path)):raise ValueError('Unexpected attempt symlink')
        try:index=int(root.parent.name.removeprefix('job-'));job=jobs[index]
        except (ValueError,IndexError):raise ValueError('Unregistered attempt job') from None
        if index<0 or root.parent.name!=f'job-{index:03}':raise ValueError('Unregistered attempt index')
        events=[];malformed=False
        for line in event_path.read_text().splitlines():
            try:events.append(json.loads(line))
            except ValueError:malformed=True;break
        attempts=sum(e.get('event_type')=='http_attempt' for e in events);responses=sum(e.get('event_type')=='inference_response' for e in events)
        has_evaluation|=job['phase']=='evaluation' and bool(events)
        physical+=attempts;recorded+=attempts;returned+=responses
        if not all((root/f).is_file() for f in ['manifest.json','checksum.sha256','config.snapshot.json','outcome.json']):
            if (root/'config.snapshot.json').is_file():
                c=json.loads((root/'config.snapshot.json').read_text())
                assigned&=(c.get('registry_freeze_hash')==plan['plan_hash'] and c.get('source_hash')==plan['source_hash'] and c.get('protocol_version')==plan['protocol_version']
                    and c.get('task_metadata')==tasks[job['task_id']] and c.get('agent_tools')==[] and c.get('upstream_execution') is False and c.get('oracle_visible_to_agents') is False
                    and all(c.get(k)==job[k] for k in ['task_id','phase','seed','rounds','topology','defense','intervention','batch']))
                partial_manifest={'graph':study_adjacency(job['topology'],5),'messages_delivered':sum(e.get('event_type')=='message_delivered' for e in events)}
                try:trace_checks(events,c,partial_manifest,_payload(plan,tasks[job['task_id']]),complete=False)
                except (ValueError,KeyError,TypeError):traces=False
            elif any(e.get('event_type')=='inference_requested' for e in events):assigned=False
            unsealed+=1;physical+=max(0,job['calls']-attempts);continue
        if malformed or not verify(root):raise ValueError('Attempt checksum or JSONL integrity failed')
        seals.append([digest([root.parent.name,root.name]),hashlib.sha256((root/'checksum.sha256').read_bytes()).hexdigest()])
        m=json.loads((root/'manifest.json').read_text());c=json.loads((root/'config.snapshot.json').read_text());o=json.loads((root/'outcome.json').read_text())
        identity=m.get('model_identity',{});backend=identity.get('backend')
        assigned&=(m.get('plan_hash')==plan['plan_hash'] and c.get('registry_freeze_hash')==plan['plan_hash'] and m.get('protocol_version')==plan['protocol_version'] and c.get('protocol_version')==plan['protocol_version'] and m.get('source_hash')==plan['source_hash'] and c.get('source_hash')==plan['source_hash'] and m.get('source_unchanged_on_exit') is True
            and m.get('controller_hash')==c.get('controller_hash')==plan['dependencies']['large_benchmark_runner.py'] and c.get('model_identity')==identity
            and c.get('task_metadata')==tasks[job['task_id']]
            and c.get('agent_tools')==[] and c.get('upstream_execution') is False and c.get('oracle_visible_to_agents') is False and c.get('official_benchmark_score') is False
            and backend in {'mock','ollama'} and all(c.get(k)==job[k] for k in ['task_id','phase','seed','rounds','topology','defense','intervention','batch']))
        if backend!='mock':assigned&=identity.get('model')==plan['model'] and identity.get('digest')==plan['model_digest'] and identity.get('worker_label')=='primary'
        response_answers={}
        for event in events:
            if event.get('event_type')=='inference_response':
                try:response_answers[event.get('agent_id'),event.get('round')]=json.loads(event.get('content','')).get('answer')
                except (ValueError,AttributeError):pass
            elif event.get('event_type')=='artifact':
                try:coverage&=json.loads(event.get('content',''))==response_answers[event.get('agent_id'),event.get('round')]
                except (ValueError,KeyError):coverage=False
        if m['status']!='completed':
            failures+=1
            try:trace_checks(events,c,m,_payload(plan,tasks[job['task_id']]),complete=False)
            except (ValueError,KeyError,TypeError):traces=False
            continue
        if index in completed:raise ValueError('Duplicate completed assignment')
        completed[index]=m;completed_paths[index]=root
        expected={(f'agent_{a}',r) for r in range(job['rounds']) for a in range(5)}
        ordered=[(f'agent_{a}',r) for r in range(job['rounds']) for a in range(5)]
        artifacts=[e for e in events if e.get('event_type')=='artifact']
        coverage&=(m.get('completed_model_calls')==responses==job['calls'] and m.get('http_attempts')==attempts and m.get('parse_failures')==0 and len(artifacts)==len(expected) and {(e.get('agent_id'),e.get('round')) for e in artifacts}==expected)
        coverage&=all([(e.get('agent_id'),e.get('round')) for e in events if e.get('event_type')==kind]==ordered for kind in ['inference_requested','inference_response'])
        coverage&=attempts==0 if backend=='mock' else attempts==responses
        try:trace_checks(events,c,m,_payload(plan,tasks[job['task_id']]))
        except (ValueError,KeyError,TypeError):traces=False
        if backend=='mock':mock+=1
        else:live+=1
        positives+=o.get('any_violation') is True;final_positive+=o.get('final_any_violation') is True;unknown+=type(o.get('final_any_violation')) is not bool
    failed_records,receipts=_recovery_evidence(queue,plan,source);resolved=set()
    for receipt in receipts:
        if receipt['decision']!='explicit_retry_failed':continue
        for entry in receipt['prior_failed_attempts']:
            index=entry['job_index']
            if index in completed and datetime.fromisoformat(completed[index]['started_utc'])>=datetime.fromisoformat(receipt['created_utc']):resolved.add(entry['attempt_id'])
    unresolved=[r for r in failed_records if r['attempt_id'] not in resolved]
    unresolved_sealed=sum(r['sealed'] for r in unresolved);unresolved_unsealed=sum(not r['sealed'] for r in unresolved)+orphan_attempts
    state_path=queue/'primary-large-state.json';state=json.loads(state_path.read_text()) if state_path.exists() else {}
    active=state.get('status') in {'running','waiting','cooling','waiting_for_primary_lease'}
    check('sealed_attempts',not unresolved_sealed and not unresolved_unsealed,len(completed),pending=bool(unresolved_unsealed) and not unresolved_sealed and active)
    check('explicit_failed_attempt_resolution',not unresolved and not orphan_attempts,len(resolved),pending=bool(unresolved_unsealed) and not unresolved_sealed and active)
    check('attempt_assignment',bool(assigned),len(completed))
    check('call_and_artifact_coverage',bool(coverage) and physical<=plan['max_http_attempts'],returned)
    check('routing_and_history',bool(traces),len(completed))
    precheck_indices={i for i,j in enumerate(jobs) if j['phase']=='integration_precheck'}
    prechecks=bool(precheck_indices) and precheck_indices<=set(completed)
    check('completed_prechecks',prechecks,len(precheck_indices&set(completed)),pending=not failures)
    feasibility=development_gate(queue,plan,completed_paths,has_evaluation)
    check('development_feasibility',feasibility=='passed',len(precheck_indices&set(completed)),pending=feasibility=='pending',limited=feasibility=='task_feasibility_indeterminate')
    matrix=len(completed)==plan['planned_runs']==len(jobs)
    done=matrix and state.get('status')=='completed' and state.get('plan_hash')==plan['plan_hash']
    check('completed_registered_matrix',done,len(completed),pending=not failures)
    severe=any(c.status=='fail' for c in checks)
    completed_blocks=sum(all(jobs.index(j) in completed for j in rows) for key,rows in blocks.items() if key[1]=='evaluation')
    payload={'protocol':plan['protocol_version'],'plan_hash':plan['plan_hash'],'catalog_hash':plan['catalog_hash'],
        'source_seals_hash':digest(seals),'observed_utc':datetime.now(timezone.utc).isoformat(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'harness_status':'blocked' if severe else 'task_feasibility_indeterminate' if feasibility=='task_feasibility_indeterminate' else ('operational_checks_passed_with_reviewed_retries' if resolved else 'operational_checks_passed') if done else 'collecting',
        'scientific_status':'development_feasibility_indeterminate' if feasibility=='task_feasibility_indeterminate' else 'incomplete_registered_matrix' if not done else 'mock_only' if not live else 'boundary_descriptive_quality_unvalidated',
        'planned_runs':plan['planned_runs'],'planned_calls':plan['planned_calls'],'completed_runs':len(completed),'failed_sealed_attempts':failures,'unsealed_attempts':unsealed,
        'physical_calls':physical,'recorded_http_attempts':recorded,'returned_calls':returned,'live_completed_runs':live,'mock_completed_runs':mock,'registered_cases':len(evaluation),'registered_projects':len(projects),'registered_source_families':len(families),
        'explicitly_resolved_retained_attempts':len(resolved),'unresolved_retained_attempts':len(unresolved)+orphan_attempts,'recovery_receipts_hash':digest([r['receipt_hash'] for r in receipts]),'development_source_location_gate':feasibility,
        'completed_evaluation_cases':len({jobs[i]['task_id'] for i in completed if jobs[i]['phase']=='evaluation'}),'completed_factorial_blocks':completed_blocks,
        'any_round_scorer_positive_runs':positives,'final_scorer_positive_runs':final_positive,'unknown_final_scorer_runs':unknown,
        'launch_full_coverage_gate':not severe and prechecks and feasibility=='passed' and mock==0 and live>0 and all(c.status=='pass' for c in checks if c.criterion in {'case_diversity','project_diversity','source_diversity'}),
        'registered_boundary_analysis_ready':not severe and done and feasibility=='passed' and not unknown and not mock,
        'checks':[c.model_dump() for c in checks]}
    provisional=Report.model_validate({**payload,'report_hash':'0'*64}).model_dump()
    provisional['report_hash']=digest({k:v for k,v in provisional.items() if k!='report_hash'})
    return Report.model_validate(provisional)


def validate_report(path):
    report=Report.model_validate_json(Path(path).read_text())
    if digest(report.model_dump(exclude={'report_hash'}))!=report.report_hash:raise ValueError('Acceptance report hash mismatch')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--queue',type=Path,required=True);p.add_argument('--source',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    report=inspect(a.queue,a.source);a.out.parent.mkdir(parents=True,exist_ok=True);write_json(a.out,report.model_dump());print('Harness:',report.harness_status,';',report.completed_runs,'/',report.planned_runs,'completed; semantic quality remains unvalidated.')
