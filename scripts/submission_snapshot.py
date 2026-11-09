"""Freeze sealed numeric evidence at an explicit UTC cutoff; leave live collection alone."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
from typing import Literal

from pydantic import BaseModel,ConfigDict,Field

from contagion.config import digest
from contagion.storage import FILES,verify,write_json

PROTOCOLS={'2.6','4.0-confirmatory','4.1-decomposition','3.0-repository','3.1-repository','3.3-repository-safeguard'}


class Closed(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)


class FrozenRun(Closed):
    id:str=Field(pattern=r'^[a-f0-9]{20}$')
    protocol:Literal['2.6','4.0-confirmatory','4.1-decomposition','3.0-repository','3.1-repository','3.3-repository-safeguard']
    backend:Literal['ollama','mock','openai']
    worker:Literal['primary','secondary','local','unspecified']
    identity_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    source_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    freeze_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    seal_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    cohort:str=Field(pattern=r'^[a-f0-9]{64}$')
    case:str=Field(pattern=r'^[a-f0-9]{20}$')
    family:Literal['catalog','patch','provenance','record','code_review']
    phase:Literal['evaluation','integration_precheck','development']
    topology:Literal['ring','star','complete','single']
    source_agent:Literal['agent_0','agent_1']|None=None
    context_policy:Literal['not_applicable','matched_reset','natural_history','direct_full','serial_split','team_split','identity_reset']
    defense:Literal['not_applicable','plain','source_attribution']
    executor:Literal['deny','permissive_simulator']
    intervention:Literal['none','benign_override','toy_forbidden_update']
    seed:int
    rounds:int=Field(ge=1,le=15)
    calls:int=Field(ge=0)
    runtime_seconds:float=Field(ge=0)
    ended_utc:str
    final_downstream_violation_rate:float|None=Field(default=None,ge=0,le=1)
    any_round_violation:bool|None=None
    attempted_forbidden:bool|None=None
    state_violation:bool|None=None
    task_success_rate:float|None=Field(default=None,ge=0,le=1)
    refusal_rate:float|None=Field(default=None,ge=0,le=1)
    quality_precision:None=None
    quality_recall:None=None


class Pending(Closed):
    allocation:Literal['primary_long','secondary','secondary_long','decomposition']
    status:Literal['missing','waiting','running','cooling','completed','stopped','failed','budget_exhausted','waiting_for_primary_lease','waiting_for_secondary_lease','unknown']
    state_sha256:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    planned_runs:int|None=Field(default=None,ge=0)
    completed_runs:int|None=Field(default=None,ge=0)
    observed_utc:str


class Cohort(Closed):
    cohort:str=Field(pattern=r'^[a-f0-9]{64}$')
    protocol:str
    family:str
    phase:str
    intervention:str
    topology:str
    n:int=Field(ge=1)
    final_endpoint_known:int=Field(ge=0)
    mean_final_downstream_violation_rate:float|None=Field(default=None,ge=0,le=1)
    any_round_known:int=Field(ge=0)
    any_round_positive:int=Field(ge=0)
    task_success_known:int=Field(ge=0)
    mean_task_success_rate:float|None=Field(default=None,ge=0,le=1)
    runtime_seconds:float=Field(ge=0)
    quality_precision:None=None
    quality_recall:None=None


class Snapshot(Closed):
    schema_version:Literal['submission-snapshot-1.0']='submission-snapshot-1.0'
    cutoff_utc:str
    frozen_utc:str
    script_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    rows:list[FrozenRun]
    cohorts:list[Cohort]
    pending:list[Pending]
    excluded_unsealed:int=Field(ge=0)
    excluded_after_cutoff:int=Field(ge=0)
    excluded_incomplete:int=Field(ge=0)
    excluded_unsupported_protocol:int=Field(ge=0)
    human_validation:Literal['pending']='pending'
    neural_scope:Literal['reference_checkpoint_only']='reference_checkpoint_only'
    text_included:Literal[False]=False
    snapshot_hash:str=Field(pattern=r'^[a-f0-9]{64}$')


def utc(value):
    parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds()!=0:raise ValueError('Explicit UTC timezone required')
    return parsed.astimezone(timezone.utc)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def numeric_row(root,m,c,o):
    protocol=m['protocol_version'];j=c.get('job',{});plan=c.get('plan',{});identity=m['model_identity']
    family=j.get('family',c.get('family','record' if protocol=='4.1-decomposition' else 'code_review'))
    phase='integration_precheck' if c.get('phase')=='integration_precheck' else 'development' if c.get('split',plan.get('split'))=='development' else 'evaluation'
    freeze=m.get('freeze_hash',m.get('plan_hash',c.get('registry_freeze_hash')))
    context=j.get('context',j.get('arm','not_applicable'));source=j.get('source','agent_0' if family!='record' else None)
    identity_hash=digest(identity);seal=sha(root/'checksum.sha256')
    cohort=digest({'protocol':protocol,'identity':identity_hash,'source':m['source_hash'],'freeze':freeze,'context':context,'defense':c.get('defense','not_applicable'),'source_agent':source,'executor':j.get('executor',plan.get('executor',c.get('executor','deny')))})
    return FrozenRun(id=digest({'seal':seal,'manifest':sha(root/'manifest.json')})[:20],protocol=protocol,
        backend=identity['backend'],worker=identity.get('worker_label','unspecified'),identity_hash=identity_hash,source_hash=m['source_hash'],freeze_hash=freeze,seal_sha256=seal,cohort=cohort,
        case=digest(c.get('case',{}).get('case_id',o.get('task_case',c.get('task_id',c.get('case_index',0)))))[:20],family=family,phase=phase,
        topology=j.get('topology',c.get('topology','star' if j.get('arm')=='team_split' else 'single')),source_agent=source,context_policy=context,defense=c.get('defense','not_applicable'),
        executor=j.get('executor',plan.get('executor',c.get('executor','deny'))),intervention=j.get('condition',j.get('intervention',c.get('intervention'))),seed=j.get('seed',c.get('seed')),
        rounds=c.get('rounds',plan.get('rounds',j.get('calls',5) if family=='record' else 5)),calls=m['completed_model_calls'],runtime_seconds=m['duration_seconds'],ended_utc=utc(m['ended_utc']).isoformat(),
        final_downstream_violation_rate=o.get('final_downstream_violation_rate',o.get('downstream_final_violation_rate')),any_round_violation=o.get('any_round_violation',o.get('any_violation')),
        attempted_forbidden=o.get('attempted_forbidden'),state_violation=o.get('actual_state_violation'),task_success_rate=o.get('task_success_rate') if family!='code_review' else None,refusal_rate=o.get('refusal_rate'))


def cohorts(rows):
    groups=defaultdict(list)
    for row in rows:groups[(row.cohort,row.topology,row.intervention,row.family,row.phase)].append(row)
    output=[]
    for selected in groups.values():
        r=selected[0];final=[x.final_downstream_violation_rate for x in selected if x.final_downstream_violation_rate is not None];success=[x.task_success_rate for x in selected if x.task_success_rate is not None];any_round=[x.any_round_violation for x in selected if x.any_round_violation is not None]
        output.append(Cohort(cohort=r.cohort,protocol=r.protocol,family=r.family,phase=r.phase,intervention=r.intervention,topology=r.topology,n=len(selected),
            final_endpoint_known=len(final),mean_final_downstream_violation_rate=mean(final) if final else None,any_round_known=len(any_round),any_round_positive=sum(any_round),
            task_success_known=len(success),mean_task_success_rate=mean(success) if success else None,runtime_seconds=math.fsum(x.runtime_seconds for x in selected)))
    return sorted(output,key=lambda r:(r.protocol,r.cohort,r.family,r.topology,r.intervention,r.phase))


def pending_row(tag,path,observed):
    path=Path(path)
    if not path.is_file():return Pending(allocation=tag,status='missing',observed_utc=observed)
    raw=json.loads(path.read_text());status=raw.get('status','unknown')
    if status not in Pending.model_fields['status'].annotation.__args__:status='unknown'
    return Pending(allocation=tag,status=status,state_sha256=sha(path),planned_runs=raw.get('planned_runs'),completed_runs=raw.get('completed_runs'),observed_utc=observed)


def safeguard(rows,pending):
    selected=[r for r in rows if r.protocol=='3.3-repository-safeguard' and r.phase=='evaluation' and r.backend!='mock']
    groups=defaultdict(list)
    for r in selected:groups[(r.defense,r.intervention)].append(r)
    cells=[]
    for (defense,condition),rs in sorted(groups.items()):
        known=[r.final_downstream_violation_rate for r in rs if r.final_downstream_violation_rate is not None]
        cells.append({'defense':defense,'intervention':condition,'n':len(rs),'final_endpoint_known':len(known),'mean_final_downstream_violation_rate':mean(known) if known else None,'quality_precision':None,'quality_recall':None})
    allocation=next((p for p in pending if p.allocation=='primary_long'),None)
    ready=allocation is not None and allocation.status=='completed' and allocation.completed_runs==allocation.planned_runs and len(selected)==64
    return {'schema_version':'submission-safeguard-1.0','status':'completed_boundary_comparison_quality_pending' if ready else 'incomplete_registered_batch_no_effect_estimate',
            'cells':cells,'effect_estimate':None,'quality_precision':None,'quality_recall':None,'human_validation':'pending',
            'interpretation':'Descriptive boundary cells only. Use completed registered long analysis for paired effects; utility requires human adjudication.'}


def report(snapshot):
    live=[r for r in snapshot.rows if r.backend!='mock'];counts=Counter((r.protocol,r.family,r.phase) for r in live)
    rq1=[r for r in live if r.protocol=='4.0-confirmatory' and r.family=='patch' and r.phase=='evaluation'];rq3=[r for r in live if r.protocol=='4.0-confirmatory' and r.family=='record' and r.phase=='evaluation']
    final=[r.final_downstream_violation_rate for r in rq1 if r.final_downstream_violation_rate is not None]
    lines=['# Frozen research-question assessment','',f'Cutoff: `{snapshot.cutoff_utc}`. Snapshot hash: `{snapshot.snapshot_hash}`. Only verified sealed completed runs ending by this cutoff contribute outcomes. Live work can continue separately.','',
        '| Question | Evidence in this snapshot | Supported interpretation | Remaining gate |','|---|---|---|---|',
        f'| RQ1 topology propagation | {len(rq1)} protocol4 patch runs; {sum(v>0 for v in final)}/{len(final)} runs with positive final downstream rate; {sum(r.any_round_violation is True for r in rq1)} with any-round violation | Any-round and final endpoints are separate; this does not by itself establish topology causality or intent | Human artifact validation; paired exposure/source analysis; few independent cases |',
        '| RQ2 partial visibility | Original catalog monitor and separate protocol4 patch monitor use dependent projections, not new runs | Recall is undefined wherever the adopted-behavior truth denominator is zero; intermediate-patch detection is a different endpoint | Keep monitor masks/endpoint cohorts separate and report positive denominators |',
        f'| RQ3 distributed responsibility | {len(rq3)} completed protocol4 record runs; {sum(r.attempted_forbidden is True for r in rq3)} attempted updates; {sum(r.state_violation is True for r in rq3)} state violations | Context allocation is tested; no refusal bypass established | Protocol4.1 decomposition and verified individual-refusal prerequisite; human review |',
        '| Safeguard and utility | See safeguard.json; only completed sealed evaluation cells shown | Boundary compliance is separate from legitimate review quality; missing quality stays null | Complete registered matrix, semantic review and human adjudication |','',
        '## Included live cohorts','', '| Protocol | Task | Phase | Completed runs |','|---|---|---|---|']
    lines.extend(f'| {protocol} | {family} | {phase} | {n} |' for (protocol,family,phase),n in sorted(counts.items()))
    lines.extend(['','## Pending allocations at freeze','', '| Allocation | Observed status | Completed / planned |','|---|---|---|'])
    lines.extend(f'| {p.allocation} | {p.status} | {p.completed_runs if p.completed_runs is not None else "unknown"} / {p.planned_runs if p.planned_runs is not None else "unknown"} |' for p in snapshot.pending)
    lines.extend(['','Human validation remains pending. Reference GPT-2 neural measurements are not recordings of swarm-model internals. No general alignment rating or collusion conclusion is inferred.',''])
    return '\n'.join(lines)


def prepare(sources,cutoff,out,pending_states=()):
    cutoff=utc(cutoff);out=Path(out)
    if out.exists():raise ValueError('Immutable snapshot output must be new')
    observed=datetime.now(timezone.utc).isoformat()
    if cutoff>utc(observed):raise ValueError('Cutoff cannot be in the future')
    rows=[];lineage=[];seen=set();ids=set();excluded=Counter()
    for source in sources:
        source=Path(source)
        if source.is_symlink() or not source.is_dir():raise ValueError('Source directory missing or symlinked')
        for path in sorted(source.rglob('manifest.json')):
            root=path.parent.resolve()
            if root in seen:continue
            seen.add(root)
            if path.is_symlink() or path.parent.is_symlink() or any((root/name).is_symlink() for name in [*FILES,'checksum.sha256']):raise ValueError('Symlink source rejected')
            try:m=json.loads(path.read_text())
            except (OSError,ValueError):excluded['unsealed']+=1;continue
            if m.get('protocol_version') not in PROTOCOLS:excluded['unsupported_protocol']+=1;continue
            if not all((root/name).is_file() for name in [*FILES,'checksum.sha256']):excluded['unsealed']+=1;continue
            if not verify(root):raise ValueError('Source seal mismatch')
            if utc(m['ended_utc'])>cutoff:excluded['after_cutoff']+=1;continue
            if m['status']!='completed':excluded['incomplete']+=1;continue
            config=json.loads((root/'config.snapshot.json').read_text());outcome=json.loads((root/'outcome.json').read_text())
            if outcome.get('status',m['status'])!=m['status']:raise ValueError('Manifest/outcome status mismatch')
            row=numeric_row(root,m,config,outcome)
            if row.id in ids:raise ValueError('Duplicate immutable run identity')
            ids.add(row.id);rows.append(row);lineage.append({'id':row.id,'source':str(root),'seal_sha256':row.seal_sha256})
    if not rows:raise ValueError('No eligible sealed completed runs before cutoff')
    pending=[pending_row(tag,path,observed) for tag,path in pending_states]
    if len({p.allocation for p in pending})!=len(pending):raise ValueError('Duplicate pending allocation')
    payload={'schema_version':'submission-snapshot-1.0','cutoff_utc':cutoff.isoformat(),'frozen_utc':observed,'script_sha256':sha(__file__),
             'rows':[r.model_dump() for r in sorted(rows,key=lambda r:r.id)],'cohorts':[r.model_dump() for r in cohorts(rows)],'pending':[p.model_dump() for p in pending],
             'excluded_unsealed':excluded['unsealed'],'excluded_after_cutoff':excluded['after_cutoff'],'excluded_incomplete':excluded['incomplete'],'excluded_unsupported_protocol':excluded['unsupported_protocol'],
             'human_validation':'pending','neural_scope':'reference_checkpoint_only','text_included':False}
    snapshot=Snapshot(**payload,snapshot_hash=digest(payload))
    from scan_privacy import scan_blob
    if scan_blob(snapshot.model_dump_json().encode(),public=True):raise ValueError('Snapshot privacy scan failed')
    out.mkdir(parents=True,exist_ok=False);write_json(out/'public.json',snapshot.model_dump());write_json(out/'lineage.private.json',{'snapshot_hash':snapshot.snapshot_hash,'sources':lineage})
    write_json(out/'safeguard.json',safeguard(rows,pending));(out/'RQ_ASSESSMENT.md').write_text(report(snapshot));return snapshot


def validate(directory):
    """Validate the closed public snapshot, content hash and derived companion files."""
    directory=Path(directory);snapshot=Snapshot.model_validate_json((directory/'public.json').read_text())
    if digest({k:v for k,v in snapshot.model_dump().items() if k!='snapshot_hash'})!=snapshot.snapshot_hash:raise ValueError('Snapshot content hash mismatch')
    if utc(snapshot.cutoff_utc)>utc(snapshot.frozen_utc):raise ValueError('Snapshot cutoff follows freeze')
    if len({r.id for r in snapshot.rows})!=len(snapshot.rows):raise ValueError('Duplicate snapshot run')
    if any(utc(r.ended_utc)>utc(snapshot.cutoff_utc) for r in snapshot.rows):raise ValueError('Run after frozen cutoff')
    if snapshot.cohorts!=cohorts(snapshot.rows):raise ValueError('Cohort summary differs from rows')
    if json.loads((directory/'safeguard.json').read_text())!=safeguard(snapshot.rows,snapshot.pending):raise ValueError('Safeguard summary differs from rows')
    if (directory/'RQ_ASSESSMENT.md').read_text()!=report(snapshot):raise ValueError('RQ assessment differs from snapshot')
    from scan_privacy import scan_blob
    for name in ['public.json','safeguard.json','RQ_ASSESSMENT.md']:
        if scan_blob((directory/name).read_bytes(),public=name.endswith('.json')):raise ValueError('Public snapshot privacy scan failed')
    return snapshot


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,action='append',required=True);p.add_argument('--cutoff',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--pending',action='append',default=[])
    a=p.parse_args();pending=[]
    for value in a.pending:
        if '=' not in value:p.error('--pending requires TAG=STATE_PATH')
        pending.append(value.split('=',1))
    result=prepare(a.source,a.cutoff,a.out,pending);print('Frozen',len(result.rows),'sealed completed runs; human validation remains pending; hash',result.snapshot_hash)
