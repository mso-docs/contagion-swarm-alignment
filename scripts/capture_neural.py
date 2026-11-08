#!/usr/bin/env python3
"""Run a bounded, explicitly labeled TransformerLens 4 capture on a supported worker."""
import argparse
import json
from contagion.neural import capture, runtime_status

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--doctor',action='store_true');p.add_argument('--mode',choices=['random-smoke','checkpoint'],default='random-smoke')
    p.add_argument('--out',default='results/neural-smoke');p.add_argument('--model');p.add_argument('--revision')
    p.add_argument('--allow-download',action='store_true');p.add_argument('--alignment',nargs=2,type=int)
    p.add_argument('--target-token');p.add_argument('--clean-file');p.add_argument('--corrupt-file')
    args=p.parse_args()
    if args.doctor:print(json.dumps(runtime_status(),indent=2))
    else:
        from pathlib import Path
        kwargs={}
        if args.clean_file:kwargs['clean_text']=Path(args.clean_file).read_text()
        if args.corrupt_file:kwargs['corrupt_text']=Path(args.corrupt_file).read_text()
        try:
            result=capture(args.out,args.mode,args.model,args.revision,args.allow_download,alignment=args.alignment,target_token=args.target_token,**kwargs)
            print('Measured capture complete:',result['evidence_type'])
        except Exception as exc:p.exit(1,f'Neural capture failed ({type(exc).__name__}); no neural result claimed. Run --doctor and use the supported separate worker.\n')
