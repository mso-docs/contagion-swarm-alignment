"""Operator-only pinned data download. No inference or execution of upstream code."""
import argparse
import hashlib
import json
from pathlib import Path

import httpx

from contagion.storage import write_json
from multidomain_docket import ROOT, private_path


def download(output):
    output = private_path(output)
    if output.exists():
        raise ValueError('Never replace an existing import')
    expected = json.loads((ROOT / 'configs/multidomain_bbh_source.json').read_text())
    # Keep the fetch origin/path allowlisted even if a local config was edited.
    if (expected['repository'] != 'suzgunmirac/BIG-Bench-Hard'
            or expected['revision'] != '9ee07bd481feebf959a6b59d61ea57bdcf30964d'
            or set(expected['files']) != {'LICENSE', 'bbh/causal_judgement.json',
                'bbh/formal_fallacies.json', 'bbh/multistep_arithmetic_two.json'}):
        raise ValueError('Unsupported source')
    blobs = {}
    with httpx.Client(timeout=45, follow_redirects=False) as client:
        for name, checksum in expected['files'].items():
            url = f"https://raw.githubusercontent.com/{expected['repository']}/{expected['revision']}/{name}"
            with client.stream('GET', url) as response:
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > 2_000_000:
                        raise ValueError('Source exceeds download cap')
            if hashlib.sha256(content).hexdigest() != checksum:
                raise ValueError('Source hash mismatch')
            blobs[name] = content
    output.mkdir(parents=True)
    for name, content in blobs.items():
        path = output / name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(content)
    write_json(output / 'source-manifest.json', expected)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    download(args.out)
    print('Pinned data imported; no model calls or upstream code execution.')
