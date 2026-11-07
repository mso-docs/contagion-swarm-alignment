import hashlib
import json
from pathlib import Path

from .config import digest

FILES = ("manifest.json", "config.snapshot.json", "events.jsonl", "outcome.json")


def write_json(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


def seal(directory):
    lines = [f"{hashlib.sha256((directory / name).read_bytes()).hexdigest()}  {name}\n" for name in FILES]
    (directory / "checksum.sha256").write_text("".join(lines))


def verify(directory):
    try:
        expected = {}
        for line in (directory / "checksum.sha256").read_text().splitlines():
            value, name = line.split("  ")
            expected[name] = value
        if set(expected) != set(FILES):
            return False
        return all(hashlib.sha256((directory / name).read_bytes()).hexdigest() == expected[name] for name in FILES)
    except (OSError, ValueError):
        return False


def source_fingerprint():
    package = Path(__file__).parent
    return digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(package.glob("*.py"))})


def allocate(root, config, provider_identity):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    prefix = digest({"config": config.model_dump(), "backend": provider_identity, "source": source_fingerprint()})[:20]
    for directory in sorted(root.glob(prefix + "-attempt-*")):
        if verify(directory):
            manifest = json.loads((directory / "manifest.json").read_text())
            if manifest["status"] == "completed":
                return directory, True
    attempt = 1
    while True:
        directory = root / f"{prefix}-attempt-{attempt:03d}"
        try:
            directory.mkdir()
            return directory, False
        except FileExistsError:
            attempt += 1
