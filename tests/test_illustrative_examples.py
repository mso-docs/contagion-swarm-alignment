import importlib
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def examples(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return importlib.import_module('illustrative_examples')


def test_illustrations_keep_actual_label_scope_and_unresolved_disagreement(examples):
    data=examples.validate(ROOT/'report/data/illustrative_examples.json')
    assert [r.strict_flag for r in data.examples]==[True,True,False]
    assert all(r.human_label=='compliant' and 'not a new independent adjudication' in r.context for r in data.examples)
    assert data.examples[1].source_seal_sha256==data.examples[2].source_seal_sha256
    assert data.examples[1].agent_id!=data.examples[2].agent_id


def test_modified_labels_and_private_free_text_are_rejected(examples,tmp_path):
    from contagion.config import digest
    source=json.loads((ROOT/'report/data/illustrative_examples.json').read_text())
    path=tmp_path/'examples.json'
    changed=json.loads(json.dumps(source));changed['examples'][0]['human_label']='violation'
    changed['examples_hash']=digest({k:v for k,v in changed.items() if k!='examples_hash'})
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError):examples.validate(path)
    changed=json.loads(json.dumps(source));changed['examples'][0]['artifact']='Contact researcher@example.org'
    changed['examples_hash']=digest({k:v for k,v in changed.items() if k!='examples_hash'})
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError,match='privacy'):examples.validate(path)


def test_bundle_closure_includes_imports_without_executing_them(monkeypatch,tmp_path):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    from research_bundle import source_dependencies
    scripts=tmp_path/'scripts';scripts.mkdir()
    (scripts/'entry.py').write_text('from dependency import value\n')
    (scripts/'dependency.py').write_text('import nested\nraise RuntimeError("must not execute")\n')
    (scripts/'nested.py').write_text('value=42\n')
    assert source_dependencies(['scripts/entry.py'],tmp_path)==['scripts/dependency.py','scripts/entry.py','scripts/nested.py']
