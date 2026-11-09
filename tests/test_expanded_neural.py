import base64
import hashlib
import importlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile
from types import SimpleNamespace

import pytest


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    return importlib.import_module('expanded_trained_pilot'), importlib.import_module('expanded_neural_worker')


class Tokenizer:
    vocab = {}
    def encode(self, text, add_special_tokens=False):
        tokens = re.findall(r' ?[A-Za-z0-9]+|[^\w\s]', text)
        for t in tokens:
            self.vocab.setdefault(t, len(self.vocab) + 1)
        return [self.vocab[t] for t in tokens]


def make_capture(module, directory, pair, layer):
    import contagion.neural as neural
    directory.mkdir(parents=True)
    c = len(pair['clean_token_ids']); d = len(pair['corrupt_token_ids'])
    data = {'schema_version': '1.0', 'evidence_type': 'instrumented_checkpoint_replay', 'model': module.MODEL,
        'revision': module.REVISION, 'seed': 101, 'device': 'cpu', 'dtype': 'float32',
        'capture_source_hash': module.sha(neural.__file__), 'clean_token_count': c, 'corrupt_token_count': d,
        'layers': [{'layer': i, 'clean_residual_rms': [1.] * c, 'corrupt_residual_rms': [1.] * d,
                    'neurons': [{'index': n, 'clean': [1.] * c, 'corrupt': [1.] * d} for n in range(4)]} for i in range(12)],
        'patch': {'hook': f'blocks.{layer}.hook_out', 'clean_position': pair['alignment'][0], 'corrupt_position': pair['alignment'][1],
                  'target_token_id_private': pair['target_token_id'], 'clean_target_logit': 2., 'corrupt_target_logit': 1.,
                  'patched_target_logit': 1.5, 'noop_target_logit': 1., 'position_control_logit': 1.}}
    inputs = {'clean_text': pair['clean'], 'corrupt_text': pair['corrupt'], 'clean_token_ids': [pair['clean_token_ids']],
              'corrupt_token_ids': [pair['corrupt_token_ids']]}
    (directory / 'capture.json').write_text(json.dumps(data))
    (directory / 'private_inputs.json').write_text(json.dumps(inputs))
    (directory / 'activations.safetensors').write_bytes(b'explicit-unit-test-tensor-fixture')
    checks = {n: module.sha(directory / n) for n in ['capture.json', 'private_inputs.json', 'activations.safetensors']}
    (directory / 'checksums.json').write_text(json.dumps(checks))
    return data


def test_six_predeclared_pairs_and_single_token_alignment(modules):
    pilot, _ = modules
    pairs, rejected = pilot.preflight(Tokenizer())
    assert len(pairs) == 6 and rejected == [] and pilot.LAYERS == list(range(12))
    assert all(len(p['clean_token_ids']) <= 32 and len(p['corrupt_token_ids']) <= 32 for p in pairs)
    class Unsupported(Tokenizer):
        def encode(self, text, add_special_tokens=False):
            return [10, 11] if text == ' five' else super().encode(text, add_special_tokens)
    selected, rejected = pilot.preflight(Unsupported())
    assert len(selected) == 5 and rejected[0]['pair_id'] == 'arithmetic-peer-probe'


def test_required_alignment_failure_stops_before_measurement(modules):
    pilot, _ = modules
    class Unsupported(Tokenizer):
        def encode(self, text, add_special_tokens=False):
            return [10, 11] if text == ' Paris' else super().encode(text, add_special_tokens)
    with pytest.raises(ValueError, match='Required reference'):
        pilot.preflight(Unsupported())


def test_existing_capture_reuse_requires_exact_tokens_layer_and_controls(modules, tmp_path):
    pilot, _ = modules
    pair = pilot.preflight(Tokenizer())[0][0]
    root = tmp_path / 'old'; make_capture(pilot, root, pair, 5)
    pilot.match_capture(root, pair, 5)
    with pytest.raises(ValueError, match='grid cell'):
        pilot.match_capture(root, pair, 4)
    (root / 'activations.safetensors').write_bytes(b'changed')
    with pytest.raises(ValueError, match='seal'):
        pilot.match_capture(root, pair, 5)


def test_prepare_reuses_old_cell_and_freezes_cache(modules, tmp_path, monkeypatch):
    pilot, _ = modules; tokenizer = Tokenizer(); pairs, _ = pilot.preflight(tokenizer)
    old = tmp_path / 'prior'; make_capture(pilot, old, pairs[0], 0)
    cache = tmp_path / 'cache'; snapshot = cache / 'hub/models--openai-community--gpt2/snapshots' / pilot.REVISION
    snapshot.mkdir(parents=True)
    for name, content in {'config.json': '{"n_layer":12}', 'model.safetensors': 'unit-test-only',
                          'vocab.json': '{}', 'merges.txt': 'fixture'}.items():
        (snapshot / name).write_text(content)
    monkeypatch.setitem(sys.modules, 'transformers', SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a, **k: tokenizer)))
    monkeypatch.setattr(pilot, 'environment', lambda _: {})
    out = tmp_path / 'grid'; plan = pilot.prepare(out, cache, [old])
    assert len(plan['jobs']) == 72 and sum(j['reused'] is not None for j in plan['jobs']) == 1
    assert plan['cpu_threads'] == 2 and plan['device'] == 'cpu' and plan['max_wall_seconds'] == 7200
    assert plan['jobs'][0]['reused']['directory'] == str(old.resolve())
    pilot.validate(out)
    (snapshot / 'vocab.json').write_text('changed')
    with pytest.raises(ValueError, match='cache changed'):
        pilot.validate(out)


