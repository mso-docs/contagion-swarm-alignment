"""A source archive must enforce private literals outside public JSON too."""
import pytest
from pathlib import Path
import importlib

@pytest.fixture
def validate_text(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    return importlib.import_module('research_bundle').validate_text


def test_bundle_blocks_private_configuration_in_source_and_json(validate_text):
    private='private-worker-fixture.invalid'
    for suffix,blob in [('.py',f'HOST = "{private}"'.encode()),('.json',f'{{"host":"{private}"}}'.encode())]:
        with pytest.raises(ValueError,match='privacy lint'):
            validate_text(blob,suffix,{private},{'PRIMARY_SERVER_ID':private})


def test_public_endpoint_exception_is_source_only_and_never_a_credential(validate_text):
    endpoint='https://openrouter.ai/api/v1'
    validate_text(f'ENDPOINT = "{endpoint}"'.encode(),'.py',{endpoint},{'CONTAGION_BASE_URL':endpoint})
    with pytest.raises(ValueError,match='privacy lint'):
        validate_text(f'{{"endpoint":"{endpoint}"}}'.encode(),'.json',{endpoint},{'CONTAGION_BASE_URL':endpoint})
    with pytest.raises(ValueError,match='privacy lint'):
        validate_text(f'KEY = "{endpoint}"'.encode(),'.py',{endpoint},{'CONTAGION_API_KEY':endpoint})
