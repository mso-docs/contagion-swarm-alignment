import importlib.util
import json
from pathlib import Path
import tarfile

import pytest

ROOT=Path(__file__).resolve().parents[1]


def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def test_worker_bundle_excludes_config_secrets_and_runtime_results(tmp_path):
    prepare=module('prepare_worker')
    (tmp_path/'src').mkdir();(tmp_path/'src/code.py').write_text('print(1)')
    (tmp_path/'results').mkdir();(tmp_path/'results/private.json').write_text('private secret')
    (tmp_path/'.env').write_text('private secret');(tmp_path/'.env.example').write_text('CONTAGION_BASE_URL=')
    (tmp_path/'.git').mkdir();(tmp_path/'.git/config').write_text('private secret')
    out=tmp_path/'results/worker.tar.gz'
    assert prepare.build(out,tmp_path)==2
    with tarfile.open(out) as archive:
        assert set(archive.getnames())=={'contagion-worker/src/code.py','contagion-worker/.env.example','contagion-worker/worker-manifest.json'}
        manifest=json.load(archive.extractfile('contagion-worker/worker-manifest.json'))
        assert len(manifest['files'])==2
    with pytest.raises(FileExistsError):prepare.build(out,tmp_path)
    with pytest.raises(ValueError):prepare.build(tmp_path/'public.tar.gz',tmp_path)


def test_worker_bundle_rejects_symlink(tmp_path):
    prepare=module('prepare_worker');(tmp_path/'scripts').mkdir()
    (tmp_path/'scripts/link.py').symlink_to('/etc/passwd')
    with pytest.raises(ValueError):prepare.build(tmp_path/'results/bundle.tar.gz',tmp_path)


def test_worker_inventory_does_not_disclose_host_or_environment(monkeypatch):
    setup=module('setup_worker')
    monkeypatch.setenv('CONTAGION_API_KEY','private-test-value')
    result=setup.inventory()
    assert 'hostname' not in result and 'private-test-value' not in json.dumps(result)
    assert 'architecture' in result and 'free_disk_gib' in result


def test_private_remote_fields_are_data_and_public_redactor_knows_them(tmp_path,monkeypatch):
    from contagion.publication import Redactor,sensitive_values
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    remote=module('remote_worker')
    path=tmp_path/'.env'
    path.write_text('PRIMARY_SERVER_ID=test-user@fixture.invalid\nPRIMARY_PROJECT_DIR=~/private-worker-dir\n')
    target,project=remote.configuration(path,'primary')
    assert target=='test-user@fixture.invalid' and project=='~/private-worker-dir'
    redact=Redactor(sensitive_values({'PRIMARY_SERVER_ID':target,'PRIMARY_PROJECT_DIR':project}))
    assert redact(target)=='[REDACTED]' and redact(project)=='[REDACTED]'
    assert redact('fixture.invalid')=='[REDACTED]'
    path.write_text('PRIMARY_SERVER_ID=-oProxyCommand=bad\nPRIMARY_PROJECT_DIR=/\n')
    with pytest.raises(ValueError):remote.configuration(path,'primary')


def test_remote_capture_timeout_and_private_error_handling(tmp_path,monkeypatch):
    from types import SimpleNamespace
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    remote=module('remote_worker')
    monkeypatch.setattr(remote,'ROOT',tmp_path)
    monkeypatch.setattr(remote,'configuration',lambda *args:('fixture.invalid','~/worker'))
    source=tmp_path/'src/contagion/neural.py';source.parent.mkdir(parents=True);source.write_text('# test source')
    calls=[]
    def run(command,**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(returncode=255,stdout='',stderr='Permission denied for private-login-value')
    monkeypatch.setattr(remote.subprocess,'run',run)
    with pytest.raises(RuntimeError,match='ssh_authentication_failed') as error:
        remote.execute('primary','smoke',tmp_path/'.env')
    assert 'private-login-value' not in str(error.value)
    assert calls[0]['timeout']==210
    import ast
    ast.parse(remote.REMOTE)
    assert "'results/'+capture_name" in remote.REMOTE
