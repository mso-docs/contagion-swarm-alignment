#!/usr/bin/env python3
"""Package allowlisted project sources for manual transfer; never include private config."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ('src', 'scripts', 'configs', 'tests', 'docs')
FILES = ('pyproject.toml', 'requirements.lock.txt', 'requirements-interpretability.txt',
         'README.md', 'AGENTS.md', 'CONTAGION_AGENT_MVP_SPEC.md', '.env.example',
         'dashboard/index.html', 'dashboard/style.css', 'dashboard/app.js',
         'dashboard/data/results.json', 'dashboard/data/research.json')


def sources(root=ROOT):
    root = Path(root)
    candidates = [root / name for name in FILES]
    for name in DIRECTORIES:
        candidates.extend((root / name).rglob('*'))
    result = []
    for path in sorted(candidates):
        relative = path.relative_to(root)
        if any(part in {'__pycache__','.pytest_cache','.cache'} or part.endswith('.egg-info') for part in relative.parts) or path.suffix in {'.pyc', '.pyo'}:
            continue
        if path.is_symlink():
            raise ValueError('Worker sources cannot contain symlinks')
        if not path.is_file():
            continue
        if path.name.startswith('.env') and path.name != '.env.example':
            raise ValueError('Private configuration is not a deployment source')
        if path.suffix in {'.key', '.pem', '.safetensors', '.sqlite'}:
            raise ValueError('Private worker artifact in a source directory')
        result.append(relative)
    return result


def build(output, root=ROOT):
    root, output = Path(root).resolve(), Path(output).resolve()
    if root / 'results' not in output.parents:
        raise ValueError('Keep private deployment bundles under ignored results/')
    paths = sources(root)
    payloads = {str(p): (root / p).read_bytes() for p in paths}
    manifest = {'schema_version': '1.0', 'files': {
        name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}}
    payloads['worker-manifest.json'] = (json.dumps(manifest, sort_keys=True, indent=2)+'\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, data in payloads.items():
            info = tarfile.TarInfo('contagion-worker/' + name)
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    return len(paths)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(f'Packaged {build(args.out)} source files. Private env, Git metadata and results excluded.')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Worker packaging stopped ({type(exc).__name__}); no private paths printed.\n')
