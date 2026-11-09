import importlib
import json
from pathlib import Path
import runpy
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def guard(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    return runpy.run_path(str(ROOT / 'scripts/security_guard.py'))


def sample_files(root, model='fixture-model'):
    from contagion.config import digest
    module = importlib.import_module('public_trace_samples')
    sample = module.Sample.model_construct(id='a' * 16, protocol='5.1-multidomain-question-coverage', source_kind='multidomain',
        model=model, source_seal_sha256='b' * 64, content_sha256='0' * 64,
        traces=[module.TraceEvent(event_id='c' * 16, round=2, event_type='artifact', agent_id='agent_0', content='Fixture output only.', content_truncated=False)],
        eligible_events=1, omitted_events=0)
    sample.content_sha256 = digest(sample.model_dump(exclude={'content_sha256'}))
    entry = module.Entry(**{k: getattr(sample, k) for k in ['id', 'protocol', 'source_kind', 'source_seal_sha256', 'content_sha256']},
                         file='data/trace-samples/' + sample.id + '.json')
    index = module.Index(generated_utc='2026-11-08T00:00:00+00:00', samples=[entry])
    base = root / 'dashboard/data'; (base / 'trace-samples').mkdir(parents=True)
    (base / 'trace-samples.json').write_text(index.model_dump_json())
    (base / 'trace-samples' / (sample.id + '.json')).write_text(sample.model_dump_json())
    return base, sample


def test_only_closed_sample_paths_are_allowed(guard):
    assert not guard['blocked_path']('dashboard/data/trace-samples.json')
    assert not guard['blocked_path']('dashboard/data/trace-samples/' + 'a' * 16 + '.json')
    assert guard['blocked_path']('dashboard/data/trace-samples/raw.json')
    assert guard['blocked_path']('dashboard/data/trace-samples/' + 'a' * 16 + '.jsonl')


def test_closed_sample_index_is_validated_with_companions(guard, tmp_path):
    sample_files(tmp_path)
    assert guard['check'](tmp_path, 'worktree', env={}) == 0


def test_staged_bad_sample_cannot_hide_behind_clean_worktree(guard, tmp_path):
    base, sample = sample_files(tmp_path)
    target = base / 'trace-samples' / (sample.id + '.json')
    clean = target.read_bytes(); bad = json.loads(clean); bad['request_histories'] = []
    target.write_text(json.dumps(bad))
    subprocess.run(['git', 'add', 'dashboard/data'], cwd=tmp_path, check=True)
    target.write_bytes(clean)
    assert guard['check'](tmp_path, 'staged', env={}) == 1


def test_missing_companion_and_unreferenced_sample_are_blocked(guard, tmp_path):
    base, sample = sample_files(tmp_path)
    target = base / 'trace-samples' / (sample.id + '.json')
    target.unlink()
    assert guard['check'](tmp_path, 'worktree', env={}) == 1
