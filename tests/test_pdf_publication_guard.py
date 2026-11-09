import importlib
import io
from pathlib import Path
import runpy
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def validator(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    return importlib.import_module('pdf_publication_guard').validate_public_pdf


def pdf(*, title='Public paper fixture', javascript=False, attachment=False, uri=None, creation_date=None):
    pypdf = pytest.importorskip('pypdf')
    from pypdf.generic import DictionaryObject, NameObject, TextStringObject, ArrayObject, NumberObject
    writer = pypdf.PdfWriter(); writer.add_blank_page(width=300, height=300)
    writer.add_metadata({'/Title': title})
    if creation_date:
        writer.add_metadata({'/CreationDate': creation_date})
    if javascript:
        writer._root_object[NameObject('/OpenAction')] = DictionaryObject({NameObject('/S'): NameObject('/JavaScript'),
            NameObject('/JS'): TextStringObject('app.alert("fixture")')})
    if attachment:
        writer.add_attachment('fixture.txt', b'fixture')
    if uri:
        writer.add_annotation(0, DictionaryObject({NameObject('/Type'): NameObject('/Annot'),
            NameObject('/Subtype'): NameObject('/Link'), NameObject('/Rect'): ArrayObject([NumberObject(n) for n in [0, 0, 10, 10]]),
            NameObject('/A'): DictionaryObject({NameObject('/S'): NameObject('/URI'), NameObject('/URI'): TextStringObject(uri)})}))
    stream = io.BytesIO(); writer.write(stream); return stream.getvalue()


def test_public_pdf_metadata_is_scanned_and_normal_reference_link_allowed(validator):
    result = validator(pdf(uri='https://example.org/paper?id=public-fixture'))
    assert result['pages'] == 1 and result['reference_links'] == 1
    secret = 'fixture' + 'PrivateCredential' + '2026'
    with pytest.raises(ValueError, match='privacy|private'):
        validator(pdf(title=secret), known={secret})
    with pytest.raises(ValueError, match='privacy'):
        validator(pdf(title='/' + 'Users' + '/private-person/paper.tex'))


def test_typed_calendar_valid_pdf_date_is_not_a_payment_card(validator):
    import scan_privacy
    dates = [f"D:202611081212{second:02d}-00'00'" for second in range(60)]
    date = next(value for value in dates if scan_privacy.findings(value, public=True).get('payment_card'))
    assert validator(pdf(creation_date=date))['pages'] == 1


@pytest.mark.parametrize('options', [{'javascript': True}, {'attachment': True},
    {'uri': 'https://private-host' + '.internal/paper'}, {'uri': 'https://127.0.0.1/paper'},
    {'uri': 'https://example.org/paper?access_token=fixture'}, {'uri': 'http://example.org/paper'}])
def test_pdf_active_content_and_private_links_fail_closed(validator, options):
    with pytest.raises(ValueError):
        validator(pdf(**options))


def test_only_named_pdf_path_is_admitted_and_index_bytes_are_used(validator, tmp_path, monkeypatch, capsys):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    guard = runpy.run_path(str(ROOT / 'scripts/security_guard.py'))
    assert guard['blocked_path']('report/other.pdf') and not guard['blocked_path']('report/paper.pdf')
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    target = tmp_path / 'report/paper.pdf'; target.parent.mkdir()
    target.write_bytes(pdf())
    subprocess.run(['git', 'add', 'report/paper.pdf'], cwd=tmp_path, check=True)
    assert guard['check'](tmp_path, 'staged', env={}) == 0
    secret = 'fixture' + 'PrivateCredential' + '2026'
    (tmp_path / '.env').write_text('CONTAGION_API_KEY=' + secret + '\n')
    target.write_bytes(pdf(title=secret)); subprocess.run(['git', 'add', 'report/paper.pdf'], cwd=tmp_path, check=True)
    target.write_bytes(pdf())
    assert guard['check'](tmp_path, 'staged', env={}) == 1
    assert secret not in capsys.readouterr().err
