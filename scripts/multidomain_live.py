"""Frozen bounded primary allocation for multidisciplinary evidence tasks.

Controller-only inference; no model tools, upstream execution or automatic retries.
Existing protocol5.0 mock dockets and earlier experiment releases stay unchanged.
"""
import argparse
import asyncio
import copy
import fcntl
import json
import math
from pathlib import Path
import shutil
import time

import httpx

from contagion.config import canonical, digest
from contagion.events import EventRecorder, read_events, utc
from contagion.inference import CallBudgetExhausted
from contagion.models import SamplingConfig
from contagion.storage import seal, source_fingerprint, verify, write_json
from contagion.topology import study_adjacency
from multidomain_docket import ARMS, CHALLENGES, DOMAINS, PROTOCOL, RULES, load, private_path, sha
from multidomain_pilot import Mock, Response, parse, request, score
from run_campaign import atomic, cooled, cooling_required, resource_reason
from run_pilot import ROOT, load_env
from run_repository_study import RepositoryProvider

DEPENDENCIES = ('multidomain_live.py', 'multidomain_docket.py', 'multidomain_pilot.py',
                'run_campaign.py', 'run_pilot.py', 'remote_worker.py', 'run_repository_study.py')


def hashes():
    return {name: sha(ROOT / 'scripts' / name) for name in DEPENDENCIES}


def schema():
    result = Response.model_json_schema()
    result['properties']['message']['maxLength'] = 400
    result['$defs']['Claim']['properties']['explanation']['maxLength'] = 160
    result['$defs']['Claim']['properties']['answer']['maxLength'] = 160
    return result


def prepare(root, catalog, model, model_digest, after=None, rounds=15, max_hours=48):
    root = private_path(root)
    if root.exists():
        raise ValueError('Use a fresh immutable allocation')
    if not model or len(model_digest) != 64 or set(model_digest) - set('0123456789abcdef'):
        raise ValueError('Pin a discovered model/digest')
    if type(rounds) is not int or not 5 <= rounds <= 20 or not 1 <= max_hours <= 72:
        raise ValueError('Invalid bounded schedule')
    manifest, payloads, _ = load(catalog)
    checks = []
    for domain in DOMAINS:
        choices = sorted((r for r in manifest['rows'] if r['domain'] == domain and r['split'] == 'development'), key=lambda r: r['id'])
        if not choices:
            raise ValueError('Every domain needs a development precheck')
        checks.append(choices[0])
    evaluation = sorted((r for r in manifest['rows'] if r['split'] == 'evaluation'), key=lambda r: (r['domain'], r['id']))
    if not evaluation:
        raise ValueError('No held-out tasks')
    jobs = []
    for phase, rows, turns in [('integration_precheck', checks, 3), ('evaluation', evaluation, rounds)]:
        for row in rows:
            if len(canonical(payloads[row['id']]).encode()) > 60000:
                raise ValueError('Task context too large')
            for arm in ARMS:
                jobs.append({'task_id': row['id'], 'domain': row['domain'], 'split': row['split'],
                             'phase': phase, 'intervention': arm, 'rounds': turns, 'topology': 'ring',
                             'seed': 41001, 'calls': turns * 5})
    planned = sum(j['calls'] for j in jobs)
    plan = {'schema_version': 'multidomain-live-plan-1.0', 'protocol_version': PROTOCOL,
            'created_utc': utc(), 'worker': 'primary', 'model': model, 'model_digest': model_digest,
            'catalog': str(Path(catalog).resolve()), 'catalog_hash': manifest['catalog_hash'],
            'source_hash': source_fingerprint(), 'dependencies': hashes(), 'jobs': jobs,
            'planned_runs': len(jobs), 'planned_calls': planned, 'max_http_attempts': math.ceil(planned * 1.1),
            'max_execution_seconds': max_hours * 3600, 'max_wait_seconds': 96 * 3600,
            'max_run_seconds': 7200, 'max_output_tokens': 2048, 'context_tokens': 32768,
            'max_history_bytes': 96000, 'after': str(Path(after).resolve()) if after else None,
            'memory_policy': 'original_task_plus_last_two_own_rounds', 'response_schema': schema(),
            'precheck_gate': 'at_least_one_clean_nonunknown_answer_with_existing_citation_per_domain_not_semantic_correctness',
            'limitations': manifest['limitations'] + ['Ring-only allocation cannot identify topology effects.',
                'Reporting pressure and marker adoption remain separate endpoints.',
                'Five development cases are used only for structural feasibility; reference correctness is not a launch criterion.',
                'This allocation is new live evidence; earlier scripted mock results are not empirical findings.']}
    plan['plan_hash'] = digest(plan)
    root.mkdir(parents=True)
    (root / 'controller').mkdir()
    for name in DEPENDENCIES:
        shutil.copyfile(ROOT / 'scripts' / name, root / 'controller' / name)
    write_json(root / 'multidomain-live-plan.json', plan)
    return plan


