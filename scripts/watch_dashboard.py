#!/usr/bin/env python3
"""Refresh public research summaries from selected local, sealed study attempts."""
import argparse
import json
import os
import time
from pathlib import Path

from contagion.research_publication import make_research_snapshot, validate_research_snapshot
from run_pilot import ROOT
from security_guard import private_values
from scan_privacy import scan_blob


def publish(sources, output, env, include_text=False):
    """Preserve approved evidence; fail closed on corrupt sealed inputs."""
    directories = set()
    for source in sources:
        for manifest in Path(source).rglob('manifest.json'):
            directory = manifest.parent
            config = directory / 'config.snapshot.json'
            if not config.is_file() or not (directory / 'checksum.sha256').is_file():
                continue  # An active attempt is not yet evidence.
            if json.loads(config.read_text()).get('protocol_version') in {'2.0', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6'}:
                directories.add(directory)
    if not directories:
        return False, 0
    current = validate_research_snapshot(output, env=env) if output.exists() else None
    fresh = make_research_snapshot(sorted(directories), env=env, include_text=include_text,
                                  detail_directory=output.parent / 'studies')
    merged = {r.id: r for r in current.studies} if current else {}
    merged.update({r.id: r for r in fresh.studies})
    rows = sorted(merged.values(), key=lambda r: r.id)
    if current and current.studies == rows and current.suite is None and current.resources is None and (not include_text or current.text_included):
        return False, len(rows)
    if current:
        fresh = current.model_copy(update={'studies': rows, 'generated_utc': fresh.generated_utc,
                                          'text_included': current.text_included or include_text, 'suite': None, 'resources': None})
    else:
        fresh.studies = rows
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(fresh.model_dump_json(indent=2) + '\n')
    validate_research_snapshot(temporary, env=env)
    if scan_blob(temporary.read_bytes(), public=True):
        raise ValueError('Public privacy lint failed')
    for row in fresh.studies:
        if row.detail_file and scan_blob((output.parent / 'studies' / Path(row.detail_file).name).read_bytes(), public=True):
            raise ValueError('Public trace privacy lint failed')
    temporary.replace(output)
    return True, len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, action='append', required=True,
                        help='Selected local study root; repeat to include more sources')
    parser.add_argument('--out', type=Path, default=ROOT / 'dashboard/data/research.json')
    parser.add_argument('--include-text', action='store_true', help='Opt into scrubbed task/trace text; review before pushing')
    parser.add_argument('--interval', type=int, default=15)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if args.interval < 5:
        parser.error('Interval must be at least 5 seconds')
    _, env = private_values(ROOT, dict(os.environ))
    while True:
        try:
            changed, count = publish(args.study, args.out, env, args.include_text)
            if changed or args.once:
                print(f'Dashboard export: {count} studies; {"updated" if changed else "unchanged"}.', flush=True)
        except Exception as exc:
            # No private exception bodies, input paths, or model content in operator logs.
            print(f'Dashboard export blocked ({type(exc).__name__}); previous snapshot retained.', flush=True)
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == '__main__':
    raise SystemExit(main())
