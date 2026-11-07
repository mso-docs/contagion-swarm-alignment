#!/usr/bin/env python3
"""Publish closed-schema research summaries; private inputs and tensors stay local."""
import argparse
import os
from pathlib import Path

from contagion.research_publication import make_research_snapshot, validate_research_snapshot
from run_pilot import ROOT, load_env

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',action='append',default=[]);p.add_argument('--review');p.add_argument('--monitor')
    p.add_argument('--scenario-index');p.add_argument('--neural',action='append',default=[]);p.add_argument('--include-text',action='store_true')
    p.add_argument('--out',type=Path,default=ROOT/'dashboard/data/research.json');p.add_argument('--validate-only',action='store_true')
    args=p.parse_args()
    try:
        private_env=load_env(ROOT/'.env',os.environ)
        if args.validate_only:data=validate_research_snapshot(args.out,env=private_env)
        else:
            data=make_research_snapshot(args.study,args.review,args.monitor,args.neural,private_env,args.include_text,args.scenario_index)
            args.out.parent.mkdir(parents=True,exist_ok=True)
            temp=args.out.with_suffix('.tmp');temp.write_text(data.model_dump_json(indent=2)+'\n');validate_research_snapshot(temp,env=private_env);temp.replace(args.out)
        print(f'Research snapshot validated: {len(data.studies)} studies, {len(data.reviews)} reviews, {len(data.neural)} measured neural captures.')
    except Exception as exc:p.exit(1,f'Research export failed ({type(exc).__name__}); no private values printed.\n')
