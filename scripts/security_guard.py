#!/usr/bin/env python3
"""Read-only publication guard over Git index blobs or nonignored candidate files."""
import argparse
import os
from pathlib import Path
import re
import shutil
import shlex
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
    private = {'.git', '.venv', '.venv-interp', '.venv-worker', '.cache', '.aws', '.ssh', 'results', 'site-dist', 'security-reports', 'logs', 'traces'}
    if any(part.casefold() in private for part in path.parts):
        return True
    if path.name.casefold().startswith('.env') and path.name != '.env.example':
        return True
    if path.name.casefold().endswith(('.redact.txt', '.pem', '.key', '.p12', '.pfx', '.eval')) or path.name.casefold() in {'id_rsa', 'id_ed25519', 'credentials'}:
        return True
    if path.suffix.casefold() in {'.log', '.sqlite', '.sqlite3', '.db', '.safetensors', '.har'}:
        return True
    if re.fullmatch(r'(?:trace|traces|events|request_history|raw_response)(?:[._-].*)?\.json', path.name, re.I):
        return True
    if path.suffix.casefold() == '.jsonl' and not re.fullmatch(r'tests/fixtures/mock_run/[^/]+/events\.jsonl', name):
        return True
    if name.startswith('dashboard/data/') and name not in {'dashboard/data/results.json', 'dashboard/data/research.json', 'dashboard/data/repositories.json', 'dashboard/data/followups.json'} and not re.fullmatch(r'dashboard/data/studies/[a-f0-9]{16}\.json',name):
        return True
    return False


def private_values(root, env):
    # Parse .env as data. Do not source it or echo values.
    sys.path.insert(0, str(ROOT / 'scripts'))
    values = dict(env)
    # Additional private dotenv files may hold judge keys or secondary endpoints.
    # Parse assignments as data without executing or expanding shell syntax.
    for path in sorted(root.glob('.env*')):
        if path.name == '.env.example':
            continue
        if path.is_symlink():
            raise ValueError('Private dotenv must not be a symlink')
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            line = re.sub(r'^export\s+', '', line)
            key, separator, value = line.partition('=')
            if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key.strip()):
                raise ValueError('Invalid private dotenv assignment')
            parts = shlex.split(value, comments=True, posix=True)
            if len(parts) > 1:
                raise ValueError('Invalid private dotenv quoting')
            # Preserve every secret across files even when key names overlap.
            parsed = parts[0] if parts else ''
            values.setdefault(key.strip(), parsed)
            values[f'PRIVATE_{path.name}_{key.strip()}'] = parsed
    values.update(env)
    result = {v for k, v in values.items() if v and len(v) >= 8 and re.search(r'KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL', k, re.I)}
    endpoint = values.get('CONTAGION_BASE_URL')
    if endpoint:
        result.add(endpoint)
        host = urlsplit(endpoint).hostname
        if host and host not in {'localhost', '127.0.0.1', '::1'}:
            result.add(host)
    for key in ['PRIMARY_SERVER_ID','SECONDARY_SERVER_ID','PRIMARY_PROJECT_DIR','SECONDARY_PROJECT_DIR']:
        if values.get(key):result.add(values[key])
    for key in ['PRIMARY_SERVER_ID','SECONDARY_SERVER_ID']:
        if values.get(key):result.add(values[key].rsplit('@',1)[-1])
    for key in ['HOME']:
        if env.get(key):
            result.add(env[key])
    for key, value in values.items():
        if key.startswith('PRIVATE_') and value and re.search(r'URL|HOST|SERVER_ID|PROJECT_DIR', key, re.I):
            result.add(value)
            host = urlsplit(value).hostname if '://' in value else value.rsplit('@', 1)[-1]
            if host and host not in {'localhost', '127.0.0.1', '::1'}:
                result.add(host)
    for path in root.glob('*.redact.txt'):
        if path.is_symlink():
            raise ValueError('Private denylist must not be a symlink')
        result.update(line.strip() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#'))
    result.add(str(root.resolve()))
    for index, value in enumerate(sorted(result)):
        values[f'PRIVATE_REDACTION_SECRET_{index}'] = value
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


def source_configuration_values(known,values):
    """Public service/loopback examples are not secrets in source; data stays strict."""
    credentials={v for k,v in values.items() if v and not k.startswith('PRIVATE_REDACTION_SECRET_') and re.search(r'KEY|TOKEN|PASSWORD|CREDENTIAL',k,re.I)}
    def public(value):
        if value in credentials:return False
        if value in {'openrouter.ai','localhost','127.0.0.1','::1'}:return True
        try:parsed=urlsplit(value)
        except ValueError:return False
        if parsed.username or parsed.password or parsed.query or parsed.fragment:return False
        return parsed.scheme in {'http','https'} and (parsed.hostname in {'localhost','127.0.0.1','::1'} or parsed.scheme=='https' and parsed.hostname=='openrouter.ai' and parsed.path.rstrip('/')=='/api/v1')
    return {v for v in known if not public(v)}


def check(root, mode, scan=False, env=None):
    root = Path(root).resolve()
    known, values = private_values(root, dict(os.environ) if env is None else env)
    from scan_privacy import findings as privacy_findings
    blobs, findings = {}, []
    source_known=source_configuration_values(known,values)
    for name in candidates(root, mode):
        if privacy_findings(name):
            findings.append((name, 'private identifier in filename'))
            continue
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
        candidate_known=known if name.startswith('dashboard/data/') else source_known
        if any(value.encode() in data or value in name for value in candidate_known):
            findings.append((name, 'known private configuration value'))
            continue
        from scan_privacy import scan_blob
        try:
            privacy = scan_blob(data, public=name.startswith('dashboard/data/'), known=candidate_known)
        except (UnicodeError, ValueError):
            findings.append((name, 'privacy lint could not validate text input'))
            continue
        if privacy:
            findings.append((name, 'privacy lint: ' + ', '.join(sorted(privacy))))
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
    followups=blobs.get('dashboard/data/followups.json')
    if followups is not None:
        try:
            from followup_publication import validate
            with tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'followups.json';path.write_bytes(followups);validate(path,values)
        except Exception:findings.append(('dashboard/data/followups.json','follow-up schema/privacy validation failed'))
    repository=blobs.get('dashboard/data/repositories.json')
    if repository is not None:
        try:
            from repository_publication import validate_repository_snapshot
            with tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'repositories.json';path.write_bytes(repository);validate_repository_snapshot(path,values)
        except Exception:findings.append(('dashboard/data/repositories.json','repository metadata schema/privacy validation failed'))
    research = blobs.get('dashboard/data/research.json')
    if research is not None:
        try:
            from contagion.research_publication import validate_research_snapshot
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'research.json'
                path.write_bytes(research)
                snapshot=validate_research_snapshot(path, env=values)
                if snapshot.suite is not None or snapshot.resources is not None:
                    raise ValueError('Private operational telemetry cannot be committed')
        except Exception:
            findings.append(('dashboard/data/research.json', 'public research schema/privacy validation failed'))
    for name,data in blobs.items():
        if name.startswith('dashboard/data/studies/'):
            try:
                from contagion.research_publication import validate_study_detail
                with tempfile.TemporaryDirectory() as temp:
                    path=Path(temp)/Path(name).name;path.write_bytes(data)
                    validate_study_detail(path,env=values)
            except Exception:
                findings.append((name,'study detail privacy/schema validation failed'))
    for name, reason in findings:
        safe = '[redacted path]' if any(value in name for value in known) or privacy_findings(name) else ascii(name)
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
