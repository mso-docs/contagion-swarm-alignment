"""Copy a validated live-data checkpoint for review/commit; never pushes or stops inference."""
import argparse
import os
import json
import re
from tempfile import TemporaryDirectory
from pathlib import Path
import shutil

from run_pilot import ROOT
from security_guard import private_values
from serve_dashboard import validate_live_data


def export(source,destination,env):
    source=Path(source);destination=Path(destination)
    if (destination/'submission-freeze.json').exists():raise ValueError('Submission snapshot is frozen; use a separate future checkpoint')
    if not (source/'research.json').is_file():raise ValueError('Start the local dashboard before exporting live data')
    (ROOT/'results').mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='dashboard-checkpoint-',dir=ROOT/'results') as temporary:
        checkpoint=Path(temporary)
        for name in ['results.json','research.json','repositories.json','followups.json','trace-samples.json']:
            path=source/name
            if not path.exists():continue
            if path.is_symlink():raise ValueError('Snapshot symlink rejected')
            (checkpoint/name).write_bytes(path.read_bytes())
        research=json.loads((checkpoint/'research.json').read_text())
        details=checkpoint/'studies';details.mkdir()
        for row in research['studies']:
            reference=row.get('detail_file')
            if not reference:continue
            name=Path(reference).name
            if not re.fullmatch(r'[a-f0-9]{16}\.json',name):raise ValueError('Unapproved trace reference')
            path=source/'studies'/name
            if path.is_symlink():raise ValueError('Trace symlink rejected')
            (details/name).write_bytes(path.read_bytes())
        sample_files=[]
        if (checkpoint/'trace-samples.json').is_file():
            from public_trace_samples import validate_index
            index=validate_index(source/'trace-samples.json',env)
            for row in index.samples:
                path=source/'trace-samples'/Path(row.file).name
                target=checkpoint/'trace-samples'/path.name;target.parent.mkdir(exist_ok=True)
                target.write_bytes(path.read_bytes());sample_files.append(target)
        validate_live_data(checkpoint,env)
        files=[*details.glob('*.json'),*checkpoint.glob('*.json'),*sample_files]
        destination.mkdir(parents=True,exist_ok=True)
        for path in files:
            target=destination/path.relative_to(checkpoint);target.parent.mkdir(parents=True,exist_ok=True)
            staging=target.with_suffix('.tmp');shutil.copyfile(path,staging);staging.replace(target)
        validate_live_data(destination,env)
        return len(files)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'results/dashboard-live/data')
    parser.add_argument('--out',type=Path,default=ROOT/'dashboard/data');args=parser.parse_args()
    _,env=private_values(ROOT,dict(os.environ))
    count=export(args.source,args.out,env);print('Exported',count,'validated data files for review; live cache and inference remain running.')
