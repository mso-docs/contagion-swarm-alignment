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


@pytest.mark.parametrize('name', ['renamed.log', 'capture.safetensors', 'session.har',
                                  'experiment.sqlite', 'archive/traces.json', 'logs/output.txt',
                                  'traces/output.txt'])
def test_raw_artifact_aliases_are_blocked(name):
    assert GUARD['blocked_path'](name)


def test_personal_email_in_staged_file_is_blocked_without_echo(tmp_path, capsys):
    root = repo(tmp_path)
    address = 'researcher' + '@' + 'private-mail.dev'
    path = stage(root, 'notes.md', 'Contact: ' + address)
    path.write_text('Clean unstaged replacement')
    assert GUARD['check'](root, 'staged', env={}) == 1
    report = capsys.readouterr().err
    assert 'email' in report
    assert address not in report


def test_alternate_dotenv_and_denylist_are_read_as_data(tmp_path, capsys):
    root = repo(tmp_path)
    secret = 'opaque' + 'PrivateJudgeCredential123'
    person = 'Synthetic' + 'PrivatePerson'
    (root / '.env.judge').write_text('OPENROUTER_API_KEY=' + secret + '\n')
    (root / 'private.redact.txt').write_text(person + '\n')
    stage(root, 'notes.md', secret + '\n' + person)
    assert GUARD['check'](root, 'staged', env={}) == 1
    report = capsys.readouterr().err
    assert secret not in report and person not in report


def test_privacy_scan_decodes_json_escapes_and_never_alters_input(monkeypatch):
    import json
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    scanner = runpy.run_path(str(ROOT / 'scripts/scan_privacy.py'))
    address = 'someone' + '@' + 'private-mail.dev'
    blob = json.dumps({'content': address}).replace('@', '\\u0040').encode()
    assert scanner['scan_blob'](blob, public=True)['email'] == 1
    assert b'\\u0040' in blob
    assert scanner['findings']('Contact: reader' + '@' + 'example.com') == {}
    assert scanner['findings']('reader' + '@' + 'example.com', public=True)['email'] == 1
    pii = ' '.join(['415' + '-555-0134', '123' + '-45-6789', '4111' + ' 1111 1111 1111'])
    result = scanner['findings'](pii, public=True)
    assert result['phone'] and result['government_id'] and result['payment_card']
    assert not scanner['findings']('2026-11-08T01:06:48.920256+00:00', public=True)
    assert not scanner['findings']('1.959963984540054', public=True)  # Scientific decimal, not a card number.


def test_public_endpoint_examples_do_not_waive_private_hosts_or_credentials(tmp_path):
    root=repo(tmp_path)
    key=''.join(['unit','Credential','01234567890123456789'])
    (root/'.env').write_text(f'CONTAGION_BASE_URL=https://openrouter.ai/api/v1\nCONTAGION_API_KEY={key}\nSECONDARY_SERVER_ID=user@private-host.example\n')
    stage(root,'client.py','BASE="https://openrouter.ai/api/v1"\n')
    assert GUARD['check'](root,'staged',env={})==0
    stage(root,'secret.py',f'KEY="{key}"\n')
    assert GUARD['check'](root,'staged',env={})==1
    known,values=GUARD['private_values'](root,{})
    assert 'https://openrouter.ai/api/v1' in known  # Public trace redaction remains strict.
    filtered=GUARD['source_configuration_values'](known,values)
    assert key in filtered and 'user@private-host.example' in filtered


def test_unknown_absolute_home_path_is_blocked_without_echo(tmp_path, capsys):
    root = repo(tmp_path)
    private_path = '/' + 'home' + '/unrelated-person/private.txt'
    stage(root, 'notes.md', private_path)
    assert GUARD['check'](root, 'staged', env={}) == 1
    assert private_path not in capsys.readouterr().err


def test_only_closed_research_snapshot_gets_larger_numeric_review_budget(tmp_path, monkeypatch):
    from contagion.research_publication import ResearchSnapshot
    root = repo(tmp_path)
    function = GUARD['check']
    monkeypatch.setitem(function.__globals__, 'MAX_BYTES', 64)
    snapshot = ResearchSnapshot(generated_utc='2026-11-08T00:00:00+00:00', limitations=[])
    stage(root, 'dashboard/data/research.json', snapshot.model_dump_json())
    assert function(root, 'staged', env={}) == 0
    stage(root, 'oversized.json', ' ' * 65)
    assert function(root, 'staged', env={}) == 1
