"""The paper must distinguish operational scores from the supplied human review."""
import importlib
from pathlib import Path


def test_supplement_preserves_negative_human_labels_and_posthoc_scope(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    module=importlib.import_module('paper_supplement')
    text,hashes=module.render()
    assert '16/16' in text and '0 positive violation labels' in text
    assert 'Strict scorer & 16 & 4 & 0' in text
    assert 'Local judge & 16 & 9 & 0' in text
    assert 'Frontier judge & 11 & 2 & 0' in text
    assert 'post-hoc sensitivity endpoint' in text and 'do not establish which interpretation is correct' in text
    assert '17; wrapper-sensitive proposals total 20' in text
    assert set(hashes)==set(module.INPUTS)


def test_final_inventory_is_separate_and_bound(monkeypatch):
    import json
    root=Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root/'scripts'))
    module=importlib.import_module('paper_supplement')
    text,hashes=module.render()
    counts=json.loads((root/'report/data/final_inventory.json').read_text())['counts']
    assert f"{counts['live_rows']} live indexed rows" in text
    assert f"{counts['live_distinct_returned_responses']} returned responses" in text
    assert 'not independent scientific replicates' in text
    assert 'defensive cybersecurity & 0 & 0 & 9' in text
    assert 'final_inventory_sha256' in hashes and 'final_inventory_script_sha256' in hashes


def test_illustrations_preserve_human_disagreement_and_distinct_agents(monkeypatch):
    root=Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root/'scripts'))
    module=importlib.import_module('paper_supplement')
    text,hashes=module.render()
    assert text.count('supplied human label: compliant')==3
    assert 'unresolved rubric disagreement' in text
    assert 'different agents' in text and 'do not establish within-agent recovery' in text
    assert '42ca903ce39e310d' in text and '/tests/expected' in text
    assert 'illustrative_examples_sha256' in hashes
