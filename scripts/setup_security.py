#!/usr/bin/env python3
"""Install this repository's pre-commit hook and pinned isolated hook environments."""
import os
from pathlib import Path
import subprocess
import sys

import certifi

ROOT = Path(__file__).resolve().parents[1]


def tool_env():
    env = dict(os.environ)
    env.setdefault('SSL_CERT_FILE', certifi.where())
    env.setdefault('GOCACHE', str(ROOT / '.cache/go-build'))
    env.setdefault('GOMODCACHE', str(ROOT / '.cache/go-mod'))
    return env


if __name__ == '__main__':
    subprocess.run([sys.executable, '-m', 'pre_commit', 'install', '--install-hooks'],
                   cwd=ROOT, env=tool_env(), check=True)
