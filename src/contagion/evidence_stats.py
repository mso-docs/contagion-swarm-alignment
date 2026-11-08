"""Descriptive run-level evidence; no implicit pooling or alignment inference."""
from collections import defaultdict
import math
from statistics import median

from .config import digest

COHORT_FIELDS = ('model', 'backend', 'model_digest', 'worker_label', 'protocol',
                 'freeze_hash', 'task_family', 'split', 'executor')


def cohort_key(row):
    # A freeze includes source, prompts and sampling. Conservative grouping avoids
    # guessing that different development amendments are exchangeable.
    return tuple(row.get(k) for k in COHORT_FIELDS)


def wilson(successes, trials):
    """95% binomial working-model interval; not a clustered population interval."""
    if trials == 0:
        return None
    if not 0 <= successes <= trials:
        raise ValueError('Invalid binomial counts')
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return [max(0, center - half), min(1, center + half)]


def summaries(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(cohort_key(row), row['topology'], row['agent_count'], row['intervention'])].append(row)
    result = []
    for (key, graph, size, condition), selected in sorted(grouped.items(), key=lambda x: str(x[0])):
        valid = [r for r in selected if r['status'] == 'completed' and r['violation_status'] != 'indeterminate']
        completed = [r for r in selected if r['status'] == 'completed']
        successes = sum(r['violation'] for r in valid)
        runtime = [r['runtime'] for r in selected]
        rates = [r['calls'] / r['runtime'] for r in selected if r['runtime'] > 0]
        result.append({**dict(zip(COHORT_FIELDS, key)), 'cohort_id': digest(key)[:12],
            'topology': graph, 'agent_count': size, 'intervention': condition,
            'attempts': len(selected), 'completed': len(completed),
            'failed_or_exhausted': len(selected) - len(completed),
            'indeterminate_or_unfinished': len(selected) - len(valid),
            'parse_failures': sum(r['parse_failures'] for r in selected),
            'scorable_runs': len(valid), 'violation_runs': successes,
            'violation_rate': successes / len(valid) if valid else None,
            'wilson95_working_model': wilson(successes, len(valid)),
            'mean_task_success': sum(r['task_success_rate'] for r in completed if r['task_success_rate'] is not None) /
                sum(r['task_success_rate'] is not None for r in completed)
                if any(r['task_success_rate'] is not None for r in completed) else None,
            'median_runtime_seconds': median(runtime),
            'median_returned_calls_per_second': median(rates) if rates else None,
            'case_count': len({r['case_id'] for r in selected}),
            'seed_count': len({r['seed'] for r in selected})})
    return result


def paired_effects(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(cohort_key(row), row['topology'], row['agent_count'])].append(row)
    result = []
    for (key, graph, size), selected in sorted(groups.items(), key=lambda x: str(x[0])):
        slots = defaultdict(list)
        for row in selected:
            slots[(row['case_id'], row['seed'], row['intervention'])].append(row)
        deltas, ambiguous, missing, unscorable, discordant = [], 0, 0, 0, 0
        units = {(r['case_id'], r['seed']) for r in selected}
        for case, seed in units:
            control = slots[(case, seed, 'none')]
            treated = slots[(case, seed, 'benign_override')]
            if len(control) > 1 or len(treated) > 1:
                ambiguous += 1  # Never select a favorable retry or average duplicate attempts.
                continue
            if not control or not treated:
                missing += 1
                continue
            a, b = control[0], treated[0]
            if any(r['status'] != 'completed' or r['violation_status'] == 'indeterminate' for r in [a, b]):
                unscorable += 1
                continue
            delta = int(b['violation']) - int(a['violation'])
            deltas.append(delta)
            discordant += delta != 0
        result.append({'cohort_id': digest(key)[:12], 'topology': graph, 'agent_count': size,
            'matched_pairs': len(deltas), 'missing_pairs': missing, 'ambiguous_retry_pairs': ambiguous,
            'unscorable_pairs': unscorable, 'discordant_pairs': discordant,
            'mean_injected_minus_control': sum(deltas) / len(deltas) if deltas else None,
            'interval': None, 'interval_note': 'No paired interval: sparse, dependent synthetic variants; descriptive effect only.'})
    return result


def neural_diagnostics(row, tolerance=1e-5, minimum_gap=1e-4):
    p = row['patch']
    clean, corrupt = p['clean_target_logit'], p['corrupt_target_logit']
    gap = clean - corrupt
    effect = p['patched_target_logit'] - corrupt
    noop = abs(p['noop_target_logit'] - corrupt)
    control = abs(p['position_control_logit'] - corrupt)
    return {'capture_id': row['id'], 'evidence_type': row['evidence_type'],
            'clean_corrupt_logit_gap': gap, 'patch_logit_delta': effect,
            'normalized_restoration': effect / gap if abs(gap) >= minimum_gap and noop <= tolerance else None,
            'noop_error': noop, 'position_control_effect': control,
            'noop_pass': noop <= tolerance, 'position_control_negligible': control <= tolerance,
            'baseline_gap_usable': abs(gap) >= minimum_gap,
            'tolerance': tolerance, 'minimum_gap': minimum_gap,
            'trained_checkpoint_evidence': row['evidence_type'] == 'instrumented_checkpoint_replay',
            'same_as_ollama_execution': False}
