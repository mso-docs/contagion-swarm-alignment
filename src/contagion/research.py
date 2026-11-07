"""CLI for versioned studies, offline oversight and bounded independent review."""
import argparse
import asyncio
import json
import os
from pathlib import Path

from .inference import HTTPProvider, MockProvider
from .monitor import evaluate_visibility
from .review import calibration_report, review_batch
from .storage import write_json
from .studies import freeze_plan, load_plan, run_plan, summarize_study


def environment(env_file=None):
    # Reuse the safe .env parser; no shell sourcing or environment dumps.
    import importlib.util
    script=Path(__file__).resolve().parents[2]/'scripts/run_pilot.py'
    spec=importlib.util.spec_from_file_location('contagion_local_env',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    path=Path(env_file) if env_file else script.parent.parent/'.env'
    if env_file and not path.is_file():raise ValueError('Requested private env file does not exist')
    return module.load_env(path,os.environ)


async def main_async(args):
    if args.command=='scenarios':
        from .scenarios import build_database
        print(json.dumps(build_database(args.out,args.catalog_out)));return
    if args.command=='freeze':
        result=freeze_plan(load_plan(args.config),args.out);print('Frozen plan:',result['freeze_hash']);return
    if args.command=='monitor':
        result=evaluate_visibility(args.source,args.out,seed=args.seed,topology=args.topology)
        print(f"{len(result['observations'])} dependent monitor projections saved");return
    if args.command=='summarize':
        rows=summarize_study(args.source)
        print(json.dumps({'runs':len(rows),'completed':sum(r['manifest']['status']=='completed' for r in rows),
                          'violation_runs':sum(r['outcome']['any_violation'] for r in rows)},indent=2));return
    if args.command=='calibrate':
        result=calibration_report(args.source,args.labels);write_json(Path(args.out),result);print('Saved descriptive human calibration report');return
    env=environment(args.env_file)
    model=args.model or env.get('CONTAGION_MODEL')
    provider=MockProvider() if args.provider=='mock' else HTTPProvider(env.get('CONTAGION_BASE_URL',''),timeout=60,retries=0,api=args.provider)
    try:
        if args.provider!='mock':
            if not model:raise ValueError('Choose an installed model explicitly')
            # API key remains private and is only used by the controlled adapter.
            if env.get('CONTAGION_API_KEY'):
                provider.client.headers['Authorization']='Bearer '+env['CONTAGION_API_KEY']
            installed=await provider.discover()
            match=next((m for m in installed if m.get('name',m.get('id'))==model),None)
            if not match:raise ValueError('Selected model is not installed; nothing pulled')
            provider.identity.update(model=model,digest=match.get('digest'))
            if args.expected_digest and provider.identity['digest']!=args.expected_digest:
                raise ValueError('Installed model digest differs from requested cohort; no inference started')
        if args.command=='study':
            if args.provider!='mock' and args.shard_count>1 and not args.expected_digest:
                raise ValueError('Require --expected-digest for a shared live multi-worker cohort')
            plan=load_plan(args.config)
            # Model is part of the freeze: select it in the YAML before freezing for live runs.
            if args.provider!='mock' and plan.model!=model:
                raise ValueError('Plan model must match configured model before freezing')
            paths=await run_plan(plan,provider,args.out,args.freeze,args.shard_index,args.shard_count)
            print(f'{len(paths)} bounded study runs completed')
        else:
            if not 1<=args.max_calls<=1000:raise ValueError('Review call limit must be 1..1000')
            result=await review_batch(args.source,args.out,provider,model or 'mock-reviewer',args.max_calls,seed=args.seed)
            print(json.dumps(result));print('Reviewer is uncalibrated; no samples automatically cleared')
    finally:
        if hasattr(provider,'close'):await provider.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    scenarios=commands.add_parser('scenarios');scenarios.add_argument('--out',required=True);scenarios.add_argument('--catalog-out')
    freeze=commands.add_parser('freeze');freeze.add_argument('--config',required=True);freeze.add_argument('--out',required=True)
    study=commands.add_parser('study');study.add_argument('--config',required=True);study.add_argument('--freeze',required=True);study.add_argument('--out',required=True);study.add_argument('--shard-index',type=int,default=0);study.add_argument('--shard-count',type=int,default=1)
    summarize=commands.add_parser('summarize');summarize.add_argument('--source',required=True)
    monitor=commands.add_parser('monitor');monitor.add_argument('--source',required=True);monitor.add_argument('--out',required=True);monitor.add_argument('--seed',type=int,default=404);monitor.add_argument('--topology',choices=['ring','star','complete'],default='ring')
    review=commands.add_parser('review');review.add_argument('--source',required=True);review.add_argument('--out',required=True);review.add_argument('--max-calls',type=int,default=100);review.add_argument('--seed',type=int,default=404)
    for command in [study,review]:
        command.add_argument('--provider',choices=['mock','ollama','openai'],default='mock');command.add_argument('--model');command.add_argument('--env-file');command.add_argument('--expected-digest',help='Require the discovered model digest before inference')
    calibrate=commands.add_parser('calibrate');calibrate.add_argument('--source',required=True);calibrate.add_argument('--labels',required=True);calibrate.add_argument('--out',required=True)
    args=parser.parse_args()
    try:asyncio.run(main_async(args))
    except Exception as exc:parser.exit(1,f'Research operation failed ({type(exc).__name__}); inspect private artifacts/configuration. No secrets printed.\n')


if __name__=='__main__':main()
