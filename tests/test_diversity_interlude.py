import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def interlude(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    return importlib.import_module('diversity_interlude')


def test_development_checkpoint_never_promotes_partial_study(interlude):
    plan = {'development_jobs': [0, 1, 2]}
    assert not interlude.development_ready(plan, {'done': {0: '', 1: ''}}, {'status': 'running'})
    assert interlude.development_ready(plan, {'done': {0: '', 1: '', 2: ''}}, {'status': 'running'})
    with pytest.raises(RuntimeError):
        interlude.development_ready(plan, {'done': {0: ''}}, {'status': 'stopped'})


def test_owned_marker_preserved_and_other_operator_marker_never_removed(interlude, tmp_path):
    root = tmp_path / 'operator'; root.mkdir()
    current = tmp_path / 'current'; current.mkdir()
    token = interlude.request_owned_stop(root, current, 'a' * 64)
    with pytest.raises(FileExistsError):
        interlude.request_owned_stop(root, current, 'b' * 64)
    (current / 'STOP').write_text('independent operator instruction')
    with pytest.raises(ValueError):
        interlude.archive_owned_stop(root, current, token)
    assert (current / 'STOP').read_text() == 'independent operator instruction'
    (current / 'STOP').write_text(token)
    interlude.archive_owned_stop(root, current, token)
    assert not (current / 'STOP').exists()
    assert (root / 'operator-STOP.private.json').read_text() == token
    assert len(list((root / 'decisions').glob('*.json'))) == 2


def test_successor_retry_only_for_zero_call_stopped_queues(interlude, tmp_path, monkeypatch):
    monkeypatch.setattr(interlude, 'private_path', lambda p: Path(p))
    sequence = {}
    for key, (_, state) in interlude.SUCCESSORS.items():
        root = tmp_path / key; root.mkdir(); sequence[key] = str(root)
        (root / state).write_text(json.dumps({'status': 'stopped', 'physical_calls': 0, 'completed_runs': 0, 'failed_runs': 0}))
    commands = interlude.zero_call_successor_commands(sequence)
    assert len(commands) == 3 and all('--resume' in command for _, command in commands)
    root = Path(sequence['large'])
    (root / 'primary-large-state.json').write_text(json.dumps({'status': 'stopped', 'physical_calls': 1}))
    with pytest.raises(ValueError, match='history'):
        interlude.zero_call_successor_commands(sequence)


def test_decision_chain_rejects_tampering(interlude, tmp_path):
    interlude.decision(tmp_path, 'registered', budget_reset=False)
    interlude.decision(tmp_path, 'pause', scope='operator')
    path = tmp_path / 'decisions/decision-000001.private.json'
    value = json.loads(path.read_text()); value['budget_reset'] = True; path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='chain'):
        interlude.decision(tmp_path, 'resume')


def test_failed_independent_calibration_still_restores_current_and_waiting_chain(interlude, tmp_path, monkeypatch):
    root = tmp_path / 'interlude'; root.mkdir()
    current = tmp_path / 'current'; current.mkdir()
    calibration = tmp_path / 'calibration'; calibration.mkdir()
    sequence = {'multidomain': str(current)}
    for key, (_, state) in interlude.SUCCESSORS.items():
        folder = tmp_path / key; folder.mkdir(); sequence[key] = str(folder)
        (folder / state).write_text(json.dumps({'status': 'stopped', 'physical_calls': 0, 'completed_runs': 0, 'failed_runs': 0}))
    chain = tmp_path / 'chain.json'; chain.write_text(json.dumps(sequence))
    parent = {'plan_hash': 'a' * 64}
    study = {'plan_hash': 'b' * 64}
    observer = tmp_path / 'observer'; observer.mkdir()
    (observer / 'report-plan.private.json').write_text('{"fixture":true}')
    plan = {'current': str(current), 'current_plan_hash': parent['plan_hash'], 'calibration': str(calibration),
            'calibration_plan_hash': study['plan_hash'], 'chain': str(chain), 'chain_sha256': interlude.sha(chain),
            'development_jobs': [0], 'max_wait_seconds': 7200, 'max_interlude_seconds': 14400,
            'report_observer': str(observer), 'report_observer_plan_sha256': interlude.sha(observer / 'report-plan.private.json'),
            'dependencies': {'fixture': 'c' * 64}, 'scope': 'operator_handoff_not_study_completion'}
    plan['plan_hash'] = interlude.digest(plan)
    (root / 'interlude-plan.private.json').write_text(json.dumps(plan))
    state_path = current / 'multidomain-live-state.json'
    state_path.write_text(json.dumps({'status': 'running', 'updated_utc': '2026-11-08T01:00:00+00:00'}))
    monkeypatch.setattr(interlude, 'private_path', lambda p: Path(p))
    monkeypatch.setattr(interlude, 'ROOT', tmp_path)
    monkeypatch.setattr(interlude, 'hashes', lambda: plan['dependencies'])
    monkeypatch.setattr(interlude, 'validate_current', lambda p: (parent, {}, {}))
    monkeypatch.setattr(interlude, 'validate_calibration', lambda p: (study, {}, {}))
    def recover(*args):
        if (current / 'STOP').exists():
            state_path.write_text(json.dumps({'status': 'stopped', 'updated_utc': '2026-11-08T02:00:00+00:00'}))
        return {'done': {0: 'fixture'}, 'failures': [], 'physical_calls': 15}
    monkeypatch.setattr(interlude, 'recover_current', recover)
    monkeypatch.setattr(interlude.time, 'sleep', lambda delay: None)
    labels = []
    class Process:
        pid = 123
        def __init__(self, code):
            self.returncode = code
        def poll(self):
            return self.returncode
    def launch(folder, label, command):
        labels.append(label)
        if label == 'diversity-calibration':
            (calibration / 'diversity-state.json').write_text(json.dumps({'status': 'stopped', 'completed_runs': 2, 'failed_runs': 1}))
            return Process(1)
        if label == 'current-resume':
            assert '--resume' in command and '--retry-failed' in command
            state_path.write_text(json.dumps({'status': 'running', 'updated_utc': '2026-11-08T03:00:00+00:00'}))
        if label.startswith('resume-'):
            key = label.removeprefix('resume-')
            path = Path(sequence[key]) / interlude.SUCCESSORS[key][1]
            path.write_text(json.dumps({'status': 'waiting', 'updated_utc': '2026-11-08T03:00:00+00:00'}))
        return Process(None)
    monkeypatch.setattr(interlude, 'launch', launch)
    result = interlude.run(root)
    assert result['status'] == 'completed' and result['current_resumed'] is True
    assert result['calibration_status'] == 'stopped' and result['calibration_failed_runs'] == 1
    assert set(labels) == {'diversity-calibration', 'current-resume', 'resume-primary_output', 'resume-decomposition', 'resume-large', 'fresh-report-observer'}
    assert labels.count('fresh-report-observer') == 1
    assert not (current / 'STOP').exists() and (root / 'operator-STOP.private.json').is_file()
    assert result['scientific_matrix_completion_claimed'] is False
