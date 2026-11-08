import copy
import math

import pytest

from contagion.evidence_stats import neural_diagnostics, paired_effects, summaries, wilson
from contagion.neural import validate_numeric_capture


def row(**updates):
    base = {'id': 'unit', 'model': 'mock-model', 'backend': 'mock', 'model_digest': None,
        'worker_label': 'local', 'protocol': '2.4', 'freeze_hash': 'frozen-test',
        'task_family': 'catalog', 'split': 'development', 'executor': 'deny',
        'topology': 'ring', 'agent_count': 5, 'intervention': 'none', 'status': 'completed',
        'violation_status': 'not_observed', 'violation': False, 'runtime': 2., 'calls': 10,
        'task_success_rate': 1., 'parse_failures': 0, 'case_id': 'case-1', 'seed': 101}
    return {**base, **updates}


def test_zero_events_has_nonzero_upper_bound_and_missing_is_not_negative():
    interval = wilson(0, 3)
    assert math.isclose(interval[0], 0, abs_tol=1e-12)
    assert interval[1] > .5
    assert wilson(0, 0) is None
    stats = summaries([row(), row(id='unknown', violation_status='indeterminate', parse_failures=1)])[0]
    assert stats['attempts'] == 2 and stats['scorable_runs'] == 1
    assert stats['indeterminate_or_unfinished'] == 1
    assert stats['violation_rate'] == 0
    assert len(summaries([row(), row(freeze_hash='different')])) == 2
    assert len(summaries([row(), row(worker_label='secondary')])) == 2


def test_paired_effect_never_selects_favorable_retry_or_pairs_across_freezes():
    control = row()
    injected = row(id='challenge', intervention='benign_override', violation=True, violation_status='observed')
    result = paired_effects([control, injected])[0]
    assert result['matched_pairs'] == 1 and result['mean_injected_minus_control'] == 1
    result = paired_effects([control, injected, row(id='retry')])[0]
    assert result['matched_pairs'] == 0 and result['ambiguous_retry_pairs'] == 1
    assert all(r['matched_pairs'] == 0 for r in paired_effects([control, {**injected, 'freeze_hash': 'other'}]))
    result = paired_effects([control, {**injected, 'violation_status': 'indeterminate'}])[0]
    assert result['unscorable_pairs'] == 1 and result['mean_injected_minus_control'] is None


def capture():
    return {'id': 'test-only', 'schema_version': '1.0', 'evidence_type': 'random_weight_smoke',
        'clean_token_count': 1, 'corrupt_token_count': 1,
        'layers': [{'layer': 0, 'clean_residual_rms': [.2], 'corrupt_residual_rms': [.3],
                    'neurons': [{'index': 0, 'clean': [.4], 'corrupt': [.5]}]}],
        'patch': {'hook': 'blocks.0.hook_out', 'clean_position': 0, 'corrupt_position': 0,
                  'clean_target_logit': 2., 'corrupt_target_logit': 0., 'patched_target_logit': 1.,
                  'noop_target_logit': 0., 'position_control_logit': 0.}}


def test_neural_normalization_requires_gap_and_noop_and_does_not_clip():
    data = capture()
    assert neural_diagnostics(data)['normalized_restoration'] == .5
    assert not neural_diagnostics(data)['trained_checkpoint_evidence']
    data['patch']['clean_target_logit'] = 1e-8
    assert neural_diagnostics(data)['normalized_restoration'] is None
    data['patch']['clean_target_logit'] = 2.
    data['patch']['noop_target_logit'] = .1
    assert neural_diagnostics(data)['normalized_restoration'] is None
    data['patch']['noop_target_logit'] = 0.
    data['patch']['patched_target_logit'] = 3.
    assert neural_diagnostics(data)['normalized_restoration'] == 1.5


@pytest.mark.parametrize('change', ['shape', 'duplicate', 'negative', 'position', 'revision'])
def test_capture_quality_rejects_inconsistent_artifacts(change):
    data = copy.deepcopy(capture())
    if change == 'shape': data['layers'][0]['clean_residual_rms'] = [.1, .2]
    if change == 'duplicate': data['layers'].append(copy.deepcopy(data['layers'][0]))
    if change == 'negative': data['layers'][0]['clean_residual_rms'] = [-.1]
    if change == 'position': data['patch']['clean_position'] = 7
    if change == 'revision': data['evidence_type'] = 'instrumented_checkpoint_replay'
    with pytest.raises(ValueError): validate_numeric_capture(data)
