"""Transfer unused primary authorization to a fresh prerequisite registration.

Never edits an original plan/state, claims completion or repeats an attempted job.
The mutable authorization pointer is updated only after immutable transfer evidence.
"""
import argparse
import copy
import fcntl
import hashlib
import json
from pathlib import Path
import shutil

from contagion.config import digest
from contagion.events import utc
from run_pilot import ROOT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    with Path(path).open('x') as stream:
        Path(path).chmod(0o600)
        json.dump(data, stream, indent=2, sort_keys=True); stream.write('\n')


def transfer(parent, output, after):
    from primary_output_recovery import validate
    parent, output, after = [Path(p).resolve() for p in (parent, output, after)]
    if output.exists() or any((ROOT/'results').resolve() not in p.parents for p in (parent, output, after)):
        raise ValueError('Use private result paths and a fresh output')
    with (parent/'queue.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = validate(parent)
        state = json.loads((parent/'primary-output-state.json').read_text())
        if state['status'] != 'stopped' or any(state.get(k, 0) != 0 for k in
                ['completed_runs', 'physical_calls', 'returned_calls', 'failed_runs', 'execution_seconds']):
            raise ValueError('Only a stopped allocation with zero calls/time can be transferred')
        source = ROOT/'results/repository-runs'/parent.name
        if source.exists() and any(source.iterdir()):
            raise ValueError('An attempt already exists; preserve and review it')
        key = plan['output_recovery_lineage']['inspection']['continuation_plan_hash']
        pointer = ROOT/'results/checkpoint-gates/primary-output-recovery-reservations'/(key+'.private.json')
        with pointer.with_suffix('.transfer.lock').open('a') as registry_lock:
            fcntl.flock(registry_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            validate(parent)
            old_pointer = json.loads(pointer.read_text())
            fresh = copy.deepcopy(plan)
            fresh.update(after=str(after), created_utc=utc())
            fresh['prerequisite_amendment'] = {'scope': 'zero_call_authorization_transfer',
                'parent_plan_hash': plan['plan_hash'], 'parent_state_sha256': sha(parent/'primary-output-state.json'),
                'prior_after': plan['after'], 'new_after': str(after), 'new_calls_authorized': 0,
                'same_jobs_and_remaining_call_wall_limits': True}
            fresh['plan_hash'] = digest({k:v for k,v in fresh.items() if k!='plan_hash'})
            decision = {'schema_version': 'primary-zero-call-transfer-1.0', 'created_utc': utc(),
                'decision': 'explicit_user_requested_prerequisite_recovery',
                'parent_plan_sha256': sha(parent/'primary-output-plan.json'),
                'parent_state_sha256': sha(parent/'primary-output-state.json'),
                'old_authorization_sha256': sha(pointer), 'new_plan_hash': fresh['plan_hash'],
                'new_after': str(after), 'extra_physical_calls': 0, 'extra_execution_seconds': 0,
                'controller_sha256': sha(__file__), 'old_state_remains_stopped': True}
            decision['decision_hash'] = digest(decision)
            output.mkdir(parents=True); (output/'controller').mkdir()
            for name in plan['dependencies']:
                shutil.copyfile(parent/'controller'/name, output/'controller'/name)
            shutil.copyfile(parent/'primary-output-plan.json', output/'parent-plan.private.json')
            shutil.copyfile(parent/'primary-output-state.json', output/'parent-state.private.json')
            write(output/'prior-authorization.private.json', old_pointer)
            write(output/'transfer-decision.private.json', decision)
            write(output/'primary-output-plan.json', fresh)
            replacement = {**old_pointer, 'new_root':str(output), 'new_plan_hash':fresh['plan_hash'],
                           'previous_reservation_sha256':sha(pointer), 'transfer_decision_hash':decision['decision_hash']}
            replacement['reservation_hash'] = digest({k:v for k,v in replacement.items() if k!='reservation_hash'})
            temporary = pointer.with_suffix('.transfer.tmp')
            write(temporary, replacement); temporary.replace(pointer)
            if not (parent/'STOP').exists():
                (parent/'STOP').write_text('Unused authorization transferred with preserved evidence; do not resume superseded prerequisite.\n')
    validate(output)
    return fresh


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    args = parser.parse_args()
    result = transfer(args.parent, args.out, args.after)
    print('Transferred unused authorization:',result['planned_runs'],'runs; no added call/time budget.')
