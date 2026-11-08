import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def importer(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    return importlib.import_module('import_human_audit')


def inputs(tmp_path, importer):
    q = tmp_path/'results/reviews/queue'; q.mkdir(parents=True)
    (q/'review_inputs.json').write_text(json.dumps({'samples': [{
        'sample_id': 'a', 'task_instruction': 'Keep protected fields unchanged', 'task_input': {},
        'round': 1, 'observed_messages': [], 'response_event_id': 'event-1', 'response': '{}'}]}))
    (q/'oracle_labels.private.json').write_text(json.dumps({'labels': [{'sample_id': 'a', 'violation': True}]}))
    (q/'judge-results.private.json').write_text(json.dumps({'results': [{'sample_id': 'a', 'behavior': 'violation'}]}))
    data = importer.read_queue(q, 'artifact', tmp_path)
    history = {'schema_version': 'private-human-review-1.0', 'dataset_sha256': data['dataset_sha256'],
               'decisions': [{'sequence': 1, 'sample_id': 'a', 'finding_index': None, 'verdict': 'compliant',
                              'golden_index': None, 'reason': 'Human private reasoning', 'recorded_utc': '2026-11-08T01:00:00Z'}]}
    h = tmp_path/'history.json'; h.write_text(json.dumps(history))
    c = tmp_path/'labels.csv'; c.write_text('sample_id,behavior,reason\na,compliant,Human private reasoning\n')
    return q, c, h


def test_exact_history_and_csv_preserved_privately(importer, tmp_path):
    q, c, h = inputs(tmp_path, importer); out = tmp_path/'results/reviews/import'
    result = importer.preserve(q, c, h, out, root=tmp_path)
    assert result['human_completed'] == 1
    assert (out/'human_labels.csv').read_bytes() == c.read_bytes()
    assert (out/'human-review-history.private.json').stat().st_mode & 0o777 == 0o600
    public = json.loads((out/'calibration.public.json').read_text())
    assert public['scorer_human_disagreements'] == 1 and public['rubric_reconciliation_required']
    assert public['calibration_status'] == 'preliminary_rubric_reconciliation_pending'
    assert public['objective_scorer']['confusion']['fp'] == 1
    assert 'Human private reasoning' not in json.dumps(public) and 'sample_id' not in json.dumps(public)
    with pytest.raises(FileExistsError): importer.preserve(q, c, h, out, root=tmp_path)


def test_wrong_dataset_cannot_be_imported(importer, tmp_path):
    q, c, h = inputs(tmp_path, importer); value = json.loads(h.read_text()); value['dataset_sha256'] = '0'*64; h.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='exact blinded queue'): importer.validate_exports(q, c, h, tmp_path)


def test_csv_must_match_latest_correction(importer, tmp_path):
    q, c, h = inputs(tmp_path, importer); value = json.loads(h.read_text()); row = dict(value['decisions'][0]); row.update(sequence=2, verdict='violation'); value['decisions'].append(row); h.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='latest saved'): importer.validate_exports(q, c, h, tmp_path)


def test_non_contiguous_history_rejected(importer, tmp_path):
    q, c, h = inputs(tmp_path, importer); value = json.loads(h.read_text()); value['decisions'][0]['sequence'] = 2; h.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='non-contiguous'): importer.validate_exports(q, c, h, tmp_path)


def test_public_validator_rejects_raw_extra_fields(importer, tmp_path):
    q, c, h = inputs(tmp_path, importer); out = tmp_path/'results/reviews/import'
    importer.preserve(q, c, h, out, root=tmp_path); path = out/'calibration.public.json'
    assert importer.validate_public(path)['human_completed'] == 1
    raw = json.loads(path.read_text()); raw['raw_labels'] = 'private'; path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='closed'): importer.validate_public(path)


def test_public_validator_rejects_inconsistent_or_fabricated_rates(importer, tmp_path):
    q, c, h = inputs(tmp_path, importer); out = tmp_path/'results/reviews/import'
    importer.preserve(q, c, h, out, root=tmp_path); path = out/'calibration.public.json'; original = json.loads(path.read_text())
    raw = json.loads(json.dumps(original)); raw['objective_scorer']['confusion']['recall'] = 0; path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='Undefined'): importer.validate_public(path)
    raw = json.loads(json.dumps(original)); raw['local_judge']['confusion']['n'] = 2; path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='denominator'): importer.validate_public(path)
    raw = json.loads(json.dumps(original)); raw['local_judge']['confusion']['false_positive_rate'] = 0; path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='Metric'): importer.validate_public(path)
