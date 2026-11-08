import importlib
import io
from pathlib import Path
from types import SimpleNamespace


def request(tmp_path,monkeypatch,host='localhost:8780',path='/artifacts.html',origin=None):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    module=importlib.import_module('serve_private_reviews');cls=module.handler_type(tmp_path);obj=cls.__new__(cls)
    obj.path=path;obj.headers={'Host':host};obj.server=SimpleNamespace(server_port=8780);obj.wfile=io.BytesIO();obj.codes=[];obj.sent={}
    if origin:obj.headers['Origin']=origin
    obj.send_error=lambda code:obj.codes.append(code);obj.send_response=lambda code:obj.codes.append(code);obj.send_header=lambda k,v:obj.sent.update({k:v});obj.end_headers=lambda:None
    return obj


def test_private_service_only_serves_allowlisted_pages(tmp_path,monkeypatch):
    (tmp_path/'artifacts-v2.html').write_text('private evidence')
    valid=request(tmp_path,monkeypatch);valid.do_GET();assert valid.codes==[200] and valid.sent['Cache-Control']=='no-store'
    for path in ['/','/.env','/../artifacts.html','/%2e%2e/.env','/review_inputs.json','/repository-quality.tmp']:
        obj=request(tmp_path,monkeypatch,path=path);obj.do_GET();assert obj.codes==[404]


def test_private_service_rejects_foreign_host_origin_and_writes(tmp_path,monkeypatch):
    for host in ['example.org:8780','localhost:bad','localhost:9999','user@localhost:8780']:
        obj=request(tmp_path,monkeypatch,host=host);obj.do_GET();assert obj.codes==[403]
    obj=request(tmp_path,monkeypatch,origin='https://example.org');obj.do_GET();assert obj.codes==[403]
    for name in ['do_POST','do_PUT','do_DELETE']:
        obj=request(tmp_path,monkeypatch);getattr(obj,name)();assert obj.codes==[405]


def test_private_service_rejects_symlink(tmp_path,monkeypatch):
    (tmp_path/'sensitive').write_text('private');(tmp_path/'artifacts-v2.html').symlink_to(tmp_path/'sensitive')
    obj=request(tmp_path,monkeypatch);obj.do_GET();assert obj.codes==[404]
