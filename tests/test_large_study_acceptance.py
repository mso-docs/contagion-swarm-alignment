import asyncio
import importlib
import json
from pathlib import Path

import pytest

from contagion.config import digest
from contagion.storage import seal,source_fingerprint

DIFF='diff --git a/item.py b/item.py\n--- a/item.py\n+++ b/item.py\n@@ -1 +1 @@\n-old\n+new\n'

@pytest.fixture
def study(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    gate=importlib.import_module('large_study_acceptance');runner=importlib.import_module('large_benchmark_runner')
    queue=tmp_path/'queue';queue.mkdir();source=tmp_path/'raw';source.mkdir()
    tasks=[{'id':f'{i:020x}','task_kind':'code_review','input_length':'long','split':split,'project_group':f'fixture-{i}','dataset':'fixture'} for i,split in enumerate(['dev','heldout'])]
    jobs=[]
    for row,phase,rounds in [(tasks[0],'integration_precheck',3),(tasks[1],'evaluation',4)]:
        for defense in ['plain','source_attribution']:
            for intervention in ['none','benign_override']:
                jobs.append({'task_id':row['id'],'phase':phase,'rounds':rounds,'topology':'ring','seed':31001,'defense':defense,'intervention':intervention,'batch':0 if phase=='integration_precheck' else 1,'stage_id':'precheck' if phase=='integration_precheck' else 'coverage','calls':rounds*5})
    for job in jobs:job['id']=digest(job)[:16]
    queue_module=importlib.import_module('large_primary_queue')
    plan={'protocol_version':runner.PROTOCOL,'plan_hash':'b'*64,'catalog_hash':'d'*64,'source_hash':source_fingerprint(),'dependencies':{'large_benchmark_runner.py':'a'*64},'tasks':tasks,'jobs':jobs,'planned_runs':len(jobs),'planned_calls':sum(j['calls'] for j in jobs),'max_http_attempts':160,'max_run_seconds':120,'development_feasibility':queue_module.FEASIBILITY_POLICY,
          'agent_count':5,'agent_tools':[],'upstream_execution':False,'oracle_visible_to_agents':False,'model':'fixture','model_digest':'c'*64}
    async def collect():
        for index,job in enumerate(jobs):
            row=next(x for x in tasks if x['id']==job['task_id']);provider=runner.AttributedMock()
            await runner.run_case(row,{'task_id':row['id'],'code_diff':DIFF},plan,job,provider,source/f'job-{index:03}')
    asyncio.run(collect());(queue/'primary-large-state.json').write_text(json.dumps({'status':'completed','plan_hash':plan['plan_hash']}))
    recovered=queue_module.recover(source,plan)
    (queue/'development-feasibility.private.json').write_text(json.dumps(queue_module.development_feasibility(plan,recovered)))
    monkeypatch.setattr(gate,'_plan',lambda q:plan)
    monkeypatch.setattr(gate,'_payload',lambda p,row:{'task_id':row['id'],'code_diff':DIFF})
    return gate,queue,source,plan


def test_harness_pass_does_not_require_successful_model_behavior(study,tmp_path):
    gate,q,source,plan=study;report=gate.inspect(q,source)
    assert report.harness_status=='operational_checks_passed' and report.scientific_status=='mock_only'
    assert report.any_round_scorer_positive_runs>0 and report.semantic_quality_score is None
    assert report.launch_full_coverage_gate is False and report.registered_boundary_analysis_ready is False
    assert report.model_success_required_for_harness_pass is False and report.legacy_human_audit_transfers_to_new_tasks is False
    p=tmp_path/'report.json';p.write_text(report.model_dump_json());assert gate.validate_report(p)==report
    data=json.loads(p.read_text());data['completed_runs']=99;p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='hash'):gate.validate_report(p)


def test_hidden_oracle_field_and_private_history_leak_fail_gate(study):
    gate,q,source,plan=study;p=next((source/'job-004').glob('*/events.jsonl'));events=[json.loads(s) for s in p.read_text().splitlines()]
    request=next(e for e in events if e['event_type']=='inference_requested' and e['round']==3)
    request['metadata']['messages'].insert(2,{'role':'assistant','content':'another agent private response'})
    p.write_text(''.join(json.dumps(e)+'\n' for e in events));seal(p.parent)
    result=gate.inspect(q,source);assert result.harness_status=='blocked'
    assert next(c for c in result.checks if c.criterion=='routing_and_history').status=='fail'


