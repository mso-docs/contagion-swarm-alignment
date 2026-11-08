"""Serve exactly two private review pages on loopback; no writes, indexes or raw files."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
PAGES={'/artifacts.html':'artifacts-v2.html','/repository-quality.html':'repository-quality-v2.html','/artifact-triage.html':'triage/artifact-triage.html','/repository-long.html':'quality-long/repository-quality.html'}


def handler_type(directory):
    directory=Path(directory).resolve()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                host=urlsplit('http://'+self.headers.get('Host',''))
                allowed=host.hostname in {'127.0.0.1','localhost'} and host.port==self.server.server_port and not host.username and not host.password
                origin=self.headers.get('Origin')
                if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}:allowed=False
            except ValueError:allowed=False
            if not allowed:self.send_error(403);return
            name=PAGES.get(urlsplit(self.path).path)
            if name is None:self.send_error(404);return
            path=directory/name
            if path.is_symlink() or not path.is_file() or path.stat().st_size>16*1024*1024 or directory not in path.resolve().parents:
                self.send_error(404);return
            body=path.read_bytes()
            self.send_response(200)
            for key,value in {'Content-Type':'text/html; charset=utf-8','Content-Length':str(len(body)),'Cache-Control':'no-store',
                              'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Cross-Origin-Resource-Policy':'same-origin',
                              'Content-Security-Policy':"frame-ancestors 'none'; base-uri 'none'; form-action 'none'; object-src 'none'"}.items():self.send_header(key,value)
            self.end_headers();self.wfile.write(body)
        def do_POST(self):self.send_error(405)
        def do_PUT(self):self.send_error(405)
        def do_DELETE(self):self.send_error(405)
        def log_message(self,*args):pass
    return Handler


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=ROOT/'results/reviews/workspaces');p.add_argument('--port',type=int,default=8780);a=p.parse_args()
    base=a.directory.resolve()
    if (ROOT/'results/reviews').resolve() not in base.parents or not 1024<=a.port<=65535:raise ValueError('Use a private review directory and unprivileged port')
    server=ThreadingHTTPServer(('127.0.0.1',a.port),handler_type(base));print(f'Private review pages ready on loopback port{a.port}; no files are written.',flush=True);server.serve_forever()
