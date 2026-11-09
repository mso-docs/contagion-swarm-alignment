"""Closed protocol4 summary export and loopback-only bounded trace inspection."""
import json
from pathlib import Path
from typing import Literal
from pydantic import Field,model_validator

from contagion.config import digest
from contagion.events import read_events,utc
from contagion.publication import Redactor,sensitive_values
from contagion.research_publication import Closed,StudyRow,StudyAgent
from advisory_publication import AdvisoryRow,summaries
from contagion.storage import verify
from large_benchmark_monitor import Cell as BenchmarkMonitorCell
from large_benchmark_monitor_v37 import Cell as BenchmarkOutputMonitorCell
from multidomain_publication import MultidomainRun,summaries as multidomain_summaries
from multidomain_publication_v51 import MultidomainRun as MultidomainCoverageRun,summaries as coverage_summaries
from diversity_publication import DiversityRun,summaries as diversity_summaries


class BenchmarkMonitorSummary(BenchmarkMonitorCell):
    analysis_scope:Literal['completed_registered_batches_descriptive','completed_registered_matrix']
    cutoff_utc:str|None=None
    report_hash:str=Field(pattern=r'^[a-f0-9]{64}$')


class BenchmarkOutputMonitorSummary(BenchmarkOutputMonitorCell):
    analysis_scope:Literal['completed_registered_batches_descriptive','completed_registered_matrix']
    cutoff_utc:str|None=None
    report_hash:str=Field(pattern=r'^[a-f0-9]{64}$')


class FollowupRun(StudyRow):
    protocol:Literal['4.0-confirmatory']='4.0-confirmatory'
    source_kind:Literal['confirmatory']='confirmatory'
    source_agent:Literal['agent_0','agent_1']
    context_policy:Literal['not_applicable','matched_reset','natural_history']
    detail_file:None=None
    id:str=Field(pattern=r'^[a-f0-9]{16}$')


class DecompositionRun(StudyRow):
    protocol:Literal['4.1-decomposition']='4.1-decomposition'
    source_kind:Literal['confirmatory']='confirmatory'
    source_agent:None=None
    arm:Literal['direct_full','serial_split','team_split','identity_reset']
    phase:Literal['calibration','matched_split','negative_control']
    context_policy:Literal['direct_full_calibration','serial_history','isolated_components','identity_reset']
    planned_calls:int=Field(ge=1,le=5)
    explicit_refusal_count:int=Field(ge=0,le=5)
    explicit_decline_count:int=Field(ge=0,le=5)
    direct_full_explicit_decline:bool|None=None
    refusal_bypass_established:Literal[False]=False
    human_verification_required:Literal[True]=True
    detail_file:None=None
    id:str=Field(pattern=r'^[a-f0-9]{16}$')


class MonitorSummary(Closed):
    endpoint:Literal['final_downstream_adoption','any_round_downstream_deviation']
    method:Literal['keyword_rule','artifact_parser']
    monitor_seed:int=Field(ge=0)
    visibility:float=Field(ge=0,le=1)
    policy:Literal['communications_only','communications_and_final_outputs','communications_and_intermediate_outputs']
    cohort:str=Field(pattern=r'^[a-f0-9]{64}$')
    protocol:Literal['4.0-confirmatory']
    backend:Literal['mock','ollama','openai']
    model:str=Field(max_length=160)
    model_digest:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    worker:Literal['primary','secondary','local','unspecified']
    source_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    freeze_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    design_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    topology:Literal['ring','star','complete']
    source_agent:Literal['agent_0','agent_1']
    defense:Literal['none','plain','source_attribution','not_applicable']
    n:int=Field(ge=0)
    tp:int=Field(ge=0)
    fp:int=Field(ge=0)
    tn:int=Field(ge=0)
    fn:int=Field(ge=0)
    precision:float|None=Field(ge=0,le=1)
    recall:float|None=Field(ge=0,le=1)
    f1:float|None=Field(ge=0,le=1)
    false_positive_rate:float|None=Field(ge=0,le=1)
    projected_runs:int=Field(ge=0)
    unknown_truth_runs:int=Field(ge=0)
    positive_runs:int=Field(ge=0)
    negative_runs:int=Field(ge=0)
    case_seed_blocks:int=Field(ge=0)

    @model_validator(mode='after')
    def denominators(self):
        if self.tp+self.fp+self.tn+self.fn!=self.n or self.tp+self.fn!=self.positive_runs or self.fp+self.tn!=self.negative_runs or self.n+self.unknown_truth_runs!=self.projected_runs:raise ValueError('Monitor denominator mismatch')
        if not self.positive_runs and self.recall is not None:raise ValueError('Recall must remain undefined without positives')
        return self


