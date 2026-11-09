"""Validate complete registered coverage without hiding interrupted attempts."""
import itertools
import json
from pathlib import Path

from contagion.config import digest
from contagion.storage import verify
from contagion.studies import StudyPlan


def compact_evidence(campaign):
    expected=set()
    for job in campaign['jobs']:
        plan=StudyPlan(**job['plan']).model_dump()
        for family,index,seed,topology,intervention in itertools.product(plan['families'],plan['case_indices'],plan['seeds'],plan['topologies'],plan['interventions']):
            expected.add(digest({'protocol_version':plan['protocol_version'],'plan':plan,'family':family,'case_index':index,'seed':seed,'topology':topology,'intervention':intervention}))
    completed={};interruptions=[];evidence=[]
    root=Path(campaign['run_root'])
    for config in root.rglob('config.snapshot.json'):
        directory=config.parent
        if not verify(directory):raise ValueError('Compact evidence corrupted or unsealed')
        manifest=json.loads((directory/'manifest.json').read_text());key=digest(json.loads(config.read_text()))
        if key not in expected or manifest['source_hash']!=campaign['source_hash'] or manifest['parse_failures']:
            raise ValueError('Unexpected or invalid compact evidence')
        if manifest['status']=='completed':
            if key in completed:raise ValueError('Ambiguous duplicate complete condition')
            completed[key]=manifest
        elif manifest['status']=='budget_exhausted' and manifest.get('failures')==['inference_budget']:
            interruptions.append({'run_id':manifest['run_id'],'config_hash':key,'status':manifest['status'],
                                  'completed_model_calls':manifest['completed_model_calls'],'reason':'inference_budget; exact cause not encoded in original run'})
        else:raise ValueError('Model/parse failures cannot be waived for readiness')
        evidence.extend(directory/name for name in ['manifest.json','config.snapshot.json','events.jsonl','outcome.json','checksum.sha256'])
    if set(completed)!=expected:raise ValueError('Registered compact conditions are missing')
    for item in interruptions:
        successor=completed[item['config_hash']]
        original=json.loads(next(p for p in root.rglob('manifest.json') if p.parent.name==item['run_id']).read_text())
        if successor['started_utc']<=original['ended_utc']:raise ValueError('Interrupted attempt lacks a later complete successor')
    return evidence,{'registered_conditions':len(expected),'completed_conditions':len(completed),
                     'interrupted_attempts':interruptions,'all_attempts_retained':True}
