#!/usr/bin/env python3
"""Private, read-only terminal experiment monitor. Never writes public assets."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from contagion.storage import verify
from run_pilot import ROOT


def plan_runs(suite, base):
    total = 0
    for job in suite['jobs']:
        path = Path(job['plan'])
        plan = json.loads((path if path.is_absolute() else base / path).read_text())
        per_run = 5 if plan['research_question'] == 'rq3' else plan['agent_count'] * plan['rounds']
        total += job['calls'] // per_run
    return total


def local_studies(sources):
    rows, pending, seen = [], 0, set()
    pending_calls=pending_attempts=0
    pending_starts=[];pending_updates=[];pending_seconds=0
    for source in sources:
        if not source.is_dir():
            raise ValueError('Study directory missing')
        for path in source.rglob('config.snapshot.json'):
            directory = path.parent.resolve()
            if directory in seen:
                continue
            seen.add(directory)
            if not (directory / 'checksum.sha256').is_file():
                pending += 1
                times=[]
                journal=directory/'events.jsonl'
                if journal.exists():
                    for line in journal.read_text().splitlines():
                        try:event=json.loads(line)
                        except ValueError:break  # An in-progress tail is provisional, never repaired.
                        pending_calls+=event.get('event_type')=='inference_response'
                        pending_attempts+=event.get('event_type')=='http_attempt'
                        if event.get('timestamp_utc'):times.append(datetime.fromisoformat(event['timestamp_utc']))
                if times:
                    pending_starts.append(min(times));pending_updates.append(max(times))
                    pending_seconds+=max(0,(datetime.now(timezone.utc)-min(times)).total_seconds())
                continue
            if not verify(directory):
                raise ValueError('Study integrity check failed')
            rows.append(json.loads((directory / 'manifest.json').read_text()))
    done = sum(r['status'] == 'completed' for r in rows)
    starts = [datetime.fromisoformat(r['started_utc']) for r in rows]+pending_starts
    ends = [datetime.fromisoformat(r['ended_utc']) for r in rows]
    end = datetime.now(timezone.utc) if pending else max(ends, default=None)
    return {'status': 'unsealed_attempts_present' if pending else 'no_active_attempt_observed',
            'completed_runs': done, 'failed_runs': len(rows) - done, 'unsealed_runs': pending,
            'physical_calls': pending_attempts+sum(r.get('http_attempts', r.get('completed_model_calls', 0)) for r in rows),
            'measured_calls': pending_calls+sum(r.get('completed_model_calls', 0) for r in rows),
            'provisional_returned_calls':pending_calls,
            'recorded_run_seconds': pending_seconds+sum(r.get('duration_seconds', 0) for r in rows),
            'elapsed_seconds': (end - min(starts)).total_seconds() if starts and end else 0,
            'updated_utc': max([r['ended_utc'] for r in rows]+[t.isoformat() for t in pending_updates],default=None)}


def estimates(row):
    seconds = row.get('recorded_run_seconds', 0)
    calls = row.get('measured_calls', 0)
    planned = row.get('planned_calls')
    rate = calls / seconds if calls > 0 and seconds > 0 else None
    remaining = max(0, planned - row.get('scheduled_completed_calls',row.get('physical_calls', 0))) if planned is not None else None
    work = remaining / rate if rate and remaining is not None else None
    updated = row.get('updated_utc')
    age = max(0, time.time() - datetime.fromisoformat(updated).timestamp()) if updated else None
    # Never promise a finish time for paused/stopped/unknown workers.
    running = row.get('status') == 'running' and age is not None and age <= 300
    return {**row, 'status_age_seconds': age, 'calls_per_minute': rate * 60 if rate else None,
            'estimated_remaining_work_seconds': work,
            'estimated_total_work_seconds': seconds + work if work is not None else None,
            'estimated_finish_utc': datetime.fromtimestamp(time.time() + work, timezone.utc).isoformat()
            if running and work is not None else None}


def duration(value):
    if value is None:
        return 'N/A'
    seconds = max(0, int(value))
    return f'{seconds // 3600}h {(seconds % 3600) // 60:02}m {seconds % 60:02}s'


def benchmark_campaign_status(root):
    root=Path(root);large=(root/'primary-large-plan.json').is_file()
    plan=json.loads((root/('primary-large-plan.json' if large else 'primary-long-plan.json')).read_text())
    path=root/('primary-large-state.json' if large else 'primary-long-state.json')
    state=json.loads(path.read_text()) if path.exists() else {'status':'waiting'}
    source=ROOT/'results/repository-runs'/root.name
    measured=local_studies([source]) if source.is_dir() else {}
    updates=[v for v in [state.get('updated_utc'),measured.get('updated_utc')] if v]
    completed=sum(json.loads(p.read_text())['completed_model_calls'] for p in source.rglob('manifest.json')
                  if (p.parent/'checksum.sha256').is_file() and json.loads(p.read_text())['status']=='completed')
    row={**measured,'status':state['status'],'planned_runs':plan['planned_runs'],'planned_calls':plan['planned_calls'],
         'scheduled_completed_calls':completed,'updated_utc':max(updates) if updates else None,
         'registered_execution_cap_seconds':plan['max_wall_seconds'],'phase':state.get('phase','waiting')}
    return estimates(row)


def render(label, row):
    attempts = row.get('completed_runs', 0) + row.get('failed_runs', 0)
    print(f'\n{label} | {row.get("status", "unknown")} | checked {datetime.now(timezone.utc).strftime("%H:%M:%S UTC")}')
    print(f'  Runs: {attempts} sealed / {row.get("planned_runs") or "unknown"} planned '
          f'({row.get("completed_runs", 0)} completed, {row.get("failed_runs", 0)} failed/exhausted, '
          f'{row.get("unsealed_runs", "unknown")} unsealed)')
    print(f'  Calls: {row.get("physical_calls", 0):,} attempted / {row.get("planned_calls") or "unknown"} planned')
    print(f'  Recorded run time: {duration(row.get("recorded_run_seconds"))} | '
          f'Elapsed window: {duration(row.get("elapsed_seconds"))}')
    rate = row.get('calls_per_minute')
    print(f'  Throughput: {f"{rate:.1f} returned calls/min" if rate else "N/A"} | '
          f'Remaining work estimate: {duration(row.get("estimated_remaining_work_seconds"))}')
    print(f'  Total work estimate: {duration(row.get("estimated_total_work_seconds"))} | '
          f'Finish estimate: {row.get("estimated_finish_utc") or "N/A (paused, stale or not confirmed running)"}')
    print(f'  Last worker update: {row.get("updated_utc") or "unknown"} | age: {duration(row.get("status_age_seconds"))}')
    print('  Estimates use recorded runs; exclude future pauses and may change with model/task/swarm size.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, action='append', default=[])
    parser.add_argument('--suite', type=Path, action='append', default=[])
    parser.add_argument('--campaign', type=Path, action='append', default=[])
    parser.add_argument('--remote', choices=['secondary'], help='Read secondary status over existing SSH; never accesses primary')
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--planned-runs', type=int)
    parser.add_argument('--planned-calls', type=int)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--interval', type=int, default=30)
    parser.add_argument('--json', action='store_true', help='Numeric private status for other local tools')
    args = parser.parse_args()
    if not (args.study or args.suite or args.campaign or args.remote):
        parser.error('Select --study, --suite, --campaign or --remote secondary')
    if args.interval < 5 or any(n is not None and n <= 0 for n in [args.planned_runs, args.planned_calls]):
        parser.error('Interval must be >=5 seconds and planned totals must be positive')
    while True:
        results = []
        try:
            if args.study:
                row = local_studies(args.study)
                row.update(planned_runs=args.planned_runs, planned_calls=args.planned_calls)
                results.append(('Local studies', estimates(row)))
            for number, root in enumerate(args.campaign,1):
                if (root/'primary-large-plan.json').is_file() or (root/'primary-long-plan.json').is_file():
                    results.append((f'Primary benchmark campaign {number}',benchmark_campaign_status(root)))
                    continue
                campaign=json.loads((root/'campaign.json').read_text())
                if not (root/'state.json').exists() and (root/'overnight.json').exists():
                    supervisor=json.loads((root/'overnight.json').read_text())
                    source=ROOT/'results/repository-runs'/root.name
                    measured=local_studies([source]) if source.is_dir() else {}
                    row={**measured,'status':supervisor['status'],'planned_calls':supervisor['planned_repository_calls'],'planned_runs':6,
                         'updated_utc':max(supervisor['updated_utc'],measured.get('updated_utc') or supervisor['updated_utc'])}
                    results.append((f'Repository prechecks ({supervisor["phase"]}); {campaign["planned_calls"]} campaign calls queued',estimates(row)))
                    continue
                state=json.loads((root/'state.json').read_text())
                measured=local_studies([Path(campaign['run_root'])])
                planned_runs=sum(len(j['plan']['families'])*len(j['plan']['case_indices'])*len(j['plan']['seeds'])*len(j['plan']['topologies'])*len(j['plan']['interventions']) for j in campaign['jobs'])
                completed_calls=0
                for manifest in Path(campaign['run_root']).rglob('manifest.json'):
                    data=json.loads(manifest.read_text())
                    if data['status']=='completed':completed_calls+=data['completed_model_calls']
                row={**measured,**{k:state[k] for k in ['status','physical_calls','completed_runs','failed_runs','updated_utc'] if k in state},
                     'planned_runs':planned_runs,'planned_calls':campaign['planned_calls'],'scheduled_completed_calls':completed_calls}
                results.append((f'Campaign {number}',estimates(row)))
            for number, root in enumerate(args.suite, 1):
                state = json.loads((root / 'state.json').read_text())
                suite = json.loads((root / 'suite.json').read_text())
                measured = local_studies([root / 'runs'])
                state.update({k: measured[k] for k in ['recorded_run_seconds', 'measured_calls', 'unsealed_runs']})
                state['planned_runs'] = plan_runs(suite, Path.cwd())
                # Only allowlisted operational fields leave this reader.
                keys = ['status', 'physical_calls', 'planned_calls', 'completed_runs', 'failed_runs',
                        'recorded_run_seconds', 'measured_calls', 'unsealed_runs', 'planned_runs',
                        'elapsed_seconds', 'updated_utc']
                results.append((f'Local suite {number}', estimates({k: state[k] for k in keys if k in state})))
            if args.remote:
                from remote_worker import execute
                messages = execute('secondary', 'suite-status', args.env_file)
                status = next(m['suite_status'] for m in messages if 'suite_status' in m)
                # Drop task/model labels and arbitrary strings from the private view too.
                keys = ['status', 'physical_calls', 'planned_calls', 'completed_runs', 'failed_runs',
                        'recorded_run_seconds', 'measured_calls', 'unsealed_runs', 'planned_runs', 'elapsed_seconds', 'updated_utc']
                results.append(('Secondary', estimates({k: status[k] for k in keys if k in status})))
            if args.json:
                print(json.dumps(dict(results)), flush=True)
            else:
                if args.watch and sys.stdout.isatty():
                    print('\033[2J\033[H', end='')
                print('CONTAGION PRIVATE PROGRESS — no public export or inference calls')
                for label, row in results:
                    render(label, row)
                sys.stdout.flush()
        except Exception as exc:
            print(f'Progress unavailable ({type(exc).__name__}); no private paths or trace content printed.', file=sys.stderr)
            if not args.watch:
                return 1
        if not args.watch:
            return 0
        time.sleep(args.interval)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        pass
