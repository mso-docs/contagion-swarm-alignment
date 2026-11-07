#!/usr/bin/env python3
"""Set up an isolated TransformerLens worker; never changes a remote host."""
import argparse
import platform
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env',type=Path,default=ROOT/'.venv-interp')
    args=parser.parse_args()
    if sys.platform=='darwin' and platform.machine()=='x86_64':
        parser.exit(2,'Unsupported local runtime: TransformerLens 4 needs torch>=2.6, unavailable for this Intel macOS interpreter. Use the prepared Linux CPU container/workflow or an operator-approved Linux worker. No legacy/insecure fallback installed.\n')
    if sys.version_info<(3,11):parser.exit(2,'Use Python 3.11 or later for the separate worker.\n')
    subprocess.run([sys.executable,'-m','venv',str(args.env)],check=True)
    python=args.env/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    subprocess.run([str(python),'-m','pip','install','--upgrade','pip==26.3'],check=True)
    if sys.platform=='linux':
        subprocess.run([str(python),'-m','pip','install','torch>=2.6,<3','--index-url','https://download.pytorch.org/whl/cpu'],check=True)
    subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/'requirements-interpretability.txt'),'-e',str(ROOT)],check=True)
    subprocess.run([str(python),'-m','pip','check'],check=True)
    print('Worker installed. Run capture_neural.py --mode random-smoke first; no checkpoint downloaded by setup.')


if __name__=='__main__':main()