def test_future_round_delivery_and_bad_assignment_fail_gate(study):
    gate,q,source,plan=study;p=next((source/'job-004').glob('*/events.jsonl'));events=[json.loads(s) for s in p.read_text().splitlines()]
    next(e for e in events if e['event_type']=='message_delivered')['metadata']['source_round']=99
    p.write_text(''.join(json.dumps(e)+'\n' for e in events));seal(p.parent)
    result=gate.inspect(q,source)
    assert result.harness_status=='blocked'
    assert 'routing_and_history' in {c.criterion for c in result.checks if c.status=='fail'}
    m=p.parent/'manifest.json';value=json.loads(m.read_text());value['plan_hash']='f'*64;m.write_text(json.dumps(value));seal(p.parent)
    with pytest.raises(ValueError,match='Foreign plan'):gate.inspect(q,source)


def test_failed_attempt_is_retained_and_cannot_be_recast_as_behavioral_negative(study):
    gate,q,source,plan=study;p=next((source/'job-004').glob('*/manifest.json'));data=json.loads(p.read_text());data['status']='failed';p.write_text(json.dumps(data));seal(p.parent)
    result=gate.inspect(q,source)
    assert result.failed_sealed_attempts==1 and result.completed_runs==7 and result.harness_status=='blocked'
    assert result.registered_boundary_analysis_ready is False


def test_hidden_fields_detection_is_structural_not_a_keyword_rule(study):
    gate,_,_,_=study
    assert gate.contains_hidden_keys({'oracle':{'truth':True}})
    assert not gate.contains_hidden_keys({'code_diff':'a literal string discussing golden files'})


def test_missing_registered_delivery_and_sealed_malformed_tail_are_rejected(study):
    gate,q,source,plan=study;p=next((source/'job-004').glob('*/events.jsonl'));original=p.read_text();events=[json.loads(s) for s in original.splitlines()]
    del events[next(i for i,e in enumerate(events) if e['event_type']=='message_delivered')]
    p.write_text(''.join(json.dumps(e)+'\n' for e in events));seal(p.parent)
    assert next(c for c in gate.inspect(q,source).checks if c.criterion=='routing_and_history').status=='fail'
    p.write_text(original+'{"malformed":');seal(p.parent)
    with pytest.raises(ValueError,match='JSONL'):gate.inspect(q,source)


def test_treatment_assignment_requires_actual_registered_intervention(study):
    gate,q,source,plan=study;p=next((source/'job-005').glob('*/events.jsonl'));events=[json.loads(s) for s in p.read_text().splitlines()]
    events=[e for e in events if e['event_type']!='intervention_applied']
    p.write_text(''.join(json.dumps(e)+'\n' for e in events));seal(p.parent)
    assert next(c for c in gate.inspect(q,source).checks if c.criterion=='routing_and_history').status=='fail'


def test_paired_analysis_requires_explicit_mock_and_preserves_unknown_utility(study):
    _,q,source,_=study;analysis=importlib.import_module('large_benchmark_analysis')
    with pytest.raises(ValueError,match='Mock/live'):analysis.analyze(q,source)
    result=analysis.analyze(q,source,allow_mock=True)
    assert result['analysis_scope']=='completed_registered_matrix' and result['evaluation_runs']==4
    assert len(result['difference_in_differences'])==1 and result['quality_precision'] is None
    assert result['official_benchmark_score'] is False and result['backend']=='mock'


def test_partial_batch_analysis_needs_cutoff_and_complete_registered_batch(study):
    from datetime import datetime,timezone
    _,q,source,_=study;analysis=importlib.import_module('large_benchmark_analysis')
    with pytest.raises(ValueError,match='explicit cutoff'):analysis.analyze(q,source,completed_batches=True,allow_mock=True)
    cutoff=datetime.now(timezone.utc).isoformat()
    (q/'primary-large-state.json').unlink()
    result=analysis.analyze(q,source,completed_batches=True,cutoff=cutoff,allow_mock=True)
    assert result['analysis_scope']=='completed_registered_batches_descriptive' and result['uncertainty']==[]
    (next((source/'job-004').glob('*/manifest.json'))).unlink()
    with pytest.raises(ValueError,match='No complete evaluation batch'):analysis.analyze(q,source,completed_batches=True,cutoff=cutoff,allow_mock=True)


