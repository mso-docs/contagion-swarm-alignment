"""Versioned secondary recovery with shared original call authorization.

Only the output allowance changes in protocol3.5. Original protocol3.1 attempts
remain immutable, and completed assignments are not repeated as new observations.
"""
import argparse
import asyncio
import fcntl
import hashlib
import json
import math
from pathlib import Path
import shutil
import time

from contagion.config import canonical, digest
from contagion.inference import CallBudgetExhausted
from contagion.storage import FILES, source_fingerprint, verify
from run_campaign import atomic, cooled, cooling_required, resource_reason, utc, validate_readiness
from run_pilot import ROOT, load_env
from run_repository_study import RepositoryProvider, RepoMock, load_input
from secondary_review_v35 import PROTOCOL, OUTPUT_TOKENS, run_case

DEPENDENCIES = ('secondary_recovery.py', 'secondary_review_v35.py', 'run_repository_study.py',
                'repository_benchmark.py', 'run_campaign.py', 'run_pilot.py', 'remote_worker.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def private_write(path, value):
    with Path(path).open('x') as stream:
        Path(path).chmod(0o600); json.dump(value, stream, indent=2, sort_keys=True); stream.write('\n')


def parent_plan(parent):
    parent = Path(parent); plan = json.loads((parent / 'long-horizon.json').read_text())
    expected = hashlib.sha256(json.dumps({k: v for k, v in plan.items() if k != 'plan_hash'}, sort_keys=True).encode()).hexdigest()
    if (expected != plan['plan_hash'] or plan['source_hash'] != source_fingerprint()
            or sha(parent / 'controller/run_repository_study.py') != plan['controller_sha256']
            or sha(ROOT / 'scripts/run_repository_study.py') != plan['controller_sha256']):
        raise ValueError('Frozen parent source or plan changed')
    return plan


def inspect(parent, source=None):
    parent = Path(parent).resolve(); plan = parent_plan(parent)
    state = json.loads((parent / 'queue-state.json').read_text())
    if state['status'] != 'stopped':
        raise ValueError('Parent must be stopped before registering recovery')
    source = Path(source).resolve() if source else ROOT / 'results/repository-runs' / parent.name
    complete = set(); attempts = []; physical = returned = failed = 0; recorded_seconds = 0.
    for directory in sorted(source.glob('job-*/*')):
        if not directory.is_dir():
            continue
        try:
            index = int(directory.parent.name.removeprefix('job-')); job = plan['jobs'][index]
        except (ValueError, IndexError):
            raise ValueError('Unregistered parent job') from None
        if (index < 0 or directory.parent.name != f'job-{index:03}' or directory.is_symlink()
                or directory.parent.is_symlink() or any((directory / n).is_symlink() for n in (*FILES, 'checksum.sha256'))
                or not verify(directory)):
            raise ValueError('Parent attempt unsealed, unsafe or corrupt')
        config = json.loads((directory / 'config.snapshot.json').read_text())
        manifest = json.loads((directory / 'manifest.json').read_text())
        frozen, row, _ = load_input(parent / job['freeze'], plan['catalog'], job['case_id'])
        condition = config.get('intervention'); identity = manifest.get('model_identity', {})
        if (condition not in {'none', 'benign_override'} or config.get('task_id') != job['case_id']
                or config.get('rounds') != job['rounds'] or config.get('topology') != job['topology']
                or config.get('seed') != plan['seed'] or config.get('registry_freeze_hash') != frozen['freeze_hash']
                or config.get('max_output_tokens') != 1536 or config.get('context_tokens_requested') != 32768
                or config.get('protocol_version') != '3.1-repository' or manifest.get('protocol_version') != '3.1-repository'
                or manifest.get('source_hash') != plan['source_hash'] or config.get('source_hash') != plan['source_hash']
                or manifest.get('source_unchanged_on_exit') is not True or manifest.get('controller_hash') != plan['controller_sha256']):
            raise ValueError('Parent attempt assignment or provenance mismatch')
        if identity.get('backend') != 'ollama' or identity.get('worker_label') != 'secondary':
            raise ValueError('Parent worker identity mismatch')
        events = [json.loads(x) for x in (directory / 'events.jsonl').read_text().splitlines()]
        if [e['sequence_no'] for e in events] != list(range(len(events))):
            raise ValueError('Parent sequence changed')
        http = sum(e['event_type'] == 'http_attempt' for e in events)
        responses = [e for e in events if e['event_type'] == 'inference_response']
        artifacts = [(e.get('agent_id'), e.get('round')) for e in events if e['event_type'] == 'artifact']
        expected = [(f'agent_{a}', r) for r in range(job['rounds']) for a in range(5)]
        if (manifest.get('http_attempts') != http or manifest.get('completed_model_calls') != len(responses)
                or manifest.get('parse_failures') != 0 or http != len(responses) or http > job['rounds'] * 5
                or artifacts != expected[:len(artifacts)]):
            raise ValueError('Parent attempt counters or artifact coverage changed')
        if not events or events[-1]['event_type'] != 'run_finished' or events[-1].get('metadata', {}).get('status') != manifest['status']:
            raise ValueError('Parent finish mismatch')
        diagnosis = None
        key = (index, condition)
        if manifest['status'] == 'completed':
            if http != job['rounds'] * 5 or len(artifacts) != http or key in complete:
                raise ValueError('Duplicate or incomplete completed parent assignment')
            complete.add(key)
        elif (manifest['status'] == 'budget_exhausted' and responses
                and responses[-1].get('metadata', {}).get('done_reason') == 'length'
                and len(artifacts) == len(responses) - 1):
            diagnosis = 'output_token_ceiling_1536'; failed += 1
        else:
            raise ValueError('Parent failure is not the reviewed output-budget condition')
        attempts.append({'parent_pair_index': index, 'condition': condition, 'attempt_id': directory.name,
            'status': manifest['status'], 'http_attempts': http, 'returned_calls': len(responses),
            'diagnosis': diagnosis, 'seal_sha256': sha(directory / 'checksum.sha256'),
            'files_sha256': {name: sha(directory / name) for name in FILES}, 'model_identity': identity})
        physical += http; returned += len(responses)
        duration = manifest.get('duration_seconds')
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
            raise ValueError('Invalid parent duration')
        recorded_seconds += duration
    if not failed:
        raise ValueError('No reviewed output-budget failure to recover')
    remaining = [{'parent_pair_index': index, 'condition': condition, 'task_id': job['case_id'],
                  'rounds': job['rounds'], 'topology': job['topology'], 'freeze': job['freeze'],
                  'calls': job['rounds'] * 5, 'seed': plan['seed']}
                 for index, job in enumerate(plan['jobs']) for condition in ('none', 'benign_override')
                 if (index, condition) not in complete]
    needed = sum(j['calls'] for j in remaining); available = plan['max_http_attempts'] - physical
    if available < needed or not remaining:
        raise ValueError('Original physical-call authorization cannot cover remaining assignments')
    if state.get('completed_pairs', 0) > len(complete) // 2 or state.get('http_attempts', 0) > physical:
        raise ValueError('Parent state exceeds authoritative raw counters')
    return {'schema_version': 'secondary-output-recovery-inspection-1.0', 'parent_plan_hash': plan['plan_hash'],
        'parent_state_sha256': sha(parent / 'queue-state.json'), 'parent_completed_runs': len(complete),
        'parent_failed_attempts': failed, 'parent_http_attempts': physical, 'parent_returned_calls': returned,
        'parent_reported_http_attempts': state.get('http_attempts'), 'remaining_jobs': remaining,
        'parent_recorded_run_seconds': recorded_seconds, 'original_allocation_wall_seconds': plan['max_run_seconds'],
        'remaining_runs': len(remaining), 'remaining_scheduled_calls': needed,
        'remaining_original_call_authorization': available, 'original_max_http_attempts': plan['max_http_attempts'],
        'attempts': attempts, 'parent_study_complete': False}


def prepare(parent, root, supplemental_hours=8, source=None):
    parent = Path(parent).resolve(); root = Path(root).resolve()
    if (ROOT / 'results').resolve() not in root.parents or root.exists() or not 1 <= supplemental_hours <= 12:
        raise ValueError('Use a fresh private root and bounded supplemental execution allowance')
    lease_path = ROOT / 'results/checkpoint-gates/controller.lock'; lease_path.parent.mkdir(parents=True, exist_ok=True)
    with (parent / 'queue.lock').open('a') as parent_lock, lease_path.open('a') as worker_lock:
        fcntl.flock(parent_lock, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(worker_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        checked = inspect(parent, source); original = parent_plan(parent)
        proof = validate_readiness(original['readiness'])
        if proof['readiness_hash'] != original['readiness_hash']:
            raise ValueError('Original readiness changed')
        if any(a['model_identity'].get('model') != proof['model'] or a['model_identity'].get('digest') != proof['model_digest'] for a in checked['attempts']):
            raise ValueError('Parent model differs from pinned readiness')
        reservations = ROOT / 'results/checkpoint-gates/secondary-continuation-reservations'
        reservation_path = reservations / (original['plan_hash'] + '.private.json')
        if reservation_path.exists():
            raise ValueError('Parent remaining budget is already reserved')
        plan = {'schema_version': 'secondary-output-recovery-1.0', 'protocol_version': PROTOCOL, 'created_utc': utc(),
            'parent': str(parent), 'parent_source': str(Path(source).resolve()) if source else str(ROOT / 'results/repository-runs' / parent.name),
            'parent_inspection': checked, 'source_hash': source_fingerprint(),
            'dependencies': {name: sha(ROOT / 'scripts' / name) for name in DEPENDENCIES},
            'catalog': original['catalog'], 'readiness': original['readiness'], 'readiness_hash': original['readiness_hash'],
            'model': proof['model'], 'model_digest': proof['model_digest'], 'worker': 'secondary',
            'jobs': checked['remaining_jobs'], 'planned_runs': checked['remaining_runs'], 'planned_calls': checked['remaining_scheduled_calls'],
            'max_http_attempts': checked['remaining_original_call_authorization'], 'max_wall_seconds': supplemental_hours * 3600,
            'max_run_seconds': 1800, 'max_wait_seconds': 16 * 3600, 'max_output_tokens': OUTPUT_TOKENS,
            'context_tokens': 32768, 'max_history_bytes': 96000,
            'amendment': 'Explicit output ceiling increase from1536 to3072; all new outcomes form protocol3.5, not the old3.1 cohort.',
            'limitations': ['Original failed and completed attempts are unchanged.',
                'Only unfinished original assignments are rerun; recovered conditions are not a balanced new protocol3.5 matrix.',
                'Output budget and recovery time confound direct comparison with protocol3.1.',
                'Full own history remains bounded at96000bytes; hitting it stops instead of silently truncating.',
                'No official benchmark score, collusion, general alignment or mechanistic claim.']}
        plan['plan_hash'] = digest(plan)
        reservation = {'parent_plan_hash': original['plan_hash'], 'continuation_root': str(root),
                       'continuation_plan_hash': plan['plan_hash'], 'created_utc': utc(), 'decision': 'explicit_user_requested_recovery'}
        reservation['reservation_hash'] = digest(reservation)
        reservations.mkdir(parents=True, exist_ok=True); private_write(reservation_path, reservation)
        root.mkdir(parents=True); (root / 'controller').mkdir()
        for name in DEPENDENCIES:
            shutil.copyfile(ROOT / 'scripts' / name, root / 'controller' / name)
        for name in {j['freeze'] for j in plan['jobs']}:
            if Path(name).name != name:
                raise ValueError('Unsafe source freeze name')
            shutil.copyfile(parent / name, root / name)
        private_write(root / 'parent-evidence.private.json', checked)
        private_write(root / 'secondary-recovery-plan.json', plan)
    validate(root); return plan


def validate(root):
    root = Path(root); plan = json.loads((root / 'secondary-recovery-plan.json').read_text())
    if (plan['plan_hash'] != digest({k: v for k, v in plan.items() if k != 'plan_hash'})
            or plan['source_hash'] != source_fingerprint()
            or any(sha(ROOT / 'scripts' / name) != value or sha(root / 'controller' / name) != value for name, value in plan['dependencies'].items())):
        raise ValueError('Frozen recovery plan or source changed')
    if inspect(plan['parent'], plan['parent_source']) != plan['parent_inspection']:
        raise ValueError('Parent evidence changed after recovery registration')
    reservation_path = ROOT / 'results/checkpoint-gates/secondary-continuation-reservations' / (plan['parent_inspection']['parent_plan_hash'] + '.private.json')
    reservation = json.loads(reservation_path.read_text())
    if (reservation['reservation_hash'] != digest({k: v for k, v in reservation.items() if k != 'reservation_hash'})
            or reservation['continuation_root'] != str(root.resolve()) or reservation['continuation_plan_hash'] != plan['plan_hash']):
        raise ValueError('Recovery reservation changed')
    return plan


def recover(root, plan):
    source = ROOT / 'results/repository-runs' / Path(root).name
    done = {}; physical = returned = failed = 0
    for path in sorted(source.glob('job-*/*/events.jsonl')):
        directory = path.parent
        if not verify(directory):
            raise ValueError('Unsealed or corrupt recovery attempt; review before resuming')
        config = json.loads((directory / 'config.snapshot.json').read_text())
        manifest = json.loads((directory / 'manifest.json').read_text())
        index = int(directory.parent.name.removeprefix('job-')); job = plan['jobs'][index]
        if (index < 0 or config.get('recovery_allocation_hash') != plan['plan_hash']
                or config.get('protocol_version') != PROTOCOL or config.get('task_id') != job['task_id']
                or config.get('intervention') != job['condition'] or config.get('topology') != job['topology']
                or config.get('rounds') != job['rounds'] or config.get('seed') != job['seed']
                or config.get('max_output_tokens') != OUTPUT_TOKENS):
            raise ValueError('Recovery attempt assignment mismatch')
        events = [json.loads(x) for x in path.read_text().splitlines()]
        http = sum(e['event_type'] == 'http_attempt' for e in events)
        responses = sum(e['event_type'] == 'inference_response' for e in events)
        if manifest.get('http_attempts') != http or manifest.get('completed_model_calls') != responses:
            raise ValueError('Recovery counters mismatch')
        physical += http; returned += responses
        if manifest['status'] == 'completed':
            if index in done or responses != job['calls']:
                raise ValueError('Duplicate or incomplete completed recovery job')
            done[index] = str(directory)
        else:
            failed += 1
    return done, physical, returned, failed


async def run(root, backend='mock', env_file=None, resume=False, retry_failed=False):
    root = Path(root); plan = validate(root); state_path = root / 'secondary-recovery-state.json'
    if state_path.exists() and not resume:
        raise ValueError('Explicit resume required')
    old = json.loads(state_path.read_text()) if state_path.exists() else {}
    done, physical, returned, failed = recover(root, plan)
    if old.get('backend', backend) != backend or (failed and not retry_failed):
        raise ValueError('Backend change or unreviewed failed retry')
    elapsed = old.get('execution_seconds', 0)
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('Invalid execution ledger')
    state = {'status': 'waiting', 'backend': backend, 'worker': 'secondary', 'plan_hash': plan['plan_hash'],
             'planned_runs': plan['planned_runs'], 'planned_calls': plan['planned_calls'], 'completed_runs': len(done),
             'physical_calls': physical, 'returned_calls': returned, 'failed_runs': failed, 'execution_seconds': elapsed}
    began = None; waiting = time.monotonic(); last_capacity = 0.; issued = physical
    lease = None; provider = RepoMock()

    def save(**kw):
        state.update(kw, updated_utc=utc())
        if began is not None:
            state['execution_seconds'] = elapsed + time.monotonic() - began
        atomic(state_path, state)

    def budget():
        if (root / 'STOP').exists():
            raise CallBudgetExhausted('operator_stop_or_source_changed')
        if began is not None and elapsed + time.monotonic() - began >= plan['max_wall_seconds']:
            raise CallBudgetExhausted('allocation_wall_budget')
        if source_fingerprint() != plan['source_hash']:
            raise CallBudgetExhausted('operator_stop_or_source_changed')
        if shutil.disk_usage(ROOT / 'results').free < 1024 ** 3:
            raise CallBudgetExhausted('controller_disk_low')

    async def resources():
        nonlocal last_capacity
        budget()
        if time.monotonic() - last_capacity < 10:
            return
        from remote_worker import execute
        def capacity():
            return next(v['capacity'] for v in execute('secondary', 'capacity', ROOT / '.env') if 'capacity' in v)
        start = time.monotonic(); stable = 0; cooling = False
        while True:
            budget(); value = await asyncio.to_thread(capacity); reason = resource_reason(value)
            if reason in {'ram_low_or_unknown', 'gpu_temperature_unknown'}:
                raise CallBudgetExhausted('unknown_or_low_resources')
            if not reason and not cooling_required(value) and not cooling:
                break
            cooling = True
            if cooled(value):
                stable += 1
                if stable >= 2:
                    break
            else:
                stable = 0
            if time.monotonic() - start > 600:
                raise CallBudgetExhausted('cooling_timeout')
            save(status='cooling'); await asyncio.sleep(10)
        last_capacity = time.monotonic(); save(status='running')

    with (root / 'queue.lock').open('a') as queue_lock:
        fcntl.flock(queue_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if resume:
            receipt = {'schema_version': 'secondary-output-resume-1.0', 'created_utc': utc(), 'plan_hash': plan['plan_hash'],
                'prior_physical_calls': physical, 'prior_returned_calls': returned, 'prior_execution_seconds': elapsed,
                'prior_failed_attempts': failed, 'decision': 'explicit_retry_failed' if failed else 'explicit_resume'}
            receipt['receipt_hash'] = digest(receipt)
            receipt_dir = root / 'recovery'; receipt_dir.mkdir(exist_ok=True)
            private_write(receipt_dir / f'decision-{len(list(receipt_dir.glob("decision-*.private.json"))) + 1:06}.private.json', receipt)
        save()
        try:
            if backend == 'ollama':
                if env_file is None or Path(env_file).resolve() != ROOT / '.env.secondary':
                    raise ValueError('Explicit secondary env required')
                env = load_env(Path(env_file), {})
                if env.get('CONTAGION_BASE_URL') != 'http://127.0.0.1:11834':
                    raise ValueError('Secondary loopback required')
                proof = validate_readiness(plan['readiness'])
                if proof['readiness_hash'] != plan['readiness_hash']:
                    raise ValueError('Pinned readiness changed')
                lease_path = ROOT / 'results/checkpoint-gates/controller.lock'; lease_path.parent.mkdir(parents=True, exist_ok=True)
                lease = lease_path.open('a')
                while True:
                    try:
                        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB); break
                    except BlockingIOError:
                        budget()
                        if time.monotonic() - waiting > plan['max_wait_seconds']:
                            raise CallBudgetExhausted('allocation_wall_budget')
                        save(status='waiting_for_secondary_lease'); await asyncio.sleep(5)
                class Provider(RepositoryProvider):
                    async def chat(self, messages, config):
                        nonlocal issued
                        await resources()
                        if issued >= plan['max_http_attempts']:
                            raise CallBudgetExhausted('physical_call_budget')
                        issued += 1
                        return await super().chat(messages, config)
                provider = Provider(env['CONTAGION_BASE_URL'], api='ollama', retries=0, timeout=90)
                inventory = await provider.discover()
                if not any(m.get('name') == plan['model'] and m.get('digest') == plan['model_digest'] for m in inventory):
                    raise ValueError('Pinned secondary model unavailable')
                provider.identity.update(model=plan['model'], digest=plan['model_digest'], worker_label='secondary')
            began = time.monotonic(); save(status='running')
            for index, job in enumerate(plan['jobs']):
                if index in done:
                    continue
                budget()
                if physical + job['calls'] > plan['max_http_attempts']:
                    raise CallBudgetExhausted('physical_call_budget')
                frozen, row, payload = load_input(root / job['freeze'], plan['catalog'], job['task_id'])
                save(job_index=index, rounds=job['rounds'], topology=job['topology'], intervention=job['condition'])
                remaining = plan['max_wall_seconds'] - (state['execution_seconds'])
                directory = await run_case(row, payload, frozen, plan, provider,
                    ROOT / 'results/repository-runs' / root.name / f'job-{index:03}', job['topology'], job['condition'],
                    seed=job['seed'], max_wall=min(plan['max_run_seconds'], remaining), stop_file=root / 'STOP')
                done, physical, returned, failed = recover(root, plan)
                save(completed_runs=len(done), physical_calls=physical, returned_calls=returned, failed_runs=failed)
                finished = json.loads((directory / 'manifest.json').read_text())
                if finished['status'] != 'completed':
                    save(failure_code=finished.get('failure_code')); raise RuntimeError('Recovery per-run gate failed')
            save(status='completed')
        except BaseException as exc:
            done, physical, returned, failed = recover(root, plan)
            save(status='stopped', error_type=type(exc).__name__, completed_runs=len(done), physical_calls=physical,
                 returned_calls=returned, failed_runs=failed)
            raise
        finally:
            if hasattr(provider, 'close'):
                await provider.close()
            if lease:
                lease.close()
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); subs = parser.add_subparsers(dest='command', required=True)
    i = subs.add_parser('inspect'); i.add_argument('--parent', type=Path, required=True)
    p = subs.add_parser('prepare'); p.add_argument('--parent', type=Path, required=True); p.add_argument('--root', type=Path, required=True)
    p.add_argument('--supplemental-hours', type=int, default=8)
    r = subs.add_parser('run'); r.add_argument('--root', type=Path, required=True); r.add_argument('--provider', choices=['mock', 'ollama'], default='mock')
    r.add_argument('--env-file', type=Path); r.add_argument('--resume', action='store_true'); r.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args()
    if args.command == 'inspect':
        value = inspect(args.parent)
        print(json.dumps({k: value[k] for k in ('parent_completed_runs', 'parent_failed_attempts', 'parent_http_attempts',
            'parent_reported_http_attempts', 'remaining_runs', 'remaining_scheduled_calls', 'remaining_original_call_authorization')}, indent=2))
    elif args.command == 'prepare':
        plan = prepare(args.parent, args.root, args.supplemental_hours)
        print('Registered', plan['planned_runs'], 'unfinished assignments /', plan['planned_calls'], 'calls as', PROTOCOL)
    else:
        state = asyncio.run(run(args.root, args.provider, args.env_file, args.resume, args.retry_failed))
        print(state['status'], state['completed_runs'], '/', state['planned_runs'])
