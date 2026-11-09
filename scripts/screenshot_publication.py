"""Allow only hash-bound, reviewed PNG screenshots with no text/EXIF metadata."""
import hashlib
import json
from pathlib import PurePosixPath
import struct
import zlib

PREFIX = 'docs/images/'
MANIFEST = PREFIX+'screenshots.json'
SAFE_CHUNKS = {b'IHDR', b'PLTE', b'IDAT', b'IEND', b'sRGB', b'gAMA', b'cHRM', b'tRNS'}


def inspect_png(data):
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) > 5*1024*1024:
        raise ValueError('Invalid or oversized screenshot')
    offset = 8
    dimensions = None
    ended = False
    compressed = []
    channels = None
    while offset < len(data):
        if offset+12 > len(data):
            raise ValueError('Truncated PNG')
        size = struct.unpack('>I', data[offset:offset+4])[0]
        kind = data[offset+4:offset+8]
        end = offset+12+size
        if kind not in SAFE_CHUNKS or end > len(data):
            raise ValueError('Unapproved PNG metadata or chunk')
        payload = data[offset+8:offset+8+size]
        crc = struct.unpack('>I', data[end-4:end])[0]
        if zlib.crc32(kind+payload) & 0xffffffff != crc:
            raise ValueError('PNG checksum mismatch')
        if dimensions is None:
            if kind != b'IHDR' or size != 13:
                raise ValueError('Missing PNG dimensions')
            dimensions = struct.unpack('>II', payload[:8])
            if any(not 1 <= d <= 4096 for d in dimensions):
                raise ValueError('Unbounded screenshot dimensions')
            depth, color, compression, filtering, interlace = payload[8:]
            if depth != 8 or color not in {2, 6} or (compression, filtering, interlace) != (0, 0, 0):
                raise ValueError('Unsupported screenshot encoding')
            channels = 3 if color == 2 else 4
        elif kind == b'IHDR':
            raise ValueError('Repeated PNG header')
        offset = end
        if kind == b'IDAT':
            compressed.append(payload)
        if kind == b'IEND':
            if size or offset != len(data):
                raise ValueError('PNG trailing content')
            ended = True
    if not ended:
        raise ValueError('Unterminated PNG')
    stride = 1+dimensions[0]*channels
    expected = stride*dimensions[1]
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(b''.join(compressed), expected+1)
    if len(pixels) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('Invalid screenshot pixel stream')
    if any(pixels[i] > 4 for i in range(0, expected, stride)):
        raise ValueError('Invalid PNG row filter')
    return dimensions


def validate_screenshot(name, data, manifest):
    value = json.loads(manifest)
    if set(value) != {'schema_version', 'screenshots'} or value['schema_version'] != 'reviewed-screenshots-1.0':
        raise ValueError('Invalid screenshot manifest')
    rows = value['screenshots']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 12:
        raise ValueError('Unbounded screenshot inventory')
    names = set()
    for row in rows:
        if set(row) != {'file', 'sha256', 'width', 'height', 'caption', 'source', 'privacy_reviewed', 'ocr_checked'}:
            raise ValueError('Unknown screenshot metadata')
        path = PurePosixPath(row['file'])
        if path.parent.as_posix() != PREFIX.rstrip('/') or path.suffix != '.png' or row['file'] in names:
            raise ValueError('Invalid screenshot path')
        if row['privacy_reviewed'] is not True or row['ocr_checked'] is not True:
            raise ValueError('Unreviewed screenshot')
        names.add(row['file'])
    selected = [row for row in rows if row['file'] == name]
    if len(selected) != 1:
        raise ValueError('Screenshot lacks exact approval')
    row = selected[0]
    if hashlib.sha256(data).hexdigest() != row['sha256']:
        raise ValueError('Screenshot changed after review')
    if inspect_png(data) != (row['width'], row['height']):
        raise ValueError('Screenshot dimensions changed')
