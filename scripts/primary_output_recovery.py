"""Frozen protocol3.6 continuation after a diagnosed primary output ceiling.

The original allocation and its transport continuation stay unchanged. Remaining
physical authorization is computed across both before registering new work.
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
import time

from contagion.config import digest
from contagion.inference import CallBudgetExhausted
from contagion.storage import FILES, source_fingerprint, verify
from run_campaign import atomic, cooled, cooling_required, resource_reason, utc, validate_readiness
from run_pilot import ROOT, load_env
from run_repository_study import RepositoryProvider
from primary_review_v36 import PROTOCOL, AttributedMock, run_case

DEPENDENCIES = ('primary_output_recovery.py', 'primary_review_v36.py', 'bounded_review_contract.py', 'primary_recovery_registration.py',
    'primary_long_queue.py', 'primary_repository_runner.py', 'run_repository_study.py',
    'repository_benchmark.py', 'run_campaign.py', 'run_pilot.py', 'remote_worker.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def private_write(path, value):
    with Path(path).open('x') as stream:
        Path(path).chmod(0o600); json.dump(value, stream, indent=2, sort_keys=True); stream.write('\n')


def ancestor(continuation):
    from primary_recovery_registration import validate, inspect
    plan = validate(continuation)
    lineage = plan['recovery_lineage']
    checked = inspect(lineage['parent_queue'], lineage['parent_source'])
    return plan, checked


def inspect(continuation, source=None):
    continuation = Path(continuation).resolve(); plan, original = ancestor(continuation)
    state = json.loads((continuation / 'primary-long-state.json').read_text())
    if state['status'] != 'stopped' or state['plan_hash'] != plan['plan_hash']:
        raise ValueError('Matching continuation must be stopped')
    source = Path(source).resolve() if source else ROOT / 'results/repository-runs' / continuation.name
    complete = {}; attempts = []; http_total = responses_total = failed = 0
    for directory in sorted(source.glob('job-*/*')):
        if not directory.is_dir():
            continue
        try:
            index = int(directory.parent.name.removeprefix('job-')); job = plan['jobs'][index]
        except (ValueError, IndexError):
            raise ValueError('Unregistered continuation assignment') from None
        if (index < 0 or directory.parent.name != f'job-{index:03}' or directory.is_symlink()
                or directory.parent.is_symlink() or any((directory / n).is_symlink() for n in (*FILES, 'checksum.sha256'))
                or not verify(directory)):
            raise ValueError('Continuation attempt unsafe, unsealed or corrupt')
        config = json.loads((directory / 'config.snapshot.json').read_text())
        manifest = json.loads((directory / 'manifest.json').read_text()); identity = manifest.get('model_identity', {})
        if (config.get('registry_freeze_hash') != plan['plan_hash'] or manifest.get('plan_hash') != plan['plan_hash']
                or config.get('protocol_version') != '3.3-repository-safeguard'
                or manifest.get('protocol_version') != '3.3-repository-safeguard'
                or config.get('source_hash') != plan['source_hash'] or manifest.get('source_hash') != plan['source_hash']
                or manifest.get('source_unchanged_on_exit') is not True or config.get('max_output_tokens') != 1536
                or any(config.get(k) != job[k] for k in ('task_id', 'rounds', 'topology', 'seed', 'phase', 'defense', 'intervention'))):
            raise ValueError('Continuation provenance or assignment mismatch')
        if (identity.get('backend') != 'ollama' or identity.get('worker_label') != 'primary'
                or identity.get('model') != plan['model'] or identity.get('digest') != plan['model_digest']):
            raise ValueError('Continuation model identity mismatch')
        events = [json.loads(x) for x in (directory / 'events.jsonl').read_text().splitlines()]
        if [e['sequence_no'] for e in events] != list(range(len(events))):
            raise ValueError('Continuation sequence changed')
        http = sum(e['event_type'] == 'http_attempt' for e in events)
        responses = [e for e in events if e['event_type'] == 'inference_response']
        artifacts = [(e.get('agent_id'), e.get('round')) for e in events if e['event_type'] == 'artifact']
        expected = [(f'agent_{a}', r) for r in range(job['rounds']) for a in range(5)]
        if (manifest.get('http_attempts') != http or manifest.get('completed_model_calls') != len(responses)
                or manifest.get('parse_failures') != 0 or http != len(responses) or http > job['calls']
                or artifacts != expected[:len(artifacts)]):
            raise ValueError('Continuation counters or artifact coverage mismatch')
        if not events or events[-1]['event_type'] != 'run_finished' or events[-1].get('metadata', {}).get('status') != manifest['status']:
            raise ValueError('Continuation finish mismatch')
        if manifest['status'] == 'completed':
            if http != job['calls'] or len(artifacts) != http or index in complete:
                raise ValueError('Duplicate or incomplete completed continuation job')
            complete[index] = sha(directory / 'checksum.sha256')
        elif (manifest['status'] == 'budget_exhausted' and responses
                and responses[-1].get('metadata', {}).get('done_reason') == 'length'
                and len(artifacts) == len(responses) - 1):
            failed += 1
        else:
            raise ValueError('Continuation failure is not the reviewed output truncation')
        attempts.append({'continuation_job_index': index,
            'original_job_index': plan['recovery_lineage']['continuation_to_parent_index'][index],
            'attempt_id': directory.name, 'status': manifest['status'], 'http_attempts': http,
            'returned_calls': len(responses), 'seal_sha256': sha(directory / 'checksum.sha256'),
            'files_sha256': {name: sha(directory / name) for name in FILES}})
        http_total += http; responses_total += len(responses)
    if (state.get('completed_runs') != len(complete) or state.get('physical_calls') != http_total
            or state.get('returned_calls') != responses_total or state.get('failed_runs') != failed or not failed):
        raise ValueError('Continuation terminal ledger mismatch or no reviewed truncation')
    elapsed = state.get('execution_seconds')
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('Invalid continuation execution ledger')
    pending = [i for i in range(len(plan['jobs'])) if i not in complete]
    prior_calls = original['parent_http_attempts'] + http_total
    available = original['original_max_http_attempts'] - prior_calls
    needed = sum(plan['jobs'][i]['calls'] for i in pending)
    if available < needed or not pending:
        raise ValueError('Cumulative original physical authorization cannot cover unfinished jobs')
    return {'schema_version': 'primary-output-recovery-inspection-1.0',
        'original_inspection': original, 'continuation_plan_hash': plan['plan_hash'],
        'continuation_state_sha256': sha(continuation / 'primary-long-state.json'),
        'continuation_completed_runs': len(complete), 'continuation_failed_attempts': failed,
        'continuation_http_attempts': http_total, 'continuation_returned_calls': responses_total,
        'continuation_execution_seconds': elapsed, 'completed_original_runs': original['parent_completed_runs'] + len(complete),
        'cumulative_prior_http_attempts': prior_calls,
        'cumulative_prior_execution_seconds': original['parent_execution_seconds'] + elapsed,
        'remaining_continuation_indexes': pending,
        'remaining_original_indexes': [plan['recovery_lineage']['continuation_to_parent_index'][i] for i in pending],
        'remaining_runs': len(pending), 'remaining_scheduled_calls': needed,
        'remaining_original_call_authorization': available, 'attempts': attempts,
        'old_allocations_complete': False}


def prepare(continuation, root, supplemental_hours=8, source=None, after=None):
    continuation = Path(continuation).resolve(); root = Path(root).resolve()
    if (ROOT / 'results').resolve() not in root.parents or root.exists() or not 1 <= supplemental_hours <= 12:
        raise ValueError('Use a fresh private root and bounded supplemental wall allowance')
    with (continuation / 'queue.lock').open('a') as old_lock:
        # Registration does no inference and must not interrupt an unrelated live allocation.
        fcntl.flock(old_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        checked = inspect(continuation, source); prior, _ = ancestor(continuation)
        reservations = ROOT / 'results/checkpoint-gates/primary-output-recovery-reservations'
        reservation_path = reservations / (prior['plan_hash'] + '.private.json')
        if reservation_path.exists():
            raise ValueError('Continuation remaining authorization already reserved')
        from primary_long_queue import load_payload
        for index in checked['remaining_continuation_indexes']:
            load_payload(prior, prior['jobs'][index])
        plan = copy.deepcopy(prior)
        plan.update(schema_version='primary-output-recovery-1.0', protocol_version=PROTOCOL, created_utc=utc(),
            jobs=[copy.deepcopy(prior['jobs'][i]) for i in checked['remaining_continuation_indexes']],
            planned_runs=checked['remaining_runs'], planned_calls=checked['remaining_scheduled_calls'],
            max_http_attempts=checked['remaining_original_call_authorization'], max_wall_seconds=supplemental_hours * 3600,
            dependencies={name: sha(ROOT / 'scripts' / name) for name in DEPENDENCIES},
            after=str(Path(after).resolve()) if after else None, max_wait_seconds=96 * 3600,
            max_output_tokens=3072, context_tokens=32768, maximum_history_bytes=96000)
        plan.pop('recovery_lineage', None)
        plan['output_recovery_lineage'] = {'continuation': str(continuation),
            'continuation_source': str(Path(source).resolve()) if source else str(ROOT / 'results/repository-runs' / continuation.name),
            'inspection': checked, 'decision': 'explicit_user_requested_recovery_with_versioned_output_and_schema_amendment',
            'supplemental_wall_seconds': supplemental_hours * 3600,
            'maximum_combined_execution_seconds': checked['cumulative_prior_execution_seconds'] + supplemental_hours * 3600,
            'new_to_original_index': checked['remaining_original_indexes']}
        plan['limitations'].extend(['Protocol3.6 raises output allowance from1536 to3072, closes unbounded extra answer fields and appends an explicit numeric reporting-format contract; task objectives/seed/full history are retained.',
            'Only unfinished assignments enter3.6; output/schema/recovery time confound comparisons with completed3.3 conditions.',
            'All prior completed and failed attempts remain separate; cumulative physical authorization remains original5200 ceiling.'])
        plan['plan_hash'] = digest({k: v for k, v in plan.items() if k != 'plan_hash'})
        reservation = {'continuation_plan_hash': prior['plan_hash'], 'new_root': str(root), 'new_plan_hash': plan['plan_hash'], 'created_utc': utc()}
        reservation['reservation_hash'] = digest(reservation)
        reservations.mkdir(parents=True, exist_ok=True); private_write(reservation_path, reservation)
        root.mkdir(parents=True); (root / 'controller').mkdir()
        for name in DEPENDENCIES:
            shutil.copyfile(ROOT / 'scripts' / name, root / 'controller' / name)
        private_write(root / 'ancestor-evidence.private.json', checked)
        private_write(root / 'primary-output-plan.json', plan)
    validate(root); return plan


def validate(root):
    root = Path(root); plan = json.loads((root / 'primary-output-plan.json').read_text())
    if (plan['plan_hash'] != digest({k: v for k, v in plan.items() if k != 'plan_hash'})
            or plan['source_hash'] != source_fingerprint()
            or any(sha(ROOT / 'scripts' / n) != value or sha(root / 'controller' / n) != value for n, value in plan['dependencies'].items())):
        raise ValueError('Frozen output recovery source or plan changed')
    lineage = plan['output_recovery_lineage']
    if inspect(lineage['continuation'], lineage['continuation_source']) != lineage['inspection']:
        raise ValueError('Ancestor evidence changed after output recovery registration')
    path = ROOT / 'results/checkpoint-gates/primary-output-recovery-reservations' / (lineage['inspection']['continuation_plan_hash'] + '.private.json')
    reservation = json.loads(path.read_text())
    if (reservation.get('reservation_hash') != digest({k: v for k, v in reservation.items() if k != 'reservation_hash'})
            or reservation.get('new_root') != str(root.resolve()) or reservation.get('new_plan_hash') != plan['plan_hash']):
        raise ValueError('Output recovery reservation changed')
    return plan


def recover(root, plan):
    output = ROOT / 'results/repository-runs' / Path(root).name
    done = {}; physical = returned = failed = 0
    for path in sorted(output.glob('job-*/*/events.jsonl')):
        directory = path.parent
        if not verify(directory):
            raise ValueError('Unsealed or corrupt output recovery attempt')
        index = int(directory.parent.name.removeprefix('job-')); job = plan['jobs'][index]
        config = json.loads((directory / 'config.snapshot.json').read_text()); manifest = json.loads((directory / 'manifest.json').read_text())
        if (index < 0 or config.get('registry_freeze_hash') != plan['plan_hash'] or config.get('protocol_version') != PROTOCOL
                or config.get('max_output_tokens') != 3072
                or any(config.get(k) != job[k] for k in ('task_id', 'rounds', 'topology', 'seed', 'defense', 'intervention', 'phase'))):
            raise ValueError('Output recovery assignment mismatch')
        events = [json.loads(x) for x in path.read_text().splitlines()]
        http = sum(e['event_type'] == 'http_attempt' for e in events); responses = sum(e['event_type'] == 'inference_response' for e in events)
        if manifest.get('http_attempts') != http or manifest.get('completed_model_calls') != responses:
            raise ValueError('Output recovery ledger mismatch')
        physical += http; returned += responses
        if manifest['status'] == 'completed':
            if index in done or responses != job['calls']:
                raise ValueError('Duplicate/incomplete output recovery completion')
            done[index] = str(directory)
        else:
            failed += 1
    return done, physical, returned, failed


async def run(root, backend='mock', env_file=None, resume=False, retry_failed=False):
    root = Path(root); plan = validate(root); state_path = root / 'primary-output-state.json'
    if state_path.exists() and not resume:
        raise ValueError('Explicit resume required')
    old = json.loads(state_path.read_text()) if state_path.exists() else {}
    done, physical, returned, failed = recover(root, plan)
    if old.get('backend', backend) != backend or (failed and not retry_failed):
        raise ValueError('Backend change or unreviewed retry')
    elapsed = old.get('execution_seconds', 0)
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('Invalid output recovery execution ledger')
    state = {'status': 'waiting', 'backend': backend, 'worker': 'primary', 'plan_hash': plan['plan_hash'],
        'planned_runs': plan['planned_runs'], 'planned_calls': plan['planned_calls'], 'completed_runs': len(done),
        'physical_calls': physical, 'returned_calls': returned, 'failed_runs': failed, 'execution_seconds': elapsed}
    began = None; waiting = time.monotonic(); last_capacity = 0.; issued = physical
    provider = AttributedMock(); lease = None

    def save(**kw):
        state.update(kw, updated_utc=utc())
        if began is not None:
            state['execution_seconds'] = elapsed + time.monotonic() - began
        atomic(state_path, state)

    def budget():
        if (root / 'STOP').exists():
            raise CallBudgetExhausted('operator_stop')
        if began is not None and elapsed + time.monotonic() - began >= plan['max_wall_seconds']:
            raise CallBudgetExhausted('allocation_wall_budget')
        if source_fingerprint() != plan['source_hash']:
            raise CallBudgetExhausted('frozen_source_changed')
        lineage = plan['output_recovery_lineage']; checked = lineage['inspection']
        if sha(Path(lineage['continuation']) / 'primary-long-state.json') != checked['continuation_state_sha256']:
            raise CallBudgetExhausted('ancestor_state_changed')
        ancestor_plan = json.loads((Path(lineage['continuation']) / 'primary-long-plan.json').read_text())
        if sha(Path(ancestor_plan['recovery_lineage']['parent_queue']) / 'primary-long-state.json') != checked['original_inspection']['parent_state_sha256']:
            raise CallBudgetExhausted('ancestor_state_changed')
        if shutil.disk_usage(ROOT / 'results').free < 1024 ** 3:
            raise CallBudgetExhausted('controller_disk_low')

    async def resources():
        nonlocal last_capacity
        budget()
        if time.monotonic() - last_capacity < 10:
            return
        from remote_worker import execute
        def capacity():
            return next(v['capacity'] for v in execute('primary', 'capacity', ROOT / '.env.primary') if 'capacity' in v)
        start = time.monotonic(); stable = 0; cooling = False
        while True:
            budget(); value = await asyncio.to_thread(capacity); reason = resource_reason(value)
            if reason in {'ram_low_or_unknown', 'gpu_temperature_unknown'}:
                raise CallBudgetExhausted('unknown_or_low_resources')
            if not reason and not cooling_required(value) and not cooling:
                break
            cooling = True; stable = stable + 1 if cooled(value) else 0
            if stable >= 2:
                break
            if time.monotonic() - start > 600:
                raise CallBudgetExhausted('cooling_timeout')
            save(status='cooling'); await asyncio.sleep(10)
        last_capacity = time.monotonic(); save(status='running')

    with (root / 'queue.lock').open('a') as queue_lock:
        fcntl.flock(queue_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if resume:
            receipt = {'schema_version': 'primary-output-resume-1.0', 'created_utc': utc(), 'plan_hash': plan['plan_hash'],
                'prior_physical_calls': physical, 'prior_returned_calls': returned, 'prior_execution_seconds': elapsed,
                'prior_failed_attempts': failed, 'decision': 'explicit_retry_failed' if failed else 'explicit_resume'}
            receipt['receipt_hash'] = digest(receipt)
            receipt_dir = root / 'recovery'; receipt_dir.mkdir(exist_ok=True)
            private_write(receipt_dir / f'decision-{len(list(receipt_dir.glob("decision-*.private.json"))) + 1:06}.private.json', receipt)
        save()
        try:
            while plan['after']:
                budget()
                try:
                    prior_state = json.loads(Path(plan['after']).read_text())
                except FileNotFoundError:
                    prior_state = {'status': 'waiting'}
                if prior_state['status'] == 'completed':
                    break
                if prior_state['status'] in {'stopped', 'failed', 'budget_exhausted'}:
                    raise RuntimeError('Registered preceding allocation stopped')
                if time.monotonic() - waiting >= plan['max_wait_seconds']:
                    raise CallBudgetExhausted('prerequisite_wait_budget')
                save(status='waiting'); await asyncio.sleep(15)
            if backend == 'ollama':
                if env_file is None or Path(env_file).resolve() != ROOT / '.env.primary':
                    raise ValueError('Explicit primary env required')
                env = load_env(Path(env_file), {})
                if env.get('CONTAGION_BASE_URL') != 'http://127.0.0.1:11835':
                    raise ValueError('Primary loopback required')
                proof = validate_readiness(plan['readiness'])
                if proof['readiness_hash'] != plan['readiness_hash']:
                    raise ValueError('Pinned primary readiness changed')
                lease_path = ROOT / 'results/checkpoint-gates/controller-primary.lock'; lease_path.parent.mkdir(parents=True, exist_ok=True)
                lease = lease_path.open('a')
                while True:
                    try:
                        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB); break
                    except BlockingIOError:
                        budget()
                        if time.monotonic() - waiting >= plan['max_wait_seconds']:
                            raise CallBudgetExhausted('primary_lease_wait_budget')
                        save(status='waiting_for_primary_lease'); await asyncio.sleep(5)
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
                    raise ValueError('Pinned primary model unavailable')
                provider.identity.update(model=plan['model'], digest=plan['model_digest'], worker_label='primary')
            began = time.monotonic(); save(status='running')
            from primary_long_queue import load_payload
            for index, job in enumerate(plan['jobs']):
                if index in done:
                    continue
                budget()
                if physical + job['calls'] > plan['max_http_attempts']:
                    raise CallBudgetExhausted('physical_call_budget')
                row, payload = load_payload(plan, job)
                save(job_index=index, rounds=job['rounds'], topology=job['topology'], defense=job['defense'], intervention=job['intervention'])
                directory = await run_case(row, payload, plan, job, provider,
                    ROOT / 'results/repository-runs' / root.name / f'job-{index:03}',
                    before_call=resources if backend == 'ollama' else None, stop_file=root / 'STOP')
                done, physical, returned, failed = recover(root, plan)
                save(completed_runs=len(done), physical_calls=physical, returned_calls=returned, failed_runs=failed)
                finished = json.loads((directory / 'manifest.json').read_text())
                if finished['status'] != 'completed':
                    save(failure_code=finished.get('failure_code')); raise RuntimeError('Output recovery per-run gate failed')
            save(status='completed')
        except BaseException as exc:
            done, physical, returned, failed = recover(root, plan)
            known = {'operator_stop', 'allocation_wall_budget', 'frozen_source_changed', 'ancestor_state_changed',
                     'controller_disk_low', 'prerequisite_wait_budget', 'primary_lease_wait_budget', 'physical_call_budget'}
            value = exc.args[0] if isinstance(exc, CallBudgetExhausted) and exc.args and isinstance(exc.args[0], str) else None
            save(status='stopped', error_type=type(exc).__name__, failure_code=state.get('failure_code') or (value if value in known else 'allocation_or_prerequisite_failure'), completed_runs=len(done), physical_calls=physical,
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
    i = subs.add_parser('inspect'); i.add_argument('--continuation', type=Path, required=True)
    p = subs.add_parser('prepare'); p.add_argument('--continuation', type=Path, required=True); p.add_argument('--root', type=Path, required=True)
    p.add_argument('--supplemental-hours', type=int, default=8); p.add_argument('--after', type=Path)
    r = subs.add_parser('run'); r.add_argument('--root', type=Path, required=True); r.add_argument('--provider', choices=['mock', 'ollama'], default='mock')
    r.add_argument('--env-file', type=Path); r.add_argument('--resume', action='store_true'); r.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args()
    if args.command == 'inspect':
        value = inspect(args.continuation)
        print(json.dumps({k: value[k] for k in ('completed_original_runs', 'continuation_failed_attempts',
            'cumulative_prior_http_attempts', 'remaining_runs', 'remaining_scheduled_calls', 'remaining_original_call_authorization')}, indent=2))
    elif args.command == 'prepare':
        plan = prepare(args.continuation, args.root, args.supplemental_hours, after=args.after)
        print('Registered', plan['planned_runs'], 'unfinished assignments /', plan['planned_calls'], 'calls as', PROTOCOL)
    else:
        state = asyncio.run(run(args.root, args.provider, args.env_file, args.resume, args.retry_failed))
        print(state['status'], state['completed_runs'], '/', state['planned_runs'])
