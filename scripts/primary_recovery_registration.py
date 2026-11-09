"""Register a frozen continuation of reviewed primary transport failures.

The parent allocation remains stopped and byte-for-byte unchanged. Only unfinished
assignments enter the continuation. Original physical-call authorization is shared;
the supplemental execution allowance is an explicit, separately recorded amendment.
"""
import argparse
import asyncio
import copy
import fcntl
import hashlib
import json
import math
from pathlib import Path
import shutil

from contagion.config import digest
from contagion.storage import FILES, verify
from run_campaign import utc
from run_pilot import ROOT

TRANSPORT_FAILURES = {'RemoteProtocolError', 'ConnectError', 'ReadTimeout', 'ConnectTimeout',
                      'ReadError', 'WriteError', 'WriteTimeout', 'PoolTimeout'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing or unsafe parent evidence')
    return json.loads(path.read_text())


def private_write(path, data):
    path = Path(path)
    with path.open('x') as stream:
        path.chmod(0o600)
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write('\n')


def _parent_plan(parent):
    from primary_long_queue import validate_plan
    return validate_plan(parent)


def inspect(parent, source=None):
    """Validate all original assignment/call ledgers, including the lost response."""
    parent = Path(parent).resolve()
    plan = _parent_plan(parent)
    state = read(parent / 'primary-long-state.json')
    if state.get('status') != 'stopped' or state.get('plan_hash') != plan['plan_hash']:
        raise ValueError('Recovery requires the stopped matching parent allocation')
    source = Path(source).resolve() if source else ROOT / 'results/repository-runs' / parent.name
    complete = {}; attempts = []; physical = returned = 0; failed = 0
    for directory in sorted(source.glob('job-*/*')):
        if not directory.is_dir():
            continue
        if directory.is_symlink() or directory.parent.is_symlink():
            raise ValueError('Unsafe parent attempt')
        try:
            index = int(directory.parent.name.removeprefix('job-'))
            job = plan['jobs'][index]
        except (ValueError, IndexError):
            raise ValueError('Unregistered parent assignment') from None
        if index < 0 or directory.parent.name != f'job-{index:03}':
            raise ValueError('Invalid parent job index')
        if not all((directory / name).is_file() and not (directory / name).is_symlink()
                   for name in (*FILES, 'checksum.sha256')) or not verify(directory):
            raise ValueError('Parent attempt is unsealed or failed integrity')
        config = read(directory / 'config.snapshot.json')
        manifest = read(directory / 'manifest.json')
        events = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()]
        if [e['sequence_no'] for e in events] != list(range(len(events))):
            raise ValueError('Parent event sequence changed')
        identity = manifest.get('model_identity', {})
        if (manifest.get('plan_hash') != plan['plan_hash']
                or config.get('registry_freeze_hash') != plan['plan_hash']
                or manifest.get('source_hash') != plan['source_hash']
                or config.get('source_hash') != plan['source_hash']
                or manifest.get('source_unchanged_on_exit') is not True
                or manifest.get('protocol_version') != '3.3-repository-safeguard'
                or config.get('protocol_version') != manifest['protocol_version']):
            raise ValueError('Parent attempt provenance mismatch')
        if (identity.get('backend') != 'ollama' or identity.get('worker_label') != 'primary'
                or identity.get('model') != plan['model'] or identity.get('digest') != plan['model_digest']):
            raise ValueError('Parent model identity mismatch')
        if any(config.get(k) != job[k] for k in ('task_id', 'rounds', 'topology', 'seed', 'phase', 'defense', 'intervention')):
            raise ValueError('Parent assignment differs from frozen schedule')
        http = sum(e['event_type'] == 'http_attempt' for e in events)
        responses = sum(e['event_type'] == 'inference_response' for e in events)
        artifact_ids = [(e.get('agent_id'), e.get('round')) for e in events if e['event_type'] == 'artifact']
        expected = [(f'agent_{a}', r) for r in range(job['rounds']) for a in range(5)]
        if (not 0 <= responses <= http <= job['calls'] or manifest.get('http_attempts') != http
                or manifest.get('completed_model_calls') != responses or manifest.get('parse_failures') != 0
                or artifact_ids != expected[:responses] or len(artifact_ids) != responses):
            raise ValueError('Parent counters or artifact coverage mismatch')
        finishes = [e for e in events if e['event_type'] == 'run_finished']
        if len(finishes) != 1 or finishes[0] != events[-1] or finishes[0].get('metadata', {}).get('status') != manifest['status']:
            raise ValueError('Parent finish record mismatch')
        if manifest['status'] == 'completed':
            if responses != job['calls'] or http != responses or index in complete:
                raise ValueError('Duplicate or incomplete completed assignment')
            complete[index] = sha(directory / 'checksum.sha256')
        elif manifest['status'] == 'failed' and manifest.get('failure') in TRANSPORT_FAILURES:
            failed += 1
        else:
            raise ValueError('Only reviewed transport failures can use this continuation')
        attempts.append({'parent_job_index': index, 'attempt_id': directory.name,
            'status': manifest['status'], 'http_attempts': http, 'returned_calls': responses,
            'failure_class': manifest.get('failure'), 'seal_sha256': sha(directory / 'checksum.sha256'),
            'files_sha256': {name: sha(directory / name) for name in FILES}})
        physical += http; returned += responses
    elapsed = state.get('execution_seconds')
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('Invalid parent execution ledger')
    if (state.get('completed_runs') != len(complete) or state.get('physical_calls') != physical
            or state.get('returned_calls') != returned or state.get('failed_runs') != failed):
        raise ValueError('Parent terminal ledger differs from authoritative attempts')
    remaining = [i for i in range(len(plan['jobs'])) if i not in complete]
    needed = sum(plan['jobs'][i]['calls'] for i in remaining)
    available = plan['max_http_attempts'] - physical
    if not failed or not remaining or available < needed:
        raise ValueError('No reviewed failure, remaining assignments, or sufficient original call budget')
    return {'schema_version': 'primary-continuation-inspection-1.0', 'parent_plan_hash': plan['plan_hash'],
        'parent_state_sha256': sha(parent / 'primary-long-state.json'), 'parent_plan_sha256': sha(parent / 'primary-long-plan.json'),
        'parent_status': state['status'], 'parent_completed_runs': len(complete), 'parent_failed_attempts': failed,
        'parent_http_attempts': physical, 'parent_returned_calls': returned, 'parent_execution_seconds': elapsed,
        'original_max_http_attempts': plan['max_http_attempts'], 'original_wall_seconds': plan['max_wall_seconds'],
        'remaining_parent_indexes': remaining, 'remaining_runs': len(remaining), 'remaining_scheduled_calls': needed,
        'remaining_original_call_authorization': available, 'attempts': attempts,
        'completed_parent_indexes': sorted(complete), 'parent_study_complete': False}


