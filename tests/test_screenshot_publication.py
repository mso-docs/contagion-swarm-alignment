import hashlib
import importlib
import json
from pathlib import Path
import struct
import zlib

import pytest

ROOT = Path(__file__).resolve().parents[1]


def chunk(kind, data):
    return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data)&0xffffffff)


@pytest.fixture
def fixture(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    module = importlib.import_module('screenshot_publication')
    png = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))+chunk(b'IDAT', zlib.compress(b'\0\0\0\0'))+chunk(b'IEND', b'')
    row = {'file': 'docs/images/example.png', 'sha256': hashlib.sha256(png).hexdigest(),
           'width': 1, 'height': 1, 'caption': 'Reviewed screenshot', 'source': 'public_snapshot',
           'privacy_reviewed': True, 'ocr_checked': True}
    manifest = {'schema_version': 'reviewed-screenshots-1.0', 'screenshots': [row]}
    return module, png, manifest


def test_exact_approved_pixels_are_required(fixture):
    module, png, manifest = fixture
    module.validate_screenshot('docs/images/example.png', png, json.dumps(manifest))
    with pytest.raises(ValueError, match='approval'):
        module.validate_screenshot('docs/images/other.png', png, json.dumps(manifest))
    with pytest.raises(ValueError, match='changed'):
        module.validate_screenshot('docs/images/example.png', png+b'extra', json.dumps(manifest))


def test_metadata_cannot_be_approved_by_changing_the_hash(fixture):
    module, png, manifest = fixture
    png = png[:-12]+chunk(b'tEXt', b'private metadata')+png[-12:]
    manifest['screenshots'][0]['sha256'] = hashlib.sha256(png).hexdigest()
    with pytest.raises(ValueError, match='metadata'):
        module.validate_screenshot('docs/images/example.png', png, json.dumps(manifest))


def test_missing_privacy_review_and_trailing_content_are_rejected(fixture):
    module, png, manifest = fixture
    manifest['screenshots'][0]['privacy_reviewed'] = False
    with pytest.raises(ValueError, match='Unreviewed'):
        module.validate_screenshot('docs/images/example.png', png, json.dumps(manifest))
    with pytest.raises(ValueError, match='trailing'):
        module.inspect_png(png+b'private appended text')
