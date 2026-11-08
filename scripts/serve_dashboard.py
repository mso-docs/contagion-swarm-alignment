#!/usr/bin/env python3
"""Loopback-only dashboard with automatic sealed-log export and no-cache responses."""
import argparse
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import threading
import sys
import time
from urllib.parse import urlsplit

from run_pilot import ROOT
from security_guard import private_values
from watch_dashboard import publish

ASSETS = {'/', '/index.html', '/app.js', '/style.css', '/widgets.js',
          '/data/results.json', '/data/research.json', '/data/repositories.json'}


DERIVED_SIGNATURE=None


def sync_derived(output,env):
    global DERIVED_SIGNATURE
    from contagion.research_publication import make_research_snapshot,validate_research_snapshot
    from scan_privacy import scan_blob
    monitors=sorted(set((ROOT/'results/monitors').rglob('monitor.json'))|set((ROOT/'results/campaigns').rglob('monitor.json')))
    seals=sorted((ROOT/'results/neural').rglob('checksums.json'))
    signature=tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in [*monitors,*seals])
    if signature==DERIVED_SIGNATURE or not output.is_file():return
    current=validate_research_snapshot(output,env=env)
    monitor_rows={json.dumps(r.model_dump(),sort_keys=True):r for r in current.monitor}
    neural_rows={r.id:r for r in current.neural}
    for path in monitors:
        raw=json.loads(path.read_text())
        mask_seeds={r.get('monitor_seed') for r in raw.get('observations',[]) if r.get('monitor_seed') is not None}
        fresh=make_research_snapshot(monitor_source=path,env=env)
        for row in fresh.monitor:
            if row.monitor_seed is None and len(mask_seeds)==1:row.monitor_seed=next(iter(mask_seeds))
            unknown=row.model_copy(update={'monitor_seed':None})
            monitor_rows.pop(json.dumps(unknown.model_dump(),sort_keys=True),None)
            monitor_rows[json.dumps(row.model_dump(),sort_keys=True)]=row
    for seal in seals:
        fresh=make_research_snapshot(neural_sources=[seal.parent],env=env)
        neural_rows.update({r.id:r for r in fresh.neural})
    from contagion.events import utc
    updated=current.model_copy(update={'monitor':list(monitor_rows.values()),'neural':list(neural_rows.values()),
        'suite':None,'resources':None,'generated_utc':utc()})
    temporary=output.with_suffix('.tmp');temporary.write_text(updated.model_dump_json(indent=2)+'\n')
    validate_research_snapshot(temporary,env=env)
    if scan_blob(temporary.read_bytes(),public=True):raise ValueError('Derived evidence privacy lint failed')
    temporary.replace(output);DERIVED_SIGNATURE=signature


def refresh(sources, output, env, state):
    try:
        changed, count = publish(sources, output, env, include_text=True)
        sync_derived(output,env)
        from repository_publication import export_repository_runs
        repository=export_repository_runs(ROOT/'results/repository-runs',output.parent/'repositories.json',env)
        state['repository_runs']=len(repository.runs)
        from contagion.research_publication import validate_research_snapshot
        index=validate_research_snapshot(output,env=env)
        state.update(status='ok', studies=count, neural_captures=len(index.neural), monitor_summaries=len(index.monitor), checked_epoch=time.time(), error=None)
        if changed:
            print(f'Local dashboard synchronized: {count} sealed study attempts.', flush=True)
    except Exception as exc:
        state.update(status='blocked', checked_epoch=time.time(), error=type(exc).__name__)
        print(f'Dashboard synchronization blocked ({type(exc).__name__}); prior validated data retained.', flush=True)


def merge_secondary(output, staging, env):
    """Merge only sanitized complete remote indexes; no raw logs or progress."""
    from contagion.research_publication import validate_research_snapshot, validate_study_detail
    from scan_privacy import scan_blob
    remote_path = staging / 'data/research.json'
    if not remote_path.is_file():
        return
    remote = validate_research_snapshot(remote_path, env=env)
    current = validate_research_snapshot(output, env=env)
    merged = {r.id: r for r in current.studies}
    merged.update({r.id: r for r in remote.studies})
    rows = sorted(merged.values(), key=lambda r: r.id)
    if current.studies == rows:
        return
    for row in remote.studies:
        if row.detail_file:
            source = staging / row.detail_file
            validate_study_detail(source, env=env)
            if scan_blob(source.read_bytes(), public=True):
                raise ValueError('Remote detail privacy lint failed')
            target = output.parent / 'studies' / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix('.tmp')
            shutil.copyfile(source, temporary)
            temporary.replace(target)
    from contagion.events import utc
    combined = current.model_copy(update={'studies': rows, 'generated_utc': utc(), 'suite': None, 'resources': None})
    temporary = output.with_suffix('.tmp')
    temporary.write_text(combined.model_dump_json(indent=2)+'\n')
    validate_research_snapshot(temporary, env=env)
    if scan_blob(temporary.read_bytes(), public=True):
        raise ValueError('Remote summary privacy lint failed')
    temporary.replace(output)