def validate(root):
    root = private_path(root)
    plan = json.loads((root / 'multidomain-live-plan.json').read_text())
    if plan['plan_hash'] != digest({k: v for k, v in plan.items() if k != 'plan_hash'}):
        raise ValueError('Plan changed')
    if source_fingerprint() != plan['source_hash'] or hashes() != plan['dependencies']:
        raise ValueError('Frozen controller changed')
    if any(sha(root / 'controller' / name) != want for name, want in plan['dependencies'].items()):
        raise ValueError('Archived controller changed')
    manifest, payloads, oracles = load(plan['catalog'])
    if manifest['catalog_hash'] != plan['catalog_hash']:
        raise ValueError('Catalog changed')
    return plan, payloads, oracles


def recover(root, plan):
    done, failures, physical, returned, reserved_seconds = {}, [], 0, 0, 0.
    backends = set()
    for path in sorted((Path(root) / 'runs').glob('job-*/attempt-*')):
        if path.is_symlink() or path.parent.is_symlink() or any(p.is_symlink() for p in path.iterdir()):
            raise ValueError('Unsafe attempt path')
        index = int(path.parent.name.removeprefix('job-'))
        if not 0 <= index < len(plan['jobs']):
            raise ValueError('Unexpected job index')
        job = plan['jobs'][index]
        events = []
        if (path / 'events.jsonl').is_file():
            for line in (path / 'events.jsonl').read_text().splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    break
        attempts = sum(e['event_type'] == 'http_attempt' for e in events)
        responses = sum(e['event_type'] == 'inference_response' for e in events)
        returned += responses
        sealed = (path / 'checksum.sha256').is_file()
        if sealed:
            if not verify(path):
                raise ValueError('Attempt seal failed')
            m = json.loads((path / 'manifest.json').read_text())
            c = json.loads((path / 'config.snapshot.json').read_text())
            if (m['plan_hash'] != plan['plan_hash'] or c['plan_hash'] != plan['plan_hash'] or c['job'] != job
                    or m['completed_model_calls'] != responses or m['http_attempts'] != attempts
                    or c.get('source_hash') != plan['source_hash'] or m.get('source_hash') != plan['source_hash']
                    or c.get('model_identity') != m.get('model_identity')):
                raise ValueError('Attempt provenance/counters mismatch')
            identity = m['model_identity']; backend = identity.get('backend')
            if (backend not in {'mock', 'ollama'} or backend == 'ollama' and
                    (identity.get('model') != plan['model'] or identity.get('digest') != plan['model_digest']
                     or identity.get('worker_label') != 'primary')):
                raise ValueError('Unexpected model identity')
            backends.add(backend)
            physical += attempts
            reserved_seconds += m['duration_seconds']
            if m['status'] == 'completed':
                if index in done or responses != job['calls']:
                    raise ValueError('Duplicate or incomplete completed job')
                artifacts = [(e.get('agent_id'), e['round']) for e in events if e['event_type'] == 'artifact']
                if artifacts != [(f'agent_{a}', r) for r in range(job['rounds']) for a in range(5)]:
                    raise ValueError('Completed artifact coverage mismatch')
                done[index] = path
                continue
            evidence_hash = sha(path / 'checksum.sha256')
        else:
            physical += max(attempts, job['calls'])
            reserved_seconds += plan['max_run_seconds']
            evidence_hash = digest({p.name: sha(p) for p in sorted(path.iterdir()) if p.is_file()})
        failures.append({'attempt': str(path.relative_to(root)), 'evidence_hash': evidence_hash,
                         'sealed': sealed, 'call_debit': attempts if sealed else max(attempts, job['calls'])})
    return {'done': done, 'failures': failures, 'physical_calls': physical, 'returned_calls': returned,
            'execution_debit_seconds': reserved_seconds, 'backends': backends}


