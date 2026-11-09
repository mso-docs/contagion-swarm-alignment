"""Bounded operator handoff for early diversity calibration; never changes frozen plans."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from contagion.config import digest
from contagion.events import utc
from contagion.storage import write_json
from diversity_calibration import validate as validate_calibration
from multidomain_docket import private_path, sha
from multidomain_live_v51 import recover as recover_current, validate as validate_current
from run_campaign import atomic
from run_pilot import ROOT

SCRIPTS = ('diversity_interlude.py', 'diversity_calibration.py', 'multidomain_live_v51.py',
           'primary_output_recovery.py', 'primary_review_v36.py', 'rq3_decomposition.py', 'large_primary_queue_v37.py',
           'large_batch_reports_v37.py')
SUCCESSORS = {'primary_output': ('primary_output_recovery.py', 'primary-output-state.json'),
              'decomposition': ('rq3_decomposition.py', 'decomposition-state.json'),
              'large': ('large_primary_queue_v37.py', 'primary-large-state.json')}
ACTIVE = {'waiting', 'running', 'cooling', 'waiting_for_primary_lease'}


def hashes():
    return {name: sha(ROOT / 'scripts' / name) for name in SCRIPTS}


def decision(root, kind, **data):
    directory = Path(root) / 'decisions'; directory.mkdir(exist_ok=True)
    files = sorted(directory.glob('decision-*.private.json'))
    previous = None
    for index, path in enumerate(files, 1):
        value = json.loads(path.read_text())
        if (path.name != f'decision-{index:06d}.private.json' or value['previous_sha256'] != previous
                or value['decision_hash'] != digest({k: v for k, v in value.items() if k != 'decision_hash'})):
            raise ValueError('Operator decision chain changed')
        previous = sha(path)
    value = {'created_utc': utc(), 'kind': kind, 'previous_sha256': previous, **data}
    value['decision_hash'] = digest(value)
    path = directory / f'decision-{len(files)+1:06d}.private.json'
    with path.open('x') as stream:
        path.chmod(0o600); json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    return value


def prepare(root, current, calibration, chain, wait_minutes=120, interlude_minutes=240, report_observer=None):
    root = private_path(root); current = private_path(current); calibration = private_path(calibration)
    if root.exists() or not 1 <= wait_minutes <= 120 or not 10 <= interlude_minutes <= 240:
        raise ValueError('Fresh bounded interlude required')
    parent, _, _ = validate_current(current); study, _, _ = validate_calibration(calibration)
    if study['after'] != str((root / 'handoff.private.json').resolve()):
        raise ValueError('Calibration must wait for this exact operator handoff')
    if study['max_execution_seconds'] > interlude_minutes * 60:
        raise ValueError('Calibration wall budget exceeds interlude ceiling')
    chain = private_path(chain); sequence = json.loads(chain.read_text())
    if Path(sequence['multidomain']).resolve() != current.resolve():
        raise ValueError('Sequence targets a different current allocation')
    for key in SUCCESSORS:
        private_path(sequence[key])
    observer_hash = None
    if report_observer:
        report_observer = private_path(report_observer)
        observer_path = report_observer / 'report-plan.private.json'
        observer = json.loads(observer_path.read_text())
        if (observer['plan_hash'] != digest({k: v for k, v in observer.items() if k != 'plan_hash'})
                or Path(observer['queue']).resolve() != Path(sequence['large']).resolve()
                or (report_observer / 'report-state.private.json').exists()):
            raise ValueError('Use a fresh prepared observer for this exact large queue')
        from large_batch_reports_v37 import hashes as observer_hashes
        if observer_hashes() != observer['dependencies']:
            raise ValueError('Prepared report observer dependencies changed')
        observer_hash = sha(observer_path)
    checks = [i for i, j in enumerate(parent['jobs']) if j['phase'] == 'integration_precheck']
    if not checks:
        raise ValueError('No registered development checkpoint')
    value = {'schema_version': 'diversity-operator-interlude-1.0', 'created_utc': utc(),
             'current': str(current), 'current_plan_hash': parent['plan_hash'],
             'calibration': str(calibration), 'calibration_plan_hash': study['plan_hash'],
             'chain': str(chain), 'chain_sha256': sha(chain), 'development_jobs': checks,
             'max_wait_seconds': wait_minutes * 60, 'max_interlude_seconds': interlude_minutes * 60,
             'report_observer': str(report_observer) if report_observer else None,
             'report_observer_plan_sha256': observer_hash,
             'dependencies': hashes(), 'scope': 'operator_handoff_not_study_completion'}
    value['plan_hash'] = digest(value)
    root.mkdir(parents=True); write_json(root / 'interlude-plan.private.json', value)
    decision(root, 'registered_interlude', current_plan_hash=parent['plan_hash'], calibration_plan_hash=study['plan_hash'])
    return value


def development_ready(plan, recovered, state):
    expected = set(plan['development_jobs'])
    complete = expected <= set(recovered['done'])
    if state['status'] in {'stopped', 'failed', 'budget_exhausted'} and not complete:
        raise RuntimeError('Current study stopped before the development checkpoint')
    return complete


def request_owned_stop(root, current, plan_hash):
    token = json.dumps({'scope': 'operator_diversity_interlude', 'interlude_plan_hash': plan_hash}, sort_keys=True) + '\n'
    path = Path(current) / 'STOP'
    with path.open('x') as stream:
        path.chmod(0o600); stream.write(token); stream.flush(); os.fsync(stream.fileno())
    decision(root, 'pause_requested', stop_sha256=sha(path))
    return token


def archive_owned_stop(root, current, token):
    path = Path(current) / 'STOP'; archive = Path(root) / 'operator-STOP.private.json'
    if not path.is_file() or path.is_symlink() or path.read_text() != token:
        raise ValueError('Do not remove another operator stop marker')
    os.link(path, archive)  # exclusive archive creation; never overwrite previous marker bytes
    path.unlink()
    decision(root, 'owned_stop_archived', stop_sha256=sha(archive))


def zero_call_successor_commands(sequence):
    commands = []
    for key, (script, state_name) in SUCCESSORS.items():
        root = private_path(sequence[key]); path = root / state_name
        if not path.exists():
            continue
        state = json.loads(path.read_text())
        if state['status'] in ACTIVE or state['status'] == 'completed':
            continue
        if state.get('physical_calls', 0) or state.get('completed_runs', 0) or state.get('failed_runs', 0):
            raise ValueError('Successor has inference history; requires separate reviewed recovery')
        if (root / 'STOP').exists():
            raise ValueError('Successor has an independent operator stop marker')
        commands.append((key, [sys.executable, str(ROOT / 'scripts' / script), 'run', '--root', str(root),
                               '--provider', 'ollama', '--env-file', str(ROOT / '.env.primary'), '--resume']))
    return commands


def launch(root, label, command):
    path = Path(root) / (label + '.private.log')
    with path.open('xb') as log:
        process = subprocess.Popen(['/usr/bin/caffeinate', '-i', *command], cwd=ROOT,
            env=dict(os.environ, PYTHONPATH=str(ROOT / 'scripts') + os.pathsep + str(ROOT / 'src')),
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True, close_fds=True)
    decision(root, 'controller_started', controller=label, pid=process.pid)
    return process


def wait_active(process, path, previous_stamp):
    began = time.monotonic()
    while time.monotonic() - began < 90:
        if Path(path).exists():
            state = json.loads(Path(path).read_text())
            if state['status'] in ACTIVE | {'completed'} and state.get('updated_utc', '') > previous_stamp:
                return state
        if process.poll() is not None:
            raise RuntimeError('Resumed controller exited before recording an active state')
        time.sleep(1)
    raise RuntimeError('Resumed controller did not become active within bounded startup wait')


def run(root):
    root = private_path(root); plan = json.loads((root / 'interlude-plan.private.json').read_text())
    if (plan['plan_hash'] != digest({k: v for k, v in plan.items() if k != 'plan_hash'})
            or hashes() != plan['dependencies'] or sha(plan['chain']) != plan['chain_sha256']):
        raise ValueError('Frozen operator interlude changed')
    if plan.get('report_observer') and sha(Path(plan['report_observer']) / 'report-plan.private.json') != plan['report_observer_plan_sha256']:
        raise ValueError('Frozen report observer plan changed')
    state_path = root / 'interlude-state.private.json'
    if state_path.exists():
        raise ValueError('No hidden retry of operator interlude; review existing decisions')
    current = Path(plan['current']); calibration = Path(plan['calibration'])
    parent, _, _ = validate_current(current); study, _, _ = validate_calibration(calibration)
    if parent['plan_hash'] != plan['current_plan_hash'] or study['plan_hash'] != plan['calibration_plan_hash']:
        raise ValueError('Registered experiment changed')
    sequence = json.loads(Path(plan['chain']).read_text())
    state = {'status': 'waiting_for_development', 'scope': plan['scope'], 'model_calls': 0,
             'calibration_status': 'not_started', 'current_resumed': False}
    token = None; safe_to_resume = False; calibration_process = None; operator_error = False
    def save(**kwargs):
        state.update(kwargs, updated_utc=utc()); atomic(state_path, state)
    with (root / 'interlude.lock').open('a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB); save()
        try:
            began = time.monotonic()
            while True:
                if (root / 'STOP').exists() or time.monotonic() - began > plan['max_wait_seconds']:
                    raise RuntimeError('Operator wait stopped or exhausted')
                recovered = recover_current(current, parent)
                current_state = json.loads((current / 'multidomain-live-state.json').read_text())
                if development_ready(plan, recovered, current_state):
                    break
                time.sleep(5)
            baseline = {r['evidence_hash'] for r in recovered['failures'] if r['sealed']}
            token = request_owned_stop(root, current, plan['plan_hash']); save(status='waiting_for_sealed_stop')
            while True:
                if time.monotonic() - began > plan['max_wait_seconds']:
                    raise RuntimeError('Current controller did not seal within handoff wait ceiling')
                current_state = json.loads((current / 'multidomain-live-state.json').read_text())
                recovered = recover_current(current, parent)
                if current_state['status'] in {'stopped', 'completed'} and all(r['sealed'] for r in recovered['failures']):
                    new = [r for r in recovered['failures'] if r['evidence_hash'] not in baseline]
                    for row in new:
                        manifest = json.loads((current / row['attempt'] / 'manifest.json').read_text())
                        if manifest.get('failure_code') != 'operator_stop':
                            raise RuntimeError('Unrelated failure requires review before resuming current study')
                    if len(new) > 1:
                        raise RuntimeError('Unexpected multiple interrupted jobs')
                    safe_to_resume = True; break
                time.sleep(2)
            handoff = {'status': 'completed', 'scope': plan['scope'], 'interlude_plan_hash': plan['plan_hash'],
                       'current_status': current_state['status'], 'current_plan_hash': parent['plan_hash'],
                       'retained_physical_calls': recovered['physical_calls'], 'retained_failed_attempts': len(recovered['failures'])}
            write_json(root / 'handoff.private.json', handoff)
            decision(root, 'sealed_capacity_handoff', **handoff)
            save(status='calibrating')
            calibration_process = launch(root, 'diversity-calibration', [sys.executable,
                str(ROOT / 'scripts/diversity_calibration.py'), 'run', '--root', str(calibration),
                '--provider', 'ollama', '--env-file', str(ROOT / '.env.primary')])
            start = time.monotonic(); stop_sent = False; terminated = False
            while calibration_process.poll() is None:
                elapsed = time.monotonic() - start
                if not stop_sent and ((root / 'STOP').exists() or elapsed >= max(1, plan['max_interlude_seconds'] - 300)):
                    marker = calibration / 'STOP'
                    if not marker.exists():
                        with marker.open('x') as stream:
                            stream.write('operator_interlude_wall_limit\n')
                    decision(root, 'bounded_calibration_stop_requested'); stop_sent = True
                if elapsed >= plan['max_interlude_seconds']:
                    os.killpg(calibration_process.pid, signal.SIGTERM); calibration_process.wait(timeout=30)
                    terminated = True
                    decision(root, 'bounded_calibration_process_terminated', uncertain_attempts_remain=True)
                    break
                time.sleep(2)
            path = calibration / 'diversity-state.json'
            result = json.loads(path.read_text()) if path.exists() else {'status': 'unknown'}
            if terminated:
                result = {**result, 'status': 'operator_terminated_with_uncertain_attempt'}
            decision(root, 'calibration_finished', calibration_status=result['status'], exit_code=calibration_process.returncode)
            save(calibration_status=result['status'], calibration_completed_runs=result.get('completed_runs', 0),
                 calibration_failed_runs=result.get('failed_runs', 0))
        except BaseException as exc:
            operator_error = True
            save(status='operator_review_required', error_type=type(exc).__name__)
            raise
        finally:
            # A failed independent calibration does not erase its evidence or strand the paused current study.
            if token is not None and safe_to_resume and (calibration_process is None or calibration_process.poll() is not None):
                archive_owned_stop(root, current, token)
                current_state = json.loads((current / 'multidomain-live-state.json').read_text())
                if current_state['status'] != 'completed':
                    decision(root, 'explicit_current_retry_authorized', retained_attempts=True, lifetime_budget_reset=False)
                    resumed = launch(root, 'current-resume', [sys.executable, str(ROOT / 'scripts/multidomain_live_v51.py'),
                        'run', '--root', str(current), '--provider', 'ollama', '--env-file', str(ROOT / '.env.primary'),
                        '--resume', '--retry-failed'])
                    wait_active(resumed, current / 'multidomain-live-state.json', current_state.get('updated_utc', ''))
                    save(current_resumed=True)
                else:
                    save(current_resumed=True)
                for label, command in zero_call_successor_commands(sequence):
                    state_file = Path(sequence[label]) / SUCCESSORS[label][1]
                    previous = json.loads(state_file.read_text()).get('updated_utc', '')
                    resumed = launch(root, 'resume-' + label, command)
                    wait_active(resumed, state_file, previous)
                if plan.get('report_observer'):
                    observer_root = Path(plan['report_observer'])
                    if not (observer_root / 'report-state.private.json').exists():
                        launch(root, 'fresh-report-observer', [sys.executable, str(ROOT / 'scripts/large_batch_reports_v37.py'),
                            'run', '--root', str(observer_root)])
                    else:
                        decision(root, 'observer_already_has_state_not_duplicated')
                save(status='restored_after_operator_error' if operator_error else 'completed', scientific_matrix_completion_claimed=False)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--root', type=Path, required=True)
    p.add_argument('--current', type=Path, required=True); p.add_argument('--calibration', type=Path, required=True)
    p.add_argument('--chain', type=Path, required=True); p.add_argument('--wait-minutes', type=int, default=120)
    p.add_argument('--interlude-minutes', type=int, default=240)
    p.add_argument('--report-observer', type=Path)
    r = sub.add_parser('run'); r.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.root, args.current, args.calibration, args.chain, args.wait_minutes, args.interlude_minutes, args.report_observer)
        print('Registered bounded operator interlude; existing model plans remain unchanged.')
    else:
        try:
            result = run(args.root); print(result['status'], '; calibration:', result['calibration_status'])
        except Exception as exc:
            parser.exit(1, f'Operator interlude requires review ({type(exc).__name__}); evidence retained.\n')
