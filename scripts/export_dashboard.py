#!/usr/bin/env python3
"""Create a publication snapshot without copying raw logs or .env to the site."""
import argparse
import os
from pathlib import Path
import sys

from contagion.publication import export_snapshot, validate_snapshot
from run_pilot import ROOT, load_env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', action='append', type=Path, help='Repeat for separate model directories; walks recursively')
    parser.add_argument('--out', type=Path, default=ROOT / 'dashboard/data/results.json')
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--include-traces', action='store_true', help='Include scrubbed free text; review before pushing')
    parser.add_argument('--include-thinking', action='store_true', help='Also include scrubbed generated reasoning text')
    parser.add_argument('--redact-file', type=Path, help='Private newline-delimited extra exact strings to redact')
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    try:
        env = load_env(args.env_file, os.environ)
        if args.validate_only:
            data = validate_snapshot(args.out, env=env)
        else:
            if not args.source:
                raise ValueError('Provide at least one --source directory')
            extra = args.redact_file.read_text().splitlines() if args.redact_file else []
            data = export_snapshot(args.source, args.out, include_traces=args.include_traces,
                                   include_thinking=args.include_thinking, env=env, extra_secrets=extra)
        print(f'Public snapshot: {len(data.runs)} sealed runs; traces={data.traces_included}; '
              f'replacements={data.redaction_replacements}; skipped unsealed={data.skipped_unsealed}')
        print('Review the exported file before pushing. Redaction cannot guarantee removal of unknown PII.')
    except Exception as exc:
        # Do not echo parsed content, secret strings, raw paths or backend diagnostics.
        print(f'Export failed ({type(exc).__name__}); no raw logs should be published.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