def recovery_receipt(root, plan, recovered, retry_failed, prior_execution):
    directory = Path(root) / 'recovery'; directory.mkdir(exist_ok=True)
    previous = None
    for i, path in enumerate(sorted(directory.glob('decision-*.private.json')), 1):
        data = json.loads(path.read_text())
        if (path.name != f'decision-{i:06d}.private.json' or data['previous_sha256'] != previous
                or data['plan_hash'] != plan['plan_hash']
                or data['receipt_hash'] != digest({k: v for k, v in data.items() if k != 'receipt_hash'})):
            raise ValueError('Recovery receipt chain changed')
        previous = sha(path)
    value = {'plan_hash': plan['plan_hash'], 'created_utc': utc(), 'previous_sha256': previous,
             'decision': 'retry_failed' if retry_failed else 'resume', 'retained_failures': recovered['failures'],
             'prior_physical_debit': recovered['physical_calls'], 'prior_execution_debit': prior_execution}
    value['receipt_hash'] = digest(value)
    path = directory / f'decision-{len(list(directory.glob("decision-*.private.json"))) + 1:06d}.private.json'
    write_json(path, value); path.chmod(0o600)


def failure_code(exc):
    if isinstance(exc, CallBudgetExhausted):
        allowed = {'operator_stop', 'allocation_wall_budget', 'run_wall_budget', 'history_budget', 'call_budget',
                   'context_truncation', 'disk_low', 'unknown_or_low_resources', 'cooling_timeout'}
        return exc.args[0] if len(exc.args) == 1 and exc.args[0] in allowed else 'budget_exhausted'
    if isinstance(exc, httpx.HTTPError):
        return 'inference_transport_failure'
    if isinstance(exc, asyncio.TimeoutError):
        return 'inference_timeout'
    return 'structured_or_controller_failure'


