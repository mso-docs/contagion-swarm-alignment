"""Synchronous per-run gate for bounded development checkpoints."""
from contagion.storage import verify
from contagion.studies import summarize_study


class CheckpointGateError(RuntimeError):
    pass


def check_run(path):
    if not verify(path):
        raise CheckpointGateError('integrity')
    row = summarize_study(path)[0]
    config, manifest, outcome = row['config'], row['manifest'], row['outcome']
    expected = 5 if config['research_question'] == 'rq3' else config['agent_count'] * config['rounds']
    if manifest['status'] != 'completed' or manifest['completed_model_calls'] != expected:
        raise CheckpointGateError('completion')
    if manifest['parse_failures']:
        raise CheckpointGateError('structured_output')
    if config['interventions'] == ['none'] and outcome['task_success_rate'] != 1:
        raise CheckpointGateError('control_task')
    if config['executor'] == 'deny' and outcome['actual_state_violation']:
        raise CheckpointGateError('simulator_boundary')
    return row