def fail_attempt(path):
    m=path/'manifest.json';data=json.loads(m.read_text());data.update(status='failed',failure='OSError');m.write_text(json.dumps(data))
    events=[json.loads(s) for s in (path/'events.jsonl').read_text().splitlines()];events[-1]['metadata'].update(status='failed',reason='OSError')
    (path/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    o=path/'outcome.json';value=json.loads(o.read_text());value['status']='failed';o.write_text(json.dumps(value));seal(path)


def test_explicit_reviewed_retry_restores_analysis_without_erasing_failure(study):
    gate,q,source,plan=study;driver=importlib.import_module('large_primary_queue');runner=importlib.import_module('large_benchmark_runner')
    analysis=importlib.import_module('large_benchmark_analysis')
    original=next((source/'job-004').glob('*/manifest.json')).parent;fail_attempt(original)
    recovered=driver.recover(source,plan)
    driver.record_recovery(q,plan,recovered,recovered['observed_or_reserved_execution_seconds'],True)
    assert gate.inspect(q,source).harness_status=='blocked'  # No successful matching successor yet.
    job=plan['jobs'][4];row=next(t for t in plan['tasks'] if t['id']==job['task_id'])
    asyncio.run(runner.run_case(row,{'task_id':row['id'],'code_diff':DIFF},plan,job,runner.AttributedMock(),source/'job-004'))
    report=gate.inspect(q,source)
    assert report.harness_status=='operational_checks_passed_with_reviewed_retries'
    assert report.failed_sealed_attempts==1 and report.explicitly_resolved_retained_attempts==1
    assert report.returned_calls>report.planned_calls and original.exists()
    result=analysis.analyze(q,source,allow_mock=True)
    assert result['failed_sealed_attempts']==1 and result['resolved_retained_attempts']==1
    assert any(e['reason']=='failed_or_exhausted_not_behavioral_negative' for e in result['exclusions'])


def test_unreviewed_retained_failure_allows_only_clean_completed_batch_description(study):
    import shutil
    from datetime import datetime,timezone
    gate,q,source,plan=study;analysis=importlib.import_module('large_benchmark_analysis')
    first=next((source/'job-000').glob('*/manifest.json')).parent;extra=first.parent/'retained-failed';shutil.copytree(first,extra);fail_attempt(extra)
    assert gate.inspect(q,source).harness_status=='blocked'
    with pytest.raises(ValueError,match='Operational failure'):analysis.analyze(q,source,allow_mock=True)
    result=analysis.analyze(q,source,completed_batches=True,cutoff=datetime.now(timezone.utc).isoformat(),allow_mock=True)
    assert result['evaluation_runs']==4 and result['harness_acceptance_status']=='blocked' and result['failed_sealed_attempts']==1
    assert result['analysis_scope']=='completed_registered_batches_descriptive' and result['uncertainty']==[]


def test_development_receipt_is_verified_from_actual_visible_coordinates(study):
    gate,q,source,plan=study;p=q/'development-feasibility.private.json';d=json.loads(p.read_text())
    d['kinds']['code_review']['grounded_finding_count']=999;p.write_text(json.dumps(d))
    report=gate.inspect(q,source)
    assert report.harness_status=='blocked' and report.development_source_location_gate=='invalid_receipt'


def test_degenerate_cluster_intervals_are_suppressed_without_changing_points(study):
    analysis=importlib.import_module('large_benchmark_analysis')
    from analyze_primary_long import OUTCOMES
    rows=[{'cohort':'x','comparison_type':'injected_minus_control','defense':'plain','rounds':15,'topology':'ring','case':str(i),'project':str(i),'seed':1,**{key:0.0 for key in OUTCOMES}} for i in range(8)]
    result=analysis.safe_uncertainty(rows)
    assert all(r['project_cluster_uncertainty']['status']=='no_observed_cluster_variation' and r['project_cluster_uncertainty']['interval'] is None for r in result)
    assert all(r['project_cluster_uncertainty']['project_weighted_mean']==0 for r in result)
    for index,row in enumerate(rows):
        if index>=4:row.update({key:1.0 for key in OUTCOMES})
    varied=analysis.safe_uncertainty(rows)
    assert all(r['project_cluster_uncertainty']['status']=='descriptive_interval_available' and r['project_cluster_uncertainty']['interval'][0]<r['project_cluster_uncertainty']['interval'][1] for r in varied)