async def one_run(path, plan, job, payload, oracle, provider, guard, backend):
    path.mkdir(parents=True)
    identity = provider.identity
    config = {'protocol_version': PROTOCOL, 'plan_hash': plan['plan_hash'], 'job': job,
              'task_id': job['task_id'], 'domain': job['domain'], 'phase': job['phase'],
              'payload_hash': digest(payload), 'oracle_hash': digest(oracle), 'model_identity': identity,
              'source_hash': plan['source_hash'], 'agent_tools': [], 'response_schema': schema(),
              'memory_policy': plan['memory_policy'], 'max_output_tokens': plan['max_output_tokens']}
    write_json(path / 'config.snapshot.json', config)
    log = EventRecorder(path / 'events.jsonl', path.name)
    clock = time.monotonic(); started = utc(); calls = attempts = parse_failures = 0
    graph = study_adjacency('ring', 5); histories = {a: [] for a in graph}; inbox = {a: [] for a in graph}
    final = {}; status = 'completed'; code = None
    def audit(kind, metadata):
        nonlocal attempts
        if kind == 'http_attempt':
            if attempts >= job['calls']:
                raise CallBudgetExhausted('call_budget')
            attempts += 1
        log.emit(kind, metadata=metadata)
    if backend == 'ollama':
        provider.audit = audit
    try:
        for r in range(job['rounds']):
            pending = {a: [] for a in graph}
            for agent in sorted(graph):
                await guard()
                remaining = plan['max_run_seconds'] - (time.monotonic() - clock)
                if remaining <= 0:
                    raise CallBudgetExhausted('run_wall_budget')
                for note in inbox[agent]:
                    log.emit('message_delivered', r, sender_id=note['sender_id'], receiver_id=agent,
                             agent_id=agent, content=note['content'], metadata={'source_round': note['source_round']})
                messages, current = request(payload, histories[agent], inbox[agent], r, job['rounds'])
                # Output form instructions are fixed before outcome collection, not peer authority.
                messages[0]['content'] = RULES + ' Return only the response JSON: claims(question_id,answer,evidence_ids,confidence,explanation), verification_performed, message, optional audit_marker. Keep each explanation under 160 characters and peer message under 400 characters.'
                if len(canonical(messages).encode()) > plan['max_history_bytes']:
                    raise CallBudgetExhausted('history_budget')
                log.emit('inference_requested', r, agent_id=agent, metadata={'messages': copy.deepcopy(messages)})
                if backend == 'mock':
                    response = await provider.chat(copy.deepcopy(messages))
                else:
                    response = await asyncio.wait_for(provider.chat(copy.deepcopy(messages), SamplingConfig(
                        model=plan['model'], seed=job['seed'] + calls, temperature=.2,
                        max_output_tokens=plan['max_output_tokens'], thinking='disabled', response_schema=schema())), timeout=remaining)
                calls += 1
                log.emit('inference_response', r, agent_id=agent, content=response.content, metadata=response.metadata)
                if (response.metadata.get('done_reason') == 'length' or
                        (response.metadata.get('prompt_eval_count') or 0) >= plan['context_tokens'] - plan['max_output_tokens']):
                    raise CallBudgetExhausted('context_truncation')
                try:
                    artifact = parse(response.content, payload)
                except ValueError:
                    parse_failures += 1
                    log.emit('parse_failure', r, agent_id=agent)
                    raise
                final[agent] = score(artifact, payload, oracle)
                log.emit('artifact', r, agent_id=agent, content=canonical(artifact.model_dump()))
                histories[agent].append((r, current, {'role': 'assistant', 'content': response.content}))
                note = artifact.message
                log.emit('message_generated', r, sender_id=agent, content=note)
                if r == 0 and agent == 'agent_0' and job['intervention'] != 'clean':
                    original = note; note += ' ' + CHALLENGES[job['intervention']]
                    log.emit('intervention_applied', r, sender_id=agent, content=note, metadata={'original': original})
                if r < job['rounds'] - 1:
                    for receiver in graph[agent]:
                        pending[receiver].append({'sender_id': agent, 'source_round': r, 'content': note})
            inbox = pending
    except BaseException as exc:
        status = 'budget_exhausted' if isinstance(exc, CallBudgetExhausted) else 'failed'
        code = failure_code(exc)
    finally:
        if backend == 'ollama':
            provider.audit = None
        log.emit('run_finished', metadata={'status': status, 'failure_code': code}); log.close()
    write_json(path / 'outcome.json', {'status': status, 'final_agents': final,
        'semantic_support': 'not_adjudicated', 'intentional_dishonesty': 'not_adjudicated',
        'scientific_status': 'mock_only' if backend == 'mock' else 'recorded_real_inference'})
    write_json(path / 'manifest.json', {'protocol_version': PROTOCOL, 'status': status, 'failure_code': code,
        'started_utc': started, 'ended_utc': utc(), 'duration_seconds': time.monotonic() - clock,
        'completed_model_calls': calls, 'http_attempts': attempts, 'parse_failures': parse_failures,
        'model_identity': identity, 'source_hash': plan['source_hash'], 'plan_hash': plan['plan_hash']})
    seal(path)
    return status


def feasibility(plan, done, payloads, backend):
    checks = [i for i, j in enumerate(plan['jobs']) if j['phase'] == 'integration_precheck']
    if not all(i in done for i in checks):
        raise ValueError('Development matrix incomplete')
    # Scripted mocks establish only shape/routing, never real task feasibility.
    if backend == 'mock':
        return {'status': 'mock_shape_checks_only', 'semantic_correctness': 'not_scored'}
    grounded = {d: 0 for d in DOMAINS}
    for index in checks:
        job = plan['jobs'][index]
        if job['intervention'] != 'clean':
            continue
        payload = payloads[job['task_id']]; ids = {e['id'] for e in payload['evidence']}
        for event in read_events(done[index] / 'events.jsonl'):
            if event['event_type'] != 'artifact' or event['round'] != job['rounds'] - 1:
                continue
            artifact = parse(event['content'], payload)
            grounded[job['domain']] += sum(c.answer.strip().casefold() != 'unknown' and bool(c.evidence_ids)
                and all(e in ids for e in c.evidence_ids) for c in artifact.claims)
    if not all(grounded.values()):
        raise ValueError('Task feasibility indeterminate')
    return {'status': 'structural_feasibility_passed', 'grounded_claims_by_domain': grounded,
            'semantic_correctness': 'not_scored'}


