#!/usr/bin/env python3
"""Inspect or initialize a project-local worker; no sudo, services or SSH."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def inventory():
    disk = shutil.disk_usage(ROOT)
    try:
        memory = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
    except (ValueError, OSError, AttributeError):
        memory = None
    return {'system': platform.system(), 'architecture': platform.machine(),
            'python': platform.python_version(), 'cpu_count': os.cpu_count(),
            'memory_gib': round(memory / 2**30, 1) if memory else None,
            'free_disk_gib': round(disk.free / 2**30, 1),
            'nvidia_smi_available': shutil.which('nvidia-smi') is not None,
            'docker_available': shutil.which('docker') is not None,
            'ollama_available': shutil.which('ollama') is not None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Install isolated dependencies after inventory')
    parser.add_argument('--role', choices=['controller', 'neural', 'both'], default='controller')
    args = parser.parse_args(argv)
    print(json.dumps(inventory(), indent=2), flush=True)
    if not args.install:
        return 0
    if sys.platform != 'linux' or sys.version_info < (3, 11):
        parser.error('Worker installation requires Linux and Python 3.11 or later')
    # Fail before any install if an interpreter cannot create virtual environments.
    if args.role in {'controller', 'both'}:
        environment = ROOT / '.venv-worker'
        if environment.exists():
            parser.error('.venv-worker already exists; use its interpreter or choose a fresh project directory')
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / 'bin/python'
        subprocess.run([str(python), '-m', 'pip', 'install', '--upgrade', '-r', str(ROOT / 'requirements-bootstrap.txt')], check=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '-e', str(ROOT) + '[test]'], check=True)
        subprocess.run([str(python), '-m', 'pip', 'check'], check=True)
        subprocess.run([str(python), '-m', 'pytest', '-q'], cwd=ROOT, check=True)
        # No credentials or local paths in the package version inventory.
        packages = subprocess.run([str(python), '-m', 'pip', 'list', '--format=json'],
                                  check=True, capture_output=True, text=True)
        directory = ROOT / 'results/worker-setup'
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / 'controller-packages.json').open('x') as stream:
            stream.write(packages.stdout)
    if args.role in {'neural', 'both'}:
        subprocess.run([sys.executable, str(ROOT / 'scripts/setup_interpretability.py')], cwd=ROOT, check=True)
    print('Project-local setup complete. No inference service, firewall or credentials changed.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'Worker setup stopped ({type(exc).__name__}); inspect private install diagnostics.', file=sys.stderr)
        raise SystemExit(1) from None
