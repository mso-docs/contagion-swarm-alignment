#!/usr/bin/env python3
"""Audit tracked AND untracked nonignored candidates without staging any files."""
import subprocess
import sys

from security_guard import ROOT, candidates
from setup_security import tool_env

if __name__ == '__main__':
    files = [name for name in candidates(ROOT, 'worktree') if (ROOT / name).exists() or (ROOT / name).is_symlink()]
    result = subprocess.run([sys.executable, '-m', 'pre_commit', 'run', '--hook-stage', 'manual',
                             '--files', *files], cwd=ROOT, env=tool_env(), check=False)
    raise SystemExit(result.returncode)
