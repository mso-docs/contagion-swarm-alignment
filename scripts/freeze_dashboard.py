"""Bind an explicitly quiescent submission dashboard to immutable approved files."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from contagion.config import digest
from contagion.events import utc
from contagion.research_publication import Closed
from run_pilot import ROOT

Hash = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
Asset = Annotated[str, Field(pattern=r'^(?:index\.html|app\.js|style\.css|widgets\.js|data/(?:results|research|repositories|followups|trace-samples)\.json|data/(?:studies|trace-samples)/[a-f0-9]{16}\.json)$')]
Source = Literal['results', 'research', 'repositories', 'followups', 'multidomain', 'diversity']
INDEXES = ('results', 'research', 'repositories', 'followups')
SOURCES = (*INDEXES, 'multidomain', 'diversity')


class DatasetCount(Closed):
    index: Source
    rows: int = Field(ge=0)
    live_rows: int = Field(ge=0)
    mock_rows: int = Field(ge=0)
    completed_rows: int = Field(ge=0)
    incomplete_rows: int = Field(ge=0)
    development_rows: int = Field(ge=0)
    evaluation_rows: int = Field(ge=0)
    unclassified_rows: int = Field(ge=0)

    @model_validator(mode='after')
    def denominators(self):
        if (self.rows != self.live_rows + self.mock_rows or self.rows != self.completed_rows + self.incomplete_rows
                or self.rows != self.development_rows + self.evaluation_rows + self.unclassified_rows):
            raise ValueError('Frozen count denominators changed')
        return self


class Freeze(Closed):
    schema_version: Literal['public-dashboard-freeze-1.0'] = 'public-dashboard-freeze-1.0'
    state: Literal['submission_frozen'] = 'submission_frozen'
    cutoff_utc: str = Field(max_length=40)
    frozen_at_utc: str = Field(max_length=40)
    collection_state: Literal['operator_confirmed_quiescent'] = 'operator_confirmed_quiescent'
    inventory_schema_version: Literal['final-evidence-inventory-1.0'] = 'final-evidence-inventory-1.0'
    inventory_sha256: Hash
    inventory_input_sha256: dict[Literal['results', 'research', 'repositories', 'followups'], Hash]
    files_sha256: dict[Asset, Hash] = Field(min_length=4, max_length=10000)
    artifact_content_sha256: Hash
    datasets: list[DatasetCount] = Field(min_length=6, max_length=6)
    trained_checkpoint_captures: int = Field(ge=0)
    random_weight_checks: int = Field(ge=0)
    monitor_summary_cells: int = Field(ge=0)
    advisory_review_records: int = Field(ge=0)
    reviewed_public_trace_samples: int = Field(ge=0, le=32)
    approved_public_detail_files: int = Field(ge=0, le=10000)
    paper_study_cutoffs_unchanged: Literal[True] = True
    raw_logs_included: Literal[False] = False
    private_apis_required: Literal[False] = False
    automatic_refresh_enabled: Literal[False] = False
    freeze_hash: Hash

    @model_validator(mode='after')
    def binding(self):
        if {r.index for r in self.datasets} != set(SOURCES):
            raise ValueError('Every dataset source needs a separate count')
        for value in (self.cutoff_utc, self.frozen_at_utc):
            when = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if when.tzinfo is None or when.utcoffset().total_seconds() != 0:
                raise ValueError('Freeze timestamps must be explicit UTC')
        if datetime.fromisoformat(self.cutoff_utc.replace('Z', '+00:00')) > datetime.fromisoformat(self.frozen_at_utc.replace('Z', '+00:00')):
            raise ValueError('Freeze cannot precede its declared cutoff')
        if self.artifact_content_sha256 != digest(self.files_sha256):
            raise ValueError('Frozen artifact content manifest changed')
        if set(self.inventory_input_sha256) != set(INDEXES):
            raise ValueError('Inventory must bind all four numeric indexes')
        if any(self.files_sha256.get(f'data/{name}.json') != value for name, value in self.inventory_input_sha256.items()):
            raise ValueError('Inventory/public index binding changed')
        if self.freeze_hash != digest(self.model_dump(exclude={'freeze_hash'})):
            raise ValueError('Freeze metadata hash changed')
        return self


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def approved_files(source, env=None):
    """Explicit existing publication closure, excluding the manifest being computed."""
    source = Path(source)
    files = {'index.html', 'app.js', 'style.css', 'data/results.json'}
    if (source / 'widgets.js').exists():
        files.add('widgets.js')
    for name in INDEXES[1:]:
        files.add(f'data/{name}.json')
    from contagion.research_publication import validate_research_snapshot
    research = validate_research_snapshot(source / 'data/research.json', env=env or {})
    if research.suite is not None or research.resources is not None:
        raise ValueError('Operator telemetry cannot enter a frozen dashboard')
    files.update(r.detail_file for r in research.studies if r.detail_file)
    if (source / 'data/trace-samples.json').exists():
        from public_trace_samples import validate_index
        index = validate_index(source / 'data/trace-samples.json', env)
        files.add('data/trace-samples.json'); files.update(r.file for r in index.samples)
    if any((source / name).is_symlink() or not (source / name).is_file() for name in files):
        raise ValueError('Frozen public assets must be regular files')
    return files


def counts(source):
    data = {name: json.loads((Path(source) / 'data' / f'{name}.json').read_text()) for name in INDEXES}
    rows = {'results': data['results']['runs'], 'research': data['research']['studies'],
            'repositories': data['repositories']['runs'], 'followups': data['followups']['runs'],
            'multidomain': data['followups'].get('multidomain', []), 'diversity': data['followups'].get('diversity', [])}
    result = []
    for name in SOURCES:
        values = rows[name]
        development = sum(r.get('split') == 'development' or name == 'diversity' for r in values)
        evaluation = sum(r.get('split') == 'evaluation' for r in values)
        result.append(DatasetCount(index=name, rows=len(values), live_rows=sum(r.get('backend') != 'mock' for r in values),
            mock_rows=sum(r.get('backend') == 'mock' for r in values), completed_rows=sum(r['status'] == 'completed' for r in values),
            incomplete_rows=sum(r['status'] != 'completed' for r in values), development_rows=development,
            evaluation_rows=evaluation, unclassified_rows=len(values) - development - evaluation))
    neural = data['research']['neural']
    sample_path = Path(source) / 'data/trace-samples.json'
    return {'datasets': result,
        'trained_checkpoint_captures': sum(r['evidence_type'] == 'instrumented_checkpoint_replay' for r in neural),
        'random_weight_checks': sum(r['evidence_type'] == 'random_weight_smoke' for r in neural),
        'monitor_summary_cells': len(data['research']['monitor']) + len(data['followups'].get('monitor', [])),
        'advisory_review_records': len(data['research']['reviews']) + len(data['followups'].get('reviews', [])),
        'reviewed_public_trace_samples': len(json.loads(sample_path.read_text())['samples']) if sample_path.exists() else 0,
        'approved_public_detail_files': len({r['detail_file'] for r in data['research']['studies'] if r.get('detail_file')})}


def validate(path, env=None, inventory=None):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Frozen manifest symlink rejected')
    result = Freeze.model_validate_json(path.read_text())
    source = path.parent.parent
    expected = approved_files(source, env)
    if set(result.files_sha256) != expected or any(sha(source / name) != value for name, value in result.files_sha256.items()):
        raise ValueError('Public files changed after the submission freeze')
    fresh = counts(source)
    if any(result.model_dump()[k] != ([r.model_dump() for r in v] if k == 'datasets' else v) for k, v in fresh.items()):
        raise ValueError('Frozen counts no longer match the public data')
    if inventory is not None and sha(inventory) != result.inventory_sha256:
        raise ValueError('Final inventory changed after the dashboard freeze')
    from scan_privacy import scan_blob
    from contagion.publication import sensitive_values
    if scan_blob(path.read_bytes(), public=True, known=sensitive_values(env or {})):
        raise ValueError('Frozen metadata privacy lint failed')
    return result


def create(source, inventory, cutoff, confirm_quiescent=False, env=None):
    source = Path(source); inventory = Path(inventory); path = source / 'data/submission-freeze.json'
    if path.exists() or not confirm_quiescent:
        raise ValueError('A fresh explicit quiescence confirmation is required; never overwrite a submission freeze')
    when = datetime.fromisoformat(cutoff.replace('Z', '+00:00'))
    if when.tzinfo is None or when.utcoffset().total_seconds() != 0 or when > datetime.now(timezone.utc):
        raise ValueError('Use a current/past explicit UTC cutoff')
    from final_evidence_inventory import validate_inventory
    checked = validate_inventory(inventory, env=env, data_root=source / 'data')
    # The inventory source must reconcile with exactly the files this snapshot will serve.
    actual = {name: sha(source / 'data' / f'{name}.json') for name in INDEXES}
    if checked.input_sha256 != actual:
        raise ValueError('Inventory inputs do not match the final public data')
    from serve_dashboard import validate_live_data
    validate_live_data(source / 'data', env)
    files = {name: sha(source / name) for name in sorted(approved_files(source, env))}
    fields = {'cutoff_utc': when.isoformat().replace('+00:00', 'Z'), 'frozen_at_utc': utc(),
              'inventory_sha256': sha(inventory), 'inventory_input_sha256': actual,
              'files_sha256': files, 'artifact_content_sha256': digest(files), **counts(source)}
    value = Freeze.model_construct(freeze_hash='0' * 64, **fields)
    value.freeze_hash = digest(value.model_dump(exclude={'freeze_hash'}))
    checked = Freeze.model_validate(value.model_dump())
    with path.open('x') as stream:
        stream.write(checked.model_dump_json(indent=2) + '\n'); stream.flush(); os.fsync(stream.fileno())
    return validate(path, env, inventory)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'dashboard')
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--cutoff', required=True)
    parser.add_argument('--confirm-quiescent', action='store_true')
    args = parser.parse_args()
    from security_guard import private_values
    _, env = private_values(ROOT, dict(os.environ))
    try:
        result = create(args.source, args.inventory, args.cutoff, args.confirm_quiescent, env)
        print('Submission dashboard frozen at', result.cutoff_utc, '; content SHA256', result.artifact_content_sha256)
    except Exception as exc:
        parser.exit(1, f'Dashboard freeze blocked ({type(exc).__name__}); no files overwritten or private diagnostics printed.\n')
