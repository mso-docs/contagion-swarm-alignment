from pathlib import Path
import runpy

ROOT=Path(__file__).resolve().parents[1]


def test_dependency_policy_rejects_code_permissions_unknown_pins_and_human_scope():
    policy=runpy.run_path(str(ROOT/'scripts/dependabot_automerge.py'));pin=next(iter(policy['APPROVED']['actions/checkout']))
    patch='-      - uses: actions/checkout@'+'a'*40+' # old\n+      - uses: actions/checkout@'+pin+' # reviewed'
    file={'filename':'.github/workflows/pages.yml','status':'modified','patch':patch}
    assert policy['safe_diff']([file])
    assert not policy['safe_diff']([{**file,'filename':'src/contagion/controller.py'}])
    assert not policy['safe_diff']([{**file,'patch':patch+'\n+permissions: write-all'}])
    assert not policy['safe_diff']([{**file,'patch':patch.replace(pin,'b'*40)}])
    assert not policy['safe_diff']([{**file,'patch':''}])