def prepare(parent, output, supplemental_hours=8, source=None):
    parent = Path(parent).resolve(); output = Path(output).resolve()
    if (ROOT / 'results').resolve() not in output.parents or output.exists():
        raise ValueError('Use a fresh private continuation directory')
    if type(supplemental_hours) is not int or not 1 <= supplemental_hours <= 12:
        raise ValueError('Supplemental execution allowance must be 1–12 hours')
    lease_path = ROOT / 'results/checkpoint-gates/controller-primary.lock'
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    with (parent / 'queue.lock').open('a') as old_lease, lease_path.open('a') as primary_lease:
        fcntl.flock(old_lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(primary_lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        checked = inspect(parent, source)
        original = _parent_plan(parent)
        reservations = ROOT / 'results/checkpoint-gates/primary-continuation-reservations'
        reservation_path = reservations / (original['plan_hash'] + '.private.json')
        if reservation_path.exists():
            raise ValueError('This parent already has a registered continuation; do not fork its remaining budget')
        from primary_long_queue import load_payload
        for index in checked['remaining_parent_indexes']:
            load_payload(original, original['jobs'][index])
        receipt = {'schema_version': 'primary-continuation-authorization-1.0', 'created_utc': utc(),
            'scope': 'unfinished_assignments_only_not_parent_completion',
            'decision': 'explicit_user_requested_recovery_after_transport_review',
            'operator_assertion': 'Connection health is checked separately before live launch; this receipt is not a network proof.',
            'inspection': checked, 'supplemental_execution_seconds': supplemental_hours * 3600,
            'maximum_combined_execution_seconds': checked['parent_execution_seconds'] + supplemental_hours * 3600,
            'physical_authorization_policy': 'Parent and continuation together remain within original physical-call cap.',
            'recovery_controller_sha256': sha(__file__)}
        receipt['receipt_hash'] = digest(receipt)
        plan = copy.deepcopy(original)
        plan.update(created_utc=utc(), after=None,
            jobs=[copy.deepcopy(original['jobs'][i]) for i in checked['remaining_parent_indexes']],
            planned_runs=checked['remaining_runs'], planned_calls=checked['remaining_scheduled_calls'],
            max_http_attempts=checked['remaining_original_call_authorization'], max_wall_seconds=supplemental_hours * 3600)
        plan['recovery_lineage'] = {'parent_queue': str(parent),
            'parent_source': str(Path(source).resolve()) if source else str(ROOT / 'results/repository-runs' / parent.name),
            'parent_plan_hash': original['plan_hash'], 'parent_completed_runs': checked['parent_completed_runs'],
            'parent_failed_attempts': checked['parent_failed_attempts'], 'parent_http_attempts_debit': checked['parent_http_attempts'],
            'parent_execution_seconds_debit': checked['parent_execution_seconds'],
            'continuation_to_parent_index': checked['remaining_parent_indexes'], 'authorization_receipt_hash': receipt['receipt_hash'],
            'recovery_controller_sha256': sha(__file__), 'parent_study_complete': False}
        plan['limitations'].append('Transport-recovery continuation: parent attempts remain separate and failed; an explicit supplemental wall allowance was registered. Assignment-level analysis must join the recorded index mapping and retain failed-attempt counts.')
        plan['plan_hash'] = digest({k: v for k, v in plan.items() if k != 'plan_hash'})
        reservation = {'schema_version': 'primary-continuation-reservation-1.0',
            'parent_plan_hash': original['plan_hash'], 'continuation_root': str(output),
            'continuation_plan_hash': plan['plan_hash'], 'authorization_receipt_hash': receipt['receipt_hash'],
            'remaining_original_physical_authorization': checked['remaining_original_call_authorization'],
            'created_utc': utc()}
        reservation['reservation_hash'] = digest(reservation)
        reservations.mkdir(parents=True, exist_ok=True)
        private_write(reservation_path, reservation)
        output.mkdir(parents=True)
        archive = output / 'controller'; archive.mkdir()
        for name in original['dependencies']:
            shutil.copyfile(parent / 'controller' / name, archive / name)
        evidence = output / 'parent-evidence'; evidence.mkdir()
        shutil.copyfile(parent / 'primary-long-plan.json', evidence / 'plan.private.json')
        shutil.copyfile(parent / 'primary-long-state.json', evidence / 'state.private.json')
        private_write(evidence / 'attempts.private.json', checked['attempts'])
        private_write(output / 'continuation-authorization.private.json', receipt)
        private_write(output / 'primary-long-plan.json', plan)
    validate(output)
    return plan


def validate(root):
    root = Path(root)
    from primary_long_queue import validate_plan
    plan = validate_plan(root)
    lineage = plan.get('recovery_lineage', {})
    receipt = read(root / 'continuation-authorization.private.json')
    if (receipt.get('receipt_hash') != digest({k: v for k, v in receipt.items() if k != 'receipt_hash'})
            or receipt['receipt_hash'] != lineage.get('authorization_receipt_hash')
            or receipt['recovery_controller_sha256'] != sha(__file__)
            or lineage.get('recovery_controller_sha256') != sha(__file__)):
        raise ValueError('Continuation authorization changed')
    reservation_path = ROOT / 'results/checkpoint-gates/primary-continuation-reservations' / (lineage['parent_plan_hash'] + '.private.json')
    reservation = read(reservation_path)
    if (reservation.get('reservation_hash') != digest({k: v for k, v in reservation.items() if k != 'reservation_hash'})
            or reservation.get('parent_plan_hash') != lineage['parent_plan_hash']
            or reservation.get('continuation_root') != str(root.resolve())
            or reservation.get('continuation_plan_hash') != plan['plan_hash']
            or reservation.get('authorization_receipt_hash') != receipt['receipt_hash']):
        raise ValueError('Continuation budget reservation changed')
    checked = inspect(lineage['parent_queue'], lineage['parent_source'])
    if checked != receipt['inspection']:
        raise ValueError('Parent evidence changed after continuation registration')
    original = _parent_plan(lineage['parent_queue'])
    expected = [original['jobs'][i] for i in checked['remaining_parent_indexes']]
    if (plan['jobs'] != expected or lineage['continuation_to_parent_index'] != checked['remaining_parent_indexes']
            or plan['planned_runs'] != checked['remaining_runs'] or plan['planned_calls'] != checked['remaining_scheduled_calls']
            or plan['max_http_attempts'] != checked['remaining_original_call_authorization']
            or plan['max_wall_seconds'] != receipt['supplemental_execution_seconds'] or plan['after'] is not None):
        raise ValueError('Continuation assignments or budgets changed')
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inspect_parser = sub.add_parser('inspect'); inspect_parser.add_argument('--parent', type=Path, required=True)
    make = sub.add_parser('prepare'); make.add_argument('--parent', type=Path, required=True)
    make.add_argument('--root', type=Path, required=True); make.add_argument('--supplemental-hours', type=int, default=8)
    runner = sub.add_parser('run'); runner.add_argument('--root', type=Path, required=True)
    runner.add_argument('--provider', choices=['mock', 'ollama'], default='mock')
    runner.add_argument('--env-file', type=Path); runner.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.command == 'inspect':
        checked = inspect(args.parent)
        print(json.dumps({k: checked[k] for k in ('parent_completed_runs', 'parent_failed_attempts',
            'remaining_runs', 'remaining_scheduled_calls', 'remaining_original_call_authorization')}, indent=2))
    elif args.command == 'prepare':
        plan = prepare(args.parent, args.root, args.supplemental_hours)
        print('Registered continuation:', plan['planned_runs'], 'unfinished runs /', plan['planned_calls'], 'calls; parent unchanged.')
    else:
        validate(args.root)
        from primary_long_queue import run
        state = asyncio.run(run(args.root, args.provider, args.resume, args.env_file))
        print(state['status'], state['completed_runs'], '/', state['planned_runs'])