def test_cpu_offline_environment_and_no_gpu(modules):
    pilot, _ = modules
    env = pilot.environment('/fixture/cache')
    assert env['CUDA_VISIBLE_DEVICES'] == '' and env['HF_HUB_OFFLINE'] == '1'
    assert env['TRANSFORMERS_OFFLINE'] == '1' and env['OMP_NUM_THREADS'] == '2' and env['MKL_NUM_THREADS'] == '2'


def test_generic_fetch_has_no_six_capture_limit_and_validates_bundle(modules, tmp_path):
    pilot, worker = modules
    pair = pilot.preflight(Tokenizer())[0][0]; original = tmp_path / 'remote'
    make_capture(pilot, original, pair, 5)
    files = {n: base64.b64encode((original / n).read_bytes()).decode() for n in
             ['capture.json', 'private_inputs.json', 'activations.safetensors', 'checksums.json']}
    seal = pilot.sha(original / 'checksums.json')
    def requester(action, env, deployment, known):
        if seal in known:
            return {'status': 'no_new_capture'}
        return {'capture_name': 'cell-040-attempt-001', 'seal_sha256': seal, 'files': files}
    target = tmp_path / 'local'
    assert worker.fetch_one('isolated.env', {'release_name': 'interp-grid-fixture'}, target, requester)
    assert not worker.fetch_one('isolated.env', {'release_name': 'interp-grid-fixture'}, target, requester)
    assert len(list(target.glob('*/checksums.json'))) == 1
    bad = dict(files); bad['capture.json'] = base64.b64encode(b'changed').decode()
    def corrupted(*args, **kwargs):
        return {'capture_name': 'cell-041-attempt-001', 'seal_sha256': seal, 'files': bad}
    with pytest.raises(ValueError, match='files mismatch'):
        worker.fetch_one('isolated.env', {}, tmp_path / 'bad', corrupted)


def test_minimal_worker_bundle_excludes_environment_and_runtime_data(modules, tmp_path, monkeypatch):
    _, worker = modules
    root = tmp_path / 'source'; (root / 'src/contagion').mkdir(parents=True); (root / 'scripts').mkdir()
    (root / 'src/contagion/neural.py').write_text('fixture')
    (root / 'scripts/expanded_trained_pilot.py').write_text('fixture')
    (root / '.env').write_text('PRIVATE=fixture')
    monkeypatch.setattr(worker, 'ROOT', root)
    bundle = root / 'results/reference.tar.gz'; worker.build_bundle(bundle)
    with tarfile.open(bundle) as archive:
        assert set(archive.getnames()) == {'src/contagion/neural.py', 'scripts/expanded_trained_pilot.py', 'worker-manifest.json'}
    compile(worker.REMOTE, '<bounded-reference-operator>', 'exec')


def test_remote_diagnostic_emits_only_allowlisted_reasons_not_private_logs(modules, tmp_path, monkeypatch):
    _, worker = modules
    base = tmp_path / 'private-worker'; release = base / 'interp-grid-fixture'
    output = release / 'results/expanded-reference'; output.mkdir(parents=True)
    (release / 'deployment.private.json').write_text(json.dumps({'output': str(output)}))
    (output / 'expanded-status.private.json').write_text(json.dumps({'status': 'stopped', 'error_type': 'ValueError', 'completed': []}))
    (release / 'worker.private.log').write_text('NEVER_ECHO_THIS_PRIVATE_LINE\nValueError: CPU reference worker cooling or sensor review required\n')
    read = Path.read_text
    def read_text(path, *args, **kwargs):
        if str(path) == '/proc/meminfo':
            return 'MemAvailable: 8388608 kB\n'
        return read(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read_text)
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps({'project': str(base), 'action': 'diagnose', 'release_name': release.name})))
    captured = io.StringIO(); monkeypatch.setattr(sys, 'stdout', captured)
    with pytest.raises(SystemExit):
        exec(compile(worker.REMOTE, '<bounded-reference-operator>', 'exec'), {})
    data = json.loads(captured.getvalue())
    assert data['coordinator_reason_code'] == 'cpu_cooling_or_sensor_guard'
    assert 'NEVER_ECHO' not in captured.getvalue() and str(base) not in captured.getvalue()
