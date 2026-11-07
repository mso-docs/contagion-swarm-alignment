#!/usr/bin/env python3
"""Build a minimal Pages artifact containing only approved public assets."""
import argparse
from pathlib import Path
import shutil

from contagion.publication import validate_snapshot

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ('index.html', 'style.css', 'app.js', 'data/results.json')


def build(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or source in output.parents or output in source.parents:
        raise ValueError('Build output must be separate from the dashboard source')
    # Fail before changing a prior build if the data does not pass schema/redaction checks.
    validate_snapshot(source / 'data/results.json')
    for asset in ASSETS:
        path = source / asset
        if path.is_symlink() or not path.is_file():
            raise ValueError('An approved dashboard asset is missing or is a symlink')
    # Refuse nonempty directories to prevent stale files or accidental destructive cleanup.
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('Choose a fresh empty build directory')
    for asset in ASSETS:
        target = output / asset
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / asset, target)
    (output / '.nojekyll').write_text('')
    print('Built five allowlisted public files; no raw runs or environment files copied.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'dashboard')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        build(args.source, args.out)
    except Exception as exc:
        parser.exit(1, f"Dashboard build failed ({type(exc).__name__}); check assets and public-data validation without publishing raw diagnostics.\n")