class Snapshot(Closed):
    schema_version:Literal['confirmatory-public-1.0']='confirmatory-public-1.0'
    generated_utc:str
    runs:list[FollowupRun|DecompositionRun]
    monitor:list[MonitorSummary|BenchmarkMonitorSummary|BenchmarkOutputMonitorSummary]=Field(default_factory=list,max_length=4096)
    reviews:list[AdvisoryRow]=Field(default_factory=list,max_length=10000)
    multidomain:list[MultidomainRun|MultidomainCoverageRun]=Field(default_factory=list,max_length=10000)
    diversity:list[DiversityRun]=Field(default_factory=list,max_length=10000)
    text_included:Literal[False]=False


def paths(source):return sorted(Path(source).glob('*/rq*/run-*/manifest.json'))


def identifier(root):return digest(str(Path(root).resolve()))[:16]


def export(source,output,env):
    redact=Redactor(sensitive_values(env));rows=[]
    for path in paths(source):
        root=path.parent
        if not (root/'checksum.sha256').is_file():continue
        if not verify(root):raise ValueError('Follow-up integrity failure')
        m=json.loads(path.read_text());config=json.loads((root/'config.snapshot.json').read_text());o=json.loads((root/'outcome.json').read_text());j=config['job'];identity=m['model_identity'];events=read_events(root/'events.jsonl')
        completed=m['status']=='completed';final=o.get('final_agents',[])
        if m.get('protocol_version')=='4.1-decomposition':
            arm=j['arm'];phase='calibration' if arm=='direct_full' else 'negative_control' if arm=='identity_reset' else 'matched_split'
            policy={'direct_full':'direct_full_calibration','serial_split':'serial_history','team_split':'isolated_components','identity_reset':'identity_reset'}[arm]
            rows.append(DecompositionRun(id=identifier(root),model=redact(identity.get('model') or 'unspecified'),backend=identity['backend'],
                worker_label=identity.get('worker_label','local'),model_digest=identity.get('digest'),arm=arm,phase=phase,context_policy=policy,planned_calls=j['calls'],
                freeze_hash=m['plan_hash'],split='evaluation',task_family='record',case_id=config['case']['case_id'],seed=j['seed'],
                topology='star' if arm=='team_split' else 'single',intervention=j['intervention'],status=m['status'],calls=m['completed_model_calls'],runtime=m['duration_seconds'],
                violation=o['any_violation'],violation_status='observed' if o['any_violation'] else 'not_observed' if completed else 'indeterminate',
                parse_failures=m['parse_failures'],task_success_rate=o['task_success_rate'] if completed else None,
                attempted_forbidden=o['attempted_forbidden'],state_violation=o['actual_state_violation'],executor=j['executor'],
                explicit_refusal_count=o['explicit_refusal_count'],explicit_decline_count=o['explicit_decline_count'],direct_full_explicit_decline=o['direct_full_explicit_decline'],
                agents=[StudyAgent(agent_id=a['agent_id'],task_success=a['task_success'],violation=a['violation'],behavior=a['behavior'],messages_received=sum(e['event_type']=='message_delivered' and e.get('receiver_id')==a['agent_id'] for e in events)) for a in final],
                started_utc=m['started_utc'],source_hash=m['source_hash'],http_attempts=m['http_attempts'],rounds=j['calls'],agent_count=5 if arm=='team_split' else 1,
                thinking='disabled',temperature=.2,max_output_tokens=1024,messages_delivered=sum(e['event_type']=='message_delivered' for e in events)))
            continue
        rows.append(FollowupRun(id=identifier(root),model=redact(identity.get('model') or 'unspecified'),backend=identity['backend'],
            worker_label=identity.get('worker_label','local'),model_digest=identity.get('digest'),source_agent=j['source'],context_policy=j.get('context','not_applicable'),
            freeze_hash=m['freeze_hash'],split='development' if config.get('phase')=='integration_precheck' else 'evaluation',task_family=j['family'],case_id=config['case']['case_id'],seed=j['seed'],topology=j['topology'],intervention=j['condition'],
            status=m['status'],calls=m['completed_model_calls'],runtime=m['duration_seconds'],violation=o['any_round_violation'],
            violation_status='observed' if o['any_round_violation'] else 'not_observed' if completed else 'indeterminate',
            parse_failures=sum(e['event_type']=='parse_failure' for e in events),task_success_rate=o['task_success_rate'] if completed else None,
            attempted_forbidden=o['attempted_forbidden'],state_violation=o['actual_state_violation'],executor=j['executor'],
            agents=[StudyAgent(agent_id=a['agent_id'],task_success=a['task_success'],violation=a['violation'],behavior=a['behavior'],messages_received=sum(e['event_type']=='message_delivered' and e.get('receiver_id')==a['agent_id'] for e in events)) for a in final],
            started_utc=m['started_utc'],source_hash=m['source_hash'],http_attempts=m['http_attempts'],rounds=5,
            agent_count=1 if j['topology']=='single' else 5,thinking='disabled',temperature=.2,max_output_tokens=1024,
            messages_delivered=sum(e['event_type']=='message_delivered' for e in events),downstream_adoption_rate=o['final_downstream_violation_rate'] if completed and j['family']=='patch' else None))
    monitors=[]
    for path in sorted((Path(source).parent/'monitors').glob('*/monitor.private.json')):
        raw=json.loads(path.read_text())
        if raw.get('schema_version')!='4.0-patch-monitor-1.0':continue
        if raw.get('status')!='completed_registered_batch':raise ValueError('Incomplete monitor export')
        for row in raw['summary']:
            monitors.append(MonitorSummary(**{**row,'model':redact(row['model'])}))
    from large_benchmark_monitor import validate_report
    from large_benchmark_monitor_v37 import validate_report as validate_output_report
    latest={}
    for path in sorted((Path(source).parent/'reports').glob('*/batch-*/monitor/public.json')):
        schema=json.loads(path.read_text()).get('schema_version')
        report=(validate_output_report(path) if schema=='3.7-static-marker-monitor-1.0' else validate_report(path))
        key=(report.source_plan_hash,report.backend)
        order=(report.analysis_scope=='completed_registered_matrix',report.cutoff_utc or '',path.stat().st_mtime_ns)
        if key not in latest or order>latest[key][0]:latest[key]=(order,report)
    for _,report in latest.values():
        for cell in report.summary:
            model=BenchmarkOutputMonitorSummary if cell.protocol=='3.7-benchmark-output-budget' else BenchmarkMonitorSummary
            monitors.append(model(**{**cell.model_dump(),'model':redact(cell.model)},
                analysis_scope=report.analysis_scope,cutoff_utc=report.cutoff_utc,report_hash=report.report_hash))
    snapshot=Snapshot(generated_utc=utc(),runs=rows,monitor=monitors,reviews=summaries(Path(source).parent/'reviews',env),multidomain=multidomain_summaries(source,env)+coverage_summaries(source,env),diversity=diversity_summaries(source,env));output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.tmp');temporary.write_text(snapshot.model_dump_json(indent=2)+'\n');validate(temporary,env);temporary.replace(output);return snapshot


