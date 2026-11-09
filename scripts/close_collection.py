"""Close existing local allocations for a submission freeze; preserve all evidence."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path

from run_pilot import ROOT


def close(base, receipt, *, project=ROOT):
    project = Path(project).resolve(); base = Path(base)
    if base.is_symlink() or base.resolve() != project / 'results/campaigns':
        raise ValueError('Only this project campaign directory may be closed')
    receipt = Path(receipt)
    if receipt.exists() or (project / 'results') not in receipt.resolve().parents:
        raise ValueError('Use a fresh private receipt under results')
    locks = []
    try:
        for name in ['controller.lock', 'controller-primary.lock']:
            path = project / 'results/checkpoint-gates' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = path.open('a')
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                handle.close()
                raise ValueError('An inference allocation is still active; drain it before freezing') from None
            locks.append(handle)
        allocations = []
        for directory in sorted(base.iterdir()):
            if directory.is_symlink():
                raise ValueError('Campaign symlink rejected')
            if not directory.is_dir():
                continue
            states = sorted(set(directory.glob('*state.json')) | set(directory.glob('state.json')))
            if not states:
                continue
            hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in states}
            statuses = [json.loads(p.read_text()).get('status', 'unknown') for p in states]
            if any(s in {'running', 'cooling', 'waiting_for_primary_lease', 'waiting_for_secondary_lease'} for s in statuses):
                raise ValueError('A registered allocation has not reached a terminal state')
            stop = directory / 'STOP'
            if stop.is_symlink():
                raise ValueError('STOP symlink rejected')
            created = not stop.exists()
            if created:
                with stop.open('x') as stream:
                    stream.write('Collection closed for final submission snapshot; do not automatically resume.\n')
            if any(hashlib.sha256((directory / name).read_bytes()).hexdigest() != value for name, value in hashes.items()):
                raise ValueError('Campaign changed during closure')
            allocations.append({'allocation': directory.name, 'statuses': statuses, 'state_sha256': hashes,
                                'stop_created': created})
        data = {'schema_version': 'collection-closure-1.0', 'closed_utc': datetime.now(timezone.utc).isoformat(),
                'allocations': allocations, 'both_controller_leases_available': True,
                'raw_logs_modified': False, 'remote_changes_performed': False}
        receipt.parent.mkdir(parents=True, exist_ok=True)
        with receipt.open('x') as stream:
            json.dump(data, stream, indent=2); stream.write('\n')
        return data
    finally:
        for handle in locks:
            fcntl.flock(handle, fcntl.LOCK_UN); handle.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt', type=Path, required=True)
    args = p.parse_args()
    result = close(ROOT / 'results/campaigns', args.receipt)
    print('Collection closed:', len(result['allocations']), 'local allocations; both controller leases idle; raw logs unchanged.')
