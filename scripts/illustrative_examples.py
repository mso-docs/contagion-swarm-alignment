"""Publish a small, source-bound illustration of scorer/human rubric differences."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import Field

from contagion.config import digest
from contagion.events import read_events
from contagion.publication import Redactor, sensitive_values
from contagion.research_publication import Closed
from contagion.storage import verify, write_json
from run_pilot import ROOT

SELECTION = 'Two strict-positive samples by opaque ID, then one unflagged final patch artifact from the selected human audit; illustrative, not representative.'
CONTEXT = 'The human label applies to the original supplied review context; this artifact excerpt is not a new independent adjudication.'


class Example(Closed):
    sample_id: str = Field(pattern=r'^[a-f0-9]{16}$')
    event_ref: str = Field(pattern=r'^[a-f0-9]{16}$')
    protocol: Literal['2.6'] = '2.6'
    family: Literal['patch'] = 'patch'
    condition: Literal['none', 'benign_override']
    agent_id: Literal['agent_0', 'agent_1', 'agent_2', 'agent_3', 'agent_4']
    round: int = Field(ge=0, le=4)
    strict_flag: bool
    human_label: Literal['compliant'] = 'compliant'
    source_seal_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    artifact: str = Field(min_length=1, max_length=1600)
    context: Literal[CONTEXT] = CONTEXT


class Examples(Closed):
    schema_version: Literal['illustrative-human-scorer-examples-1.0'] = 'illustrative-human-scorer-examples-1.0'
    selection: Literal[SELECTION] = SELECTION
    examples: list[Example] = Field(min_length=3, max_length=3)
    source_hashes: dict[str, str]
    examples_hash: str = Field(pattern=r'^[a-f0-9]{64}$')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(path, env=None):
    from scan_privacy import scan_blob
    data = Examples.model_validate_json(Path(path).read_text())
    if data.examples_hash != digest(data.model_dump(exclude={'examples_hash'})):
        raise ValueError('Illustrative content changed')
    if len({e.sample_id for e in data.examples}) != 3 or [e.strict_flag for e in data.examples] != [True, True, False] or data.examples[-1].round != 4:
        raise ValueError('Illustrative selection changed')
    if set(data.source_hashes) != {'dataset_sha256', 'csv_sha256', 'history_sha256', 'queue_sha256', 'oracle_sha256'} or any(len(v) != 64 or any(c not in '0123456789abcdef' for c in v) for v in data.source_hashes.values()):
        raise ValueError('Invalid source bindings')
    if scan_blob(Path(path).read_bytes(), public=True, known=sensitive_values(env or {})):
        raise ValueError('Illustrative privacy check failed')
    return data


def generate(queue, labels, history, campaign, output, env):
    from import_human_audit import validate_exports, validate_public
    from calibrate_review import load_labels
    queue = Path(queue)
    receipt = validate_exports(queue, labels, history)
    human = validate_public(ROOT / 'report/data/human_audit.json')
    if any(receipt[k] != v for k, v in human['source_hashes'].items()):
        raise ValueError('Examples must use the actual frozen human reference')
    samples = {r['sample_id']: r for r in json.loads((queue / 'review_inputs.json').read_text())['samples']}
    judgments = load_labels(labels, set(samples))
    oracle_path = queue / 'oracle_labels.private.json'
    oracle = json.loads(oracle_path.read_text())['labels']
    flagged = sorted((r for r in oracle if r['family'] == 'patch' and r['violation']), key=lambda r: r['sample_id'])[:2]
    final = sorted((r for r in oracle if r['family'] == 'patch' and not r['violation'] and r['round'] == 4), key=lambda r: r['sample_id'])[:1]
    if len(flagged) != 2 or len(final) != 1:
        raise ValueError('Required actual illustrative strata are unavailable')
    config = json.loads((Path(campaign) / 'campaign.json').read_text())
    source = Path(config['run_root']); directories = {}
    for manifest in source.rglob('manifest.json'):
        directory = manifest.parent
        if not (directory / 'checksum.sha256').is_file():
            continue
        m = json.loads(manifest.read_text()); seal = sha(directory / 'checksum.sha256')
        if m.get('protocol_version') == '2.6':
            directories[digest(['2.6', seal])[:20]] = (directory, seal)
            directories[m['run_id']] = (directory, seal)
            directories[directory.name] = (directory, seal)
    redact = Redactor(sensitive_values(env)); rows = []
    for selected in flagged + final:
        if judgments[selected['sample_id']] != 'compliant':
            raise ValueError('Do not synthesize a human label')
        directory, seal = directories[selected['run_id']]
        if not verify(directory):
            raise ValueError('Illustrative source seal mismatch')
        events = [e for e in read_events(directory / 'events.jsonl') if e['event_id'] == selected['artifact_event_id']]
        if len(events) != 1 or events[0]['event_type'] != 'artifact':
            raise ValueError('Original artifact is unavailable')
        event = events[0]
        if event['round'] != selected['round'] or event['metadata']['score']['violation'] != selected['violation']:
            raise ValueError('Oracle differs from original artifact scoring')
        answer = json.loads(event['content'])
        response = json.loads(samples[selected['sample_id']]['response'])
        if response.get('answer') != answer:
            raise ValueError('Human-reviewed response does not match source artifact')
        rows.append(Example(sample_id=selected['sample_id'], event_ref=digest(event['event_id'])[:16],
            condition=selected['condition'], agent_id=event['agent_id'], round=event['round'], strict_flag=selected['violation'],
            source_seal_sha256=seal, artifact=redact(json.dumps(answer, sort_keys=True))))
    hashes = {k: receipt[k] for k in human['source_hashes']}; hashes['oracle_sha256'] = sha(oracle_path)
    data = Examples.model_construct(examples=rows, source_hashes=hashes, examples_hash='0' * 64)
    data.examples_hash = digest(data.model_dump(exclude={'examples_hash'}))
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, data.model_dump()); return validate(output, env)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=ROOT / 'report/data/illustrative_examples.json')
    args = p.parse_args()
    from security_guard import private_values
    _, env = private_values(ROOT, dict(os.environ))
    base = ROOT / 'results/reviews'
    data = generate(base / 'workspaces/triage', base / 'human-audit-v1/human_labels.csv',
        base / 'human-audit-v1/human-review-history.private.json', ROOT / 'results/campaigns/heldout-v26-20261108', args.out, env)
    print('Validated', len(data.examples), 'actual, redacted illustrative artifacts; no new labels or model calls.')
