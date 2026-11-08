#!/usr/bin/env python3
"""Generate private researcher tables/figures from a validated public projection."""
import argparse
from pathlib import Path

from contagion.reporting import generate_report
from run_pilot import ROOT

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, default=ROOT / 'dashboard/data/research.json')
    parser.add_argument('--legacy', type=Path, default=ROOT / 'dashboard/data/results.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'results/research-report')
    parser.add_argument('--max-cohort-figures', type=int, default=16)
    args = parser.parse_args()
    try:
        result = generate_report(args.snapshot, args.out, args.max_cohort_figures, args.legacy)
        print(f'Report regenerated: {result["runs"]} attempts, {result["cohorts"]} strict cohorts, {result["figures"]} figures. No inference performed.')
    except Exception as exc:
        parser.exit(1, f'Report blocked ({type(exc).__name__}); no private paths or trace content printed.\n')