def validate(path,env=None):
    from scan_privacy import scan_blob
    data=Snapshot.model_validate_json(Path(path).read_text());known=sensitive_values(env or {})
    if scan_blob(Path(path).read_bytes(),public=True,known=known):raise ValueError('Follow-up privacy check')
    redact=Redactor(known)
    if any(redact(r.model)!=r.model for r in [*data.runs,*data.monitor,*data.multidomain,*data.diversity]):raise ValueError('Private model label')
    return data


def private_detail(source,ident,env):
    redact=Redactor(sensitive_values(env))
    for path in paths(source):
        root=path.parent
        if identifier(root)!=ident:continue
        if not verify(root):raise ValueError('Unsealed follow-up')
        m=json.loads(path.read_text());config=json.loads((root/'config.snapshot.json').read_text());events=read_events(root/'events.jsonl')
        eligible=[e for e in events if e['event_type'] in {'artifact','message_delivered','inference_response'}];selected=eligible[-128:]
        traces=[{k:(redact(v[:2000]) if k=='content' else v) for k,v in e.items() if k in {'event_id','round','event_type','agent_id','sender_id','receiver_id','content'}} for e in selected]
        return {'schema_version':'1.0','id':ident,'graph':m['graph'],'traces':traces,'text_included':True,'eligible_events':len(eligible),'omitted_events':len(eligible)-len(selected),
                'task_instruction':redact(config['case']['instruction']),'task_input':redact(json.dumps(config['case']['payload']))}
    raise ValueError('Unknown follow-up')
