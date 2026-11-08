#!/usr/bin/env python3
"""Build a minimal Pages artifact containing only approved public assets."""
import argparse
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contagion.publication import validate_snapshot
from scan_privacy import scan_blob
from security_guard import private_values

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ('index.html', 'style.css', 'app.js', 'data/results.json')


def build(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or source in output.parents or output in source.parents:
        raise ValueError('Build output must be separate from the dashboard source')
    # Fail before changing a prior build if the data does not pass schema/redaction checks.
    validate_snapshot(source / 'data/results.json')
    assets = ASSETS
    if (source/'widgets.js').exists() or (source/'widgets.js').is_symlink():assets += ('widgets.js',)
    research = source / 'data/research.json'
    if research.exists() or research.is_symlink():
        from contagion.research_publication import validate_research_snapshot
        snapshot=validate_research_snapshot(research)
        if snapshot.suite is not None or snapshot.resources is not None:
            raise ValueError('Private operational telemetry cannot enter Pages')
        from contagion.research_publication import validate_study_detail
        for row in snapshot.studies:
            if row.detail_file:
                path=source/row.detail_file
                validate_study_detail(path)
                assets += (row.detail_file,)
        assets += ('data/research.json',)
    followups=source/'data/followups.json'
    if followups.exists() or followups.is_symlink():
        from followup_publication import validate
        _,values=private_values(ROOT,dict(os.environ));validate(followups,values);assets+=('data/followups.json',)
    repository=source/'data/repositories.json'
    if repository.exists() or repository.is_symlink():
        from repository_publication import validate_repository_snapshot
        _,values=private_values(ROOT,dict(os.environ));validate_repository_snapshot(repository,values)
        assets+=('data/repositories.json',)
    for asset in assets:
        path = source / asset
        if path.is_symlink() or not path.is_file():
            raise ValueError('An approved dashboard asset is missing or is a symlink')
    known, _ = private_values(ROOT, dict(os.environ))
    for asset in assets:
        if asset.startswith('data/') and scan_blob((source / asset).read_bytes(), public=True, known=known):
            raise ValueError('Public asset failed privacy lint')
    # Refuse nonempty directories to prevent stale files or accidental destructive cleanup.
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('Choose a fresh empty build directory')
    for asset in assets:
        target = output / asset
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / asset, target)
    (output / '.nojekyll').write_text('')
    print(f'Built {len(assets)+1} allowlisted public files; no raw runs or environment files copied.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'dashboard')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        build(args.source, args.out)
    except Exception as exc:
        parser.exit(1, f"Dashboard build failed ({type(exc).__name__}); check assets and public-data validation without publishing raw diagnostics.\n")
