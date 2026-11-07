from pathlib import Path
import runpy
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = runpy.run_path(str(ROOT / 'scripts/security_guard.py'))


def repo(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    return tmp_path


def stage(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    subprocess.run(['git', 'add', '--', name], cwd=root, check=True)
    return path


@pytest.mark.parametrize('name', ['.env', '.env.production', 'sub/.ENV', 'results/run/events.jsonl',
                                  '.aws/credentials', 'key.pem', 'private.redact.txt',
                                  'dashboard/data/raw.json', 'other/events.jsonl'])
def test_private_paths_blocked(name):
    assert GUARD['blocked_path'](name)


@pytest.mark.parametrize('name', ['.env.example', 'README.md', 'dashboard/data/results.json',
                                  'tests/fixtures/mock_run/mock/events.jsonl'])
def test_intended_paths_allowed(name):
    assert not GUARD['blocked_path'](name)


def test_index_secret_cannot_be_hidden_by_clean_worktree(tmp_path, capsys):
    root = repo(tmp_path)
    secret = ''.join(['opaque', 'UnitTest', 'Credential', '123'])
    (root / '.env').write_text(f'CONTAGION_API_KEY={secret}\n')
    path = stage(root, 'sample.txt', secret)
    path.write_text('clean working copy')
    assert GUARD['check'](root, 'staged', env={}) == 1
    assert secret not in capsys.readouterr().err


def test_forced_private_file_is_blocked(tmp_path):
    root = repo(tmp_path)
    stage(root, '.env', 'CONTAGION_MODEL=fixture\n')
    assert GUARD['check'](root, 'staged', env={}) == 1


def test_symlink_does_not_read_private_target(tmp_path):
    root = repo(tmp_path)
    (root / '.env').write_text('CONTAGION_MODEL=fixture\n')
    (root / 'alias.txt').symlink_to(root / '.env')
    assert GUARD['check'](root, 'worktree', env={}) == 1


def test_public_index_is_validated_not_worktree(tmp_path):
    root = repo(tmp_path)
    path = stage(root, 'dashboard/data/results.json', '{"private_history": []}')
    path.write_text('{}')
    assert GUARD['check'](root, 'staged', env={}) == 1


def test_thinking_comparison_has_matched_budgets():
    import yaml
    from contagion.config import RunConfig
    on = yaml.safe_load((ROOT/'configs/rq1_pair_thinking_enabled.yaml').read_text())
    off = yaml.safe_load((ROOT/'configs/rq1_pair_thinking_disabled_matched.yaml').read_text())
    assert on['base']['thinking'] == 'enabled' and off['base']['thinking'] == 'disabled'
    assert RunConfig(**on['base']).protocol_version == '1.1'
    assert RunConfig(**off['base']).protocol_version == '1.1'
    on['base'].pop('thinking')
    off['base'].pop('thinking')
    assert on == off


def test_dangling_symlink_is_also_blocked(tmp_path):
    root = repo(tmp_path)
    (root / 'dangling.txt').symlink_to(root / 'missing-private-key')
    assert GUARD['check'](root, 'worktree', env={}) == 1
