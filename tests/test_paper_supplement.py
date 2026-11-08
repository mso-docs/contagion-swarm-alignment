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