async def run(root, backend='mock', env_file=None, resume=False, retry_failed=False):
    root = Path(root); plan, payloads, oracles = validate(root)
    state_path = root / 'multidomain-live-state.json'
    old = json.loads(state_path.read_text()) if state_path.exists() else {}
    if old and not resume:
        raise ValueError('Explicit resume required')
    if retry_failed and not resume:
        raise ValueError('Retry requires explicit resume')
    if old and old.get('backend') != backend:
        raise ValueError('Cannot change backend')
    recovered = recover(root, plan)
    if recovered['backends'] - {backend}:
        raise ValueError('Recovered attempts use another backend')
    if recovered['failures'] and not retry_failed:
        raise ValueError('Retained failures require explicit retry review')
    elapsed = max(old.get('execution_seconds', 0.), recovered['execution_debit_seconds'])
    if resume:
        recovery_receipt(root, plan, recovered, retry_failed, elapsed)
    state = {'status': 'waiting', 'backend': backend, 'planned_runs': plan['planned_runs'],
             'planned_calls': plan['planned_calls'], 'completed_runs': len(recovered['done']),
             'physical_calls': recovered['physical_calls'], 'returned_calls': recovered['returned_calls'],
             'failed_runs': len(recovered['failures']), 'execution_seconds': elapsed, 'plan_hash': plan['plan_hash']}
    began = None; waiting = time.monotonic(); provider = Mock(); lease = None; last_resources = 0.
    provider.identity = {'backend': 'mock', 'model': 'multidomain-scripted-v1'}
    def save(**kwargs):
        state.update(kwargs, updated_utc=utc())
        if began is not None:
            state['execution_seconds'] = elapsed + time.monotonic() - began
        atomic(state_path, state)
    def budget():
        if (root / 'STOP').exists():
            raise CallBudgetExhausted('operator_stop')
        if began is not None and elapsed + time.monotonic() - began >= plan['max_execution_seconds']:
            raise CallBudgetExhausted('allocation_wall_budget')
        if hashes() != plan['dependencies'] or source_fingerprint() != plan['source_hash']:
            raise ValueError('Frozen controller changed')
    async def guard():
        nonlocal last_resources
        budget()
        if shutil.disk_usage(root).free < 512 * 1024 * 1024:
            raise CallBudgetExhausted('disk_low')
        if backend == 'mock' or time.monotonic() - last_resources < 15:
            return
        from remote_worker import execute
        def capacity():
            return next(m['capacity'] for m in execute('primary', 'capacity', env_file) if 'capacity' in m)
        data = capacity()
        if resource_reason(data) in {'ram_low_or_unknown', 'gpu_temperature_unknown'}:
            raise CallBudgetExhausted('unknown_or_low_resources')
        if resource_reason(data) or cooling_required(data):
            start = time.monotonic(); stable = 0
            while stable < 2:
                budget(); data = capacity()
                if resource_reason(data) in {'ram_low_or_unknown', 'gpu_temperature_unknown'}:
                    raise CallBudgetExhausted('unknown_or_low_resources')
                stable = stable + 1 if cooled(data) else 0
                if time.monotonic() - start > 600:
                    raise CallBudgetExhausted('cooling_timeout')
                if stable < 2:
                    save(status='cooling'); await asyncio.sleep(10)
            save(status='running')
        last_resources = time.monotonic()
    with (root / 'queue.lock').open('a') as queue_lock:
        fcntl.flock(queue_lock, fcntl.LOCK_EX | fcntl.LOCK_NB); save()
        try:
            while plan['after']:
                budget()
                try:
                    previous = json.loads(Path(plan['after']).read_text())
                except FileNotFoundError:
                    previous = {'status': 'waiting'}
                if previous['status'] == 'completed':
                    break
                if previous['status'] in {'stopped', 'failed', 'budget_exhausted'}:
                    raise RuntimeError('Prerequisite requires recovery')
                if time.monotonic() - waiting > plan['max_wait_seconds']:
                    raise RuntimeError('Prerequisite wait exhausted')
                await asyncio.sleep(15)
            if backend == 'ollama':
                if env_file is None or Path(env_file).resolve() != ROOT / '.env.primary':
                    raise ValueError('Explicit primary env required')
                env = load_env(Path(env_file), {})
                if env.get('CONTAGION_BASE_URL') != 'http://127.0.0.1:11835':
                    raise ValueError('Primary loopback tunnel required')
                lock = ROOT / 'results/checkpoint-gates/controller-primary.lock'; lock.parent.mkdir(parents=True, exist_ok=True)
                lease = lock.open('a')
                while True:
                    try:
                        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB); break
                    except BlockingIOError:
                        budget()
                        if time.monotonic() - waiting > plan['max_wait_seconds']:
                            raise RuntimeError('Primary lease wait exhausted')
                        save(status='waiting_for_primary_lease'); await asyncio.sleep(5)
                provider = RepositoryProvider(env['CONTAGION_BASE_URL'], api='ollama', retries=0, timeout=180)
                inventory = await provider.discover()
                if not any(m.get('name') == plan['model'] and m.get('digest') == plan['model_digest'] for m in inventory):
                    raise ValueError('Pinned model unavailable')
                provider.identity.update(model=plan['model'], digest=plan['model_digest'], worker_label='primary')
                if old.get('model_identity') and old['model_identity'] != provider.identity:
                    raise ValueError('Backend identity changed; register new cohort')
                state['model_identity'] = provider.identity
            if backend == 'ollama' and shutil.disk_usage(root).free < plan['planned_calls'] * 128768 + 2 * 1024 ** 3:
                raise CallBudgetExhausted('disk_low')
            began = time.monotonic(); save(status='running'); await guard()
            for index, job in enumerate(plan['jobs']):
                if index in recovered['done']:
                    continue
                if job['phase'] == 'evaluation':
                    gate = feasibility(plan, recovered['done'], payloads, backend)
                    if not (root / 'development-gate.private.json').exists():
                        write_json(root / 'development-gate.private.json', gate)
                await guard()
                if recovered['physical_calls'] + job['calls'] > plan['max_http_attempts']:
                    raise CallBudgetExhausted('call_budget')
                folder = root / 'runs' / f'job-{index:03}'
                folder.mkdir(parents=True, exist_ok=True)
                attempt = 1
                while (folder / f'attempt-{attempt:03}').exists():
                    attempt += 1
                save(status='running', job_index=index, domain=job['domain'], phase=job['phase'])
                result = await one_run(folder / f'attempt-{attempt:03}', plan, job,
                    payloads[job['task_id']], oracles[job['task_id']], provider, guard, backend)
                recovered = recover(root, plan)
                save(completed_runs=len(recovered['done']), physical_calls=recovered['physical_calls'],
                     returned_calls=recovered['returned_calls'], failed_runs=len(recovered['failures']))
                if result != 'completed':
                    raise RuntimeError('Per-run gate failed')
            save(status='completed')
        except BaseException as exc:
            recovered = recover(root, plan)
            save(status='stopped', failure_code=failure_code(exc), completed_runs=len(recovered['done']),
                 physical_calls=recovered['physical_calls'], returned_calls=recovered['returned_calls'],
                 failed_runs=len(recovered['failures']))
            raise
        finally:
            if hasattr(provider, 'close'):
                await provider.close()
            if lease:
                lease.close()
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--root', type=Path, required=True)
    p.add_argument('--catalog', type=Path, required=True); p.add_argument('--model', required=True); p.add_argument('--digest', required=True)
    p.add_argument('--after', type=Path); p.add_argument('--rounds', type=int, default=15); p.add_argument('--max-hours', type=int, default=48)
    r = sub.add_parser('run'); r.add_argument('--root', type=Path, required=True)
    r.add_argument('--provider', choices=['mock', 'ollama'], default='mock'); r.add_argument('--env-file', type=Path)
    r.add_argument('--resume', action='store_true'); r.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args()
    if args.command == 'prepare':
        plan = prepare(args.root, args.catalog, args.model, args.digest, args.after, args.rounds, args.max_hours)
        print('Registered', plan['planned_runs'], 'multidisciplinary runs /', plan['planned_calls'], 'calls; no inference yet.')
    else:
        try:
            state = asyncio.run(run(args.root, args.provider, args.env_file, args.resume, args.retry_failed))
            print(state['status'], state['completed_runs'], '/', state['planned_runs'])
        except Exception as exc:
            parser.exit(1, f'Multidisciplinary allocation stopped ({type(exc).__name__}); logs retained; review before retry.\n')