def sync_secondary_neural(env_file,execute=None):
    if execute is None:
        from remote_worker import execute
    fetched=0
    for _ in range(8):
        messages=execute('secondary','trained-fetch',env_file)
        if not any(m.get('phase')=='capture_fetched' for m in messages):break
        fetched+=1
    return fetched


def handler_type(directory, state):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)
        def end_headers(self):
            self.send_header('Cache-Control', 'no-store, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('X-Content-Type-Options', 'nosniff')
            super().end_headers()
        def do_GET(self):
            path = urlsplit(self.path).path
            if re.fullmatch(r'/__private_repository/[a-f0-9]{16}',path):
                host=urlsplit('http://'+self.headers.get('Host',''))
                if host.hostname not in {'127.0.0.1','localhost'} or host.port!=self.server.server_port or host.username or host.password:
                    self.send_error(403);return
                try:
                    from repository_publication import private_detail
                    _,env=private_values(ROOT,dict(os.environ))
                    data=json.dumps(private_detail(ROOT/'results/repository-runs',path.rsplit('/',1)[-1],env)).encode()
                    self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
                except Exception:self.send_error(404)
                return
            if path == '/__local_status':
                revision = hashlib.sha256(b''.join((directory/name).read_bytes() for name in
                    ['index.html', 'app.js', 'style.css', 'widgets.js'])).hexdigest()[:16]
                data = json.dumps({**state, 'asset_revision': revision}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if path not in ASSETS and not re.fullmatch(r'/data/studies/[a-f0-9]{16}\.json', path):
                self.send_error(404)
                return
            target = directory / ('index.html' if path == '/' else path.lstrip('/'))
            if target.is_symlink() or directory.resolve() not in target.resolve().parents:
                self.send_error(404)
                return
            super().do_GET()
        def do_HEAD(self):
            self.send_error(405)
        def log_message(self, *_):
            pass  # Do not echo URLs or arbitrary request content.
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', action='append', type=Path)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--interval', type=int, default=15)
    parser.add_argument('--sync-secondary', action='store_true', help='Poll sanitized secondary suite snapshots every 60 seconds; never primary')
    args = parser.parse_args()
    if args.interval < 5 or not 1024 <= args.port <= 65535:
        parser.error('Use interval >=5 seconds and an unprivileged valid port')
    sources = args.study or [ROOT / 'results/studies']
    _, env = private_values(ROOT, dict(os.environ))
    state = {'status': 'starting', 'checked_epoch': None, 'studies': 0, 'error': None}
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_type(ROOT / 'dashboard', state))
    stop = threading.Event()
    boot_revision=hashlib.sha256(b''.join(p.read_bytes() for p in [Path(__file__),ROOT/'scripts/watch_dashboard.py',ROOT/'scripts/repository_publication.py',*sorted((ROOT/'src/contagion').glob('*.py'))])).hexdigest()
    def worker():
        last_remote=0;pending_revision=None
        while not stop.is_set():
            revision=hashlib.sha256(b''.join(p.read_bytes() for p in [Path(__file__),ROOT/'scripts/watch_dashboard.py',ROOT/'scripts/repository_publication.py',*sorted((ROOT/'src/contagion').glob('*.py'))])).hexdigest()
            if revision!=boot_revision:
                if pending_revision==revision:
                    print('Reloading local dashboard for updated schema support.',flush=True)
                    os.execv(sys.executable,[sys.executable,*sys.argv])
                pending_revision=revision
            if args.sync_secondary and time.monotonic()-last_remote>=60:
                last_remote=time.monotonic()
                try:
                    from remote_worker import execute
                    staging=ROOT/'results/dashboard-remote-staging'
                    execute('secondary','suite-sync',ROOT/'.env',public_target=staging)
                    merge_secondary(ROOT/'dashboard/data/research.json',staging,env)
                    state['secondary_sync']='ok'
                except Exception as exc:
                    state['secondary_sync']='unavailable: '+type(exc).__name__
                try:
                    sync_secondary_neural(ROOT/'.env')
                    state['secondary_neural_sync']='ok'
                except Exception as exc:
                    state['secondary_neural_sync']='unavailable: '+type(exc).__name__
            refresh(sources, ROOT / 'dashboard/data/research.json', env, state)
            stop.wait(args.interval)
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    print(f'Local dashboard: http://127.0.0.1:{args.port}/#research — automatic log sync; no automatic Git push.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
