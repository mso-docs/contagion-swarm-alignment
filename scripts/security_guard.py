#!/usr/bin/env python3
"""Read-only publication guard over Git index blobs or nonignored candidate files."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 5 * 1024 * 1024


def git(root, *args):
    return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True).stdout


def candidates(root, mode):
    args = ('diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z') if mode == 'staged' else (
        'ls-files', '--cached', '--others', '--exclude-standard', '-z')
    return sorted({p.decode('utf-8') for p in git(root, *args).split(b'\0') if p})


def blocked_path(name):
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or any(ord(c) < 32 for c in name):
        return True
    private = {'.git', '.venv', '.cache', '.aws', '.ssh', 'results', 'site-dist', 'security-reports'}
    if any(part.casefold() in private for part in path.parts):
        return True
    if path.name.casefold().startswith('.env') and path.name != '.env.example':
        return True
    if path.name.endswith(('.redact.txt', '.pem', '.key', '.p12', '.pfx', '.eval')) or path.name in {'id_rsa', 'id_ed25519', 'credentials'}:
        return True
    if path.suffix == '.jsonl' and not re.fullmatch(r'tests/fixtures/mock_run/[^/]+/events\.jsonl', name):
        return True
    if name.startswith('dashboard/data/') and name != 'dashboard/data/results.json':
        return True
    return False


def private_values(root, env):
    # Parse .env as data. Do not source it or echo values.
    sys.path.insert(0, str(ROOT / 'scripts'))
    from run_pilot import load_env
    values = load_env(root / '.env', env)
    result = {v for k, v in values.items() if v and len(v) >= 8 and re.search(r'KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL', k, re.I)}
    endpoint = values.get('CONTAGION_BASE_URL')
    if endpoint:
        result.add(endpoint)
        host = urlsplit(endpoint).hostname
        if host and host not in {'localhost', '127.0.0.1', '::1'}:
            result.add(host)
    for key in ['HOME']:
        if env.get(key):
            result.add(env[key])
    result.add(str(root.resolve()))
    return result, values


def read_candidate(root, name, mode):
    if mode == 'staged':
        stage = git(root, 'ls-files', '--stage', '--', name).split(b' ', 1)[0]
        if stage not in {b'100644', b'100755'}:
            raise ValueError('symlinks and submodules are not approved publication inputs')
        return git(root, 'show', f':{name}')
    path = root / name
    if path.is_symlink() or root.resolve() not in path.resolve().parents:
        raise ValueError('symlink or external path')
    return path.read_bytes()


def check(root, mode, scan=False, env=None):
    root = Path(root).resolve()
    known, values = private_values(root, dict(os.environ) if env is None else env)
    blobs, findings = {}, []
    for name in candidates(root, mode):
        if blocked_path(name):
            findings.append((name, 'private or unapproved publication path'))
            continue
        if mode == 'worktree' and not (root / name).exists() and not (root / name).is_symlink():
            continue
        try:
            data = read_candidate(root, name, mode)
        except ValueError:
            findings.append((name, 'unapproved file type'))
            continue
        if len(data) > MAX_BYTES:
            findings.append((name, 'file exceeds 5 MiB review limit'))
            continue
        if any(value.encode() in data or value in name for value in known):
            findings.append((name, 'known private configuration value'))
            continue
        blobs[name] = data
    # Validate the actual index version of public data, not an unstaged clean copy.
    public = blobs.get('dashboard/data/results.json')
    if public is not None:
        try:
            from contagion.publication import validate_snapshot
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'public.json'
                path.write_bytes(public)
                validate_snapshot(path, env=values)
        except Exception:
            findings.append(('dashboard/data/results.json', 'public schema/privacy validation failed'))
    for name, reason in findings:
        safe = '[redacted path]' if any(value in name for value in known) else ascii(name)
        print(f'Blocked {safe}: {reason}', file=sys.stderr)
    if findings:
        return 1
    if scan:
        binary = shutil.which('gitleaks')
        if not binary:
            raise ValueError('Gitleaks is unavailable; run through the installed pre-commit hook environment')
        with tempfile.TemporaryDirectory() as temp:
            for name, data in blobs.items():
                target = Path(temp) / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            result = subprocess.run([binary, 'dir', temp, '--redact=100', '--no-banner',
                                     '--config', str(root / '.gitleaks.toml'), '--ignore-gitleaks-allow',
                                     '--timeout=120'], cwd=root, check=False)
            if result.returncode:
                return result.returncode
    print(f'Publication guard passed: {len(blobs)} {mode} candidate files; no files staged or modified.')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['staged', 'worktree'], required=True)
    parser.add_argument('--gitleaks', action='store_true')
    args = parser.parse_args()
    try:
        raise SystemExit(check(ROOT, args.mode, args.gitleaks))
    except Exception as exc:
        print(f'Publication guard could not complete ({type(exc).__name__}); commit blocked.', file=sys.stderr)
        raise SystemExit(1) from None
