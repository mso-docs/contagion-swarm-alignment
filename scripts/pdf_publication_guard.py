"""Narrow inspection for the explicitly approved report/paper.pdf artifact."""
import hashlib
import io
import ipaddress
import re
from datetime import datetime
from urllib.parse import parse_qsl, unquote, urlsplit


def validate_public_pdf(data, known=()):
    from pypdf import PdfReader
    from pypdf.generic import DictionaryObject, IndirectObject, StreamObject
    from scan_privacy import findings
    if not data.startswith(b'%PDF-') or len(data) > 5 * 1024 * 1024:
        raise ValueError('Unexpected public paper binary or size')
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 60:
        raise ValueError('Encrypted or oversized paper rejected')
    strings = []; urls = []; seen = set()
    forbidden_keys = {'/JS', '/JavaScript', '/EmbeddedFiles', '/EF', '/AF', '/AA', '/AcroForm', '/XFA', '/RichMedia', '/Launch'}
    forbidden_actions = {'/JavaScript', '/Launch', '/SubmitForm', '/ImportData', '/GoToR', '/GoToE',
                         '/Rendition', '/Sound', '/Movie', '/SetOCGState', '/Hide', '/Thread', '/ResetForm'}
    def walk(value, depth=0):
        if depth > 100 or len(seen) > 100000:
            raise ValueError('Paper object complexity exceeds inspection limit')
        if isinstance(value, IndirectObject):
            key = (value.idnum, value.generation)
            if key in seen:
                return
            seen.add(key); value = value.get_object()
        if isinstance(value, DictionaryObject):
            if set(map(str, value)) & forbidden_keys or value.get('/Type') == '/Filespec' or value.get('/S') in forbidden_actions:
                raise ValueError('Active content or embedded files rejected')
            for key, child in value.items():
                if str(key) in {'/CreationDate', '/ModDate'} and isinstance(child, str) and re.fullmatch(r"D:\d{14}(?:Z|[+-]\d{2}'\d{2}')?", child):
                    # Typed PDF timestamps are not card numbers. Validate the
                    # calendar before rendering them as an unambiguous ISO date.
                    strings.append(datetime.strptime(child[2:16], '%Y%m%d%H%M%S').isoformat())
                    continue
                if str(key) in {'/A', '/OpenAction'}:
                    action = child.get_object() if isinstance(child, IndirectObject) else child
                    if isinstance(action, DictionaryObject) and action.get('/S') not in {'/GoTo', '/URI'}:
                        raise ValueError('Unsupported PDF action rejected')
                if str(key) == '/URI' and isinstance(child, str):
                    urls.append(str(child))
                walk(child, depth + 1)
            if isinstance(value, StreamObject) and (value.get('/Type') == '/Metadata' or value.get('/Subtype') == '/XML'):
                metadata = value.get_data()
                if len(metadata) > 1024 * 1024:
                    raise ValueError('Paper metadata stream too large')
                strings.append(metadata.decode('utf-8'))
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child, depth + 1)
        elif isinstance(value, str):
            strings.append(str(value))
        elif isinstance(value, bytes):
            try:
                strings.append(value.decode('utf-8'))
            except UnicodeError:
                pass  # Font/image streams are not treated as free-text documents.
    walk(reader.trailer)
    for page in reader.pages:
        strings.append(page.extract_text() or '')
    for uri in urls:
        parsed = urlsplit(uri)
        host = (parsed.hostname or '').lower()
        if (parsed.scheme != 'https' or not host or parsed.username or parsed.password
                or '.' not in host or host.endswith(('.local', '.internal', '.lan', '.localhost', '.ts.net', '.invalid', '.test'))):
            raise ValueError('Private or credential-bearing paper link rejected')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError('Paper links may not use numeric host addresses')
        if any(re.search(r'key|token|auth|password|secret|credential|session|signature', key, re.I) for key, _ in parse_qsl(parsed.query)):
            raise ValueError('Credential-like paper link query rejected')
        strings.append(unquote(uri))
    text = '\n'.join(strings)
    if findings(text, public=True, known=known):
        raise ValueError('Public paper text or metadata failed privacy lint')
    compact = re.sub(r'\s+', '', text).casefold()
    if any(value and len(value) >= 8 and re.sub(r'\s+', '', value).casefold() in compact for value in known):
        raise ValueError('Known private paper value rejected')
    return {'sha256': hashlib.sha256(data).hexdigest(), 'pages': len(reader.pages),
            'reference_links': len(urls), 'audited_text': text}
