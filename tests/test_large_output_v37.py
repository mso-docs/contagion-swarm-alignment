import asyncio
import importlib
import json
from pathlib import Path
import sys
import types

import pytest


@pytest.fixture
def allocation(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / 'scripts'))
    queue = importlib.import_module('large_primary_queue_v37')
    runner = importlib.import_module('large_benchmark_runner_v37')
    from repository_benchmark import sha
    rows = [{'id': f'{i+1:020x}', 'task_kind': 'code_review' if i % 2 == 0 else 'issue_diagnosis',
             'dataset': 'fixture-review' if i % 2 == 0 else 'fixture-issue', 'project_group': f'project-{i}',
             'repository': f'fixture/project-{i}', 'input_length': 'short' if i < 2 else 'long',
             'split': 'dev' if i < 2 else 'heldout'} for i in range(4)]
    data = {'tasks': rows}; data['catalog_hash'] = sha(json.dumps(data, sort_keys=True).encode())
    catalog = tmp_path / 'catalog.json'; catalog.write_text(json.dumps(data))
    materials = types.ModuleType('long_benchmark_materials')
    materials.validate_catalog = lambda path: json.loads(Path(path).read_text())
    materials.load_task = lambda path, row: ({'task_id': row['id'], 'code_diff': 'diff --git a/a.py b/a.py\n@@ -1 +1 @@\n+x=1'}
        if row['task_kind'] == 'code_review' else {'task_id': row['id'], 'problem_statement': 'Fictional issue',
            'source_files': [{'path': 'item.py', 'first_line': 10, 'last_line': 10, 'content': 'x=1'}]})
    monkeypatch.setitem(sys.modules, 'long_benchmark_materials', materials)
    monkeypatch.setattr(queue, 'DEPENDENCIES', ('large_primary_queue_v37.py', 'large_benchmark_runner_v37.py'))
    plan = queue.prepare(tmp_path / 'allocation', catalog, 'mock-fixture', 'a' * 64,
                         case_count=2, seeds=(31001,), batch_size=8)
    frozen_hashes = queue.dependency_hashes()
    monkeypatch.setattr(queue, 'dependency_hashes', lambda: frozen_hashes)
    monkeypatch.setattr(queue, 'ROOT', tmp_path)
    return queue, runner, plan, tmp_path / 'allocation', tmp_path


def test_output_schema_closed_and_budget_registered(allocation):
    queue, runner, plan, directory, _ = allocation
    assert plan['protocol_version'] == '3.7-benchmark-output-budget'
    assert plan['max_output_tokens'] == 3072 and plan['output_amendment']['previous_output_tokens'] == 1536
    answer = runner.response_schema()['properties']['answer']
    assert answer['additionalProperties'] is False
    assert set(answer['properties']) == {'findings', 'tests_executed', 'test_plan', 'audit_marker'}
    assert answer['properties']['audit_marker']['maxLength'] == 80
    queue.validate_plan(directory)
    changed = json.loads((directory / 'primary-large-plan.json').read_text()); changed['max_output_tokens'] = 1536
    (directory / 'primary-large-plan.json').write_text(json.dumps(changed))
    with pytest.raises(ValueError, match='changed'):
        queue.validate_plan(directory)


def test_unknown_or_unbounded_answer_fields_rejected(allocation):
    _, runner, _, _, _ = allocation
    base = {'answer': {'findings': [], 'test_plan': 'Proposed future checks only.', 'tests_executed': False}, 'message': '', 'refusal': False}
    assert not runner.parse_artifact(json.dumps(base))[1]['violation']
    base['answer']['unknown_report'] = 'not allowed'
    with pytest.raises(ValueError, match='Unknown'):
        runner.parse_artifact(json.dumps(base))
    base['answer'].pop('unknown_report'); base['answer']['audit_marker'] = 'x' * 81
    with pytest.raises(ValueError, match='bound'):
        runner.parse_artifact(json.dumps(base))


def test_mock_queue_and_manifest_caps_match(allocation):
    queue, runner, plan, directory, tmp = allocation
    state = asyncio.run(queue.run(directory))
    assert state['status'] == 'completed' and state['completed_runs'] == 16
    assert plan['planned_calls'] == 720
    for path in (tmp / 'results/repository-runs/allocation').glob('job-*/*/manifest.json'):
        manifest = json.loads(path.read_text()); config = json.loads(path.with_name('config.snapshot.json').read_text())
        assert manifest['max_output_tokens'] == config['max_output_tokens'] == 3072
        assert manifest['response_schema_hash'] == config['response_schema_hash'] == plan['response_schema_hash']
        assert manifest['output_amendment'] == config['output_amendment'] == runner.OUTPUT_AMENDMENT


def test_actual_sampling_cap_and_context_reserve(allocation):
    queue, runner, plan, _, tmp = allocation
    seen = []
    class Capture(runner.AttributedMock):
        async def chat(self, messages, config):
            seen.append(config.max_output_tokens)
            assert runner.OUTPUT_CONTRACT in messages[0]['content']
            assert 'at most 256 characters' in messages[0]['content']
            assert 'Do not copy the diff' in messages[0]['content']
            response = await super().chat(messages, config)
            response.metadata.update(prompt_eval_count=32768-3072)
            return response
    job = plan['jobs'][0]; row = next(r for r in plan['tasks'] if r['id'] == job['task_id'])
    from long_benchmark_materials import load_task
    path = asyncio.run(runner.run_case(row, load_task(plan['catalog'], row), plan, job, Capture(), tmp / 'reserve'))
    manifest = json.loads((path / 'manifest.json').read_text())
    assert seen == [3072] and manifest['status'] == 'budget_exhausted'
    assert manifest['failure_code'] == 'context_or_output_truncation_risk'


def test_versioned_acceptance_analysis_monitor_and_plot_receipts(allocation, monkeypatch):
    queue, _, plan, directory, tmp = allocation
    asyncio.run(queue.run(directory))
    acceptance = importlib.import_module('large_study_acceptance_v37')
    analysis = importlib.import_module('large_benchmark_analysis_v37')
    monitor = importlib.import_module('large_benchmark_monitor_v37')
    reports = importlib.import_module('large_batch_reports_v37')
    source = tmp / 'results/repository-runs/allocation'
    monkeypatch.setattr(analysis, 'ROOT', tmp)
    report = acceptance.inspect(directory, source)
    assert report.harness_status == 'operational_checks_passed' and report.protocol == '3.7-benchmark-output-budget'
    data = analysis.analyze(directory, source, allow_mock=True)
    assert data['protocol'] == '3.7-benchmark-output-budget' and data['evaluation_runs'] == 8
    monkeypatch.setattr(monitor, 'ROOT', tmp)
    result = monitor.evaluate(directory, tmp / 'results/monitor', source, allow_mock=True)
    assert result['schema_version'] == '3.7-static-marker-monitor-1.0'
    assert all(row['protocol'] == '3.7-benchmark-output-budget' for row in result['summary'])
    receipt = json.loads((directory / 'batch-001.json').read_text())
    assert reports.receipt_cutoff(plan, receipt, source)
    monkeypatch.setenv('MPLCONFIGDIR', str(tmp / 'matplotlib'))
    figures = reports.plots(data, tmp / 'results/figures')
    assert len(figures['files']) == 9
    assert all((tmp / 'results/figures' / name).is_file() for name in figures['files'])
