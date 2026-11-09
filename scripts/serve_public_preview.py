"""Build/serve the exact allowlisted Pages artifact on loopback, with no private APIs."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from build_dashboard import build
from publication_readiness import expected_assets, inspect
from run_pilot import ROOT


def prepare(source, artifact):
    artifact = Path(artifact)
    if (ROOT / 'results/public-preview').resolve() not in artifact.resolve().parents:
        raise ValueError('Use a fresh artifact directory under results/public-preview')
    build(source, artifact)
    return inspect(source, artifact)


def handler(artifact, allowed):
    artifact = Path(artifact).resolve()
    class PublicPreview(SimpleHTTPRequestHandler):
        def allowed(self):
            try:
                host = urlsplit('http://' + self.headers.get('Host', ''))
                if host.hostname not in {'127.0.0.1', 'localhost'} or host.port != self.server.server_port or host.username or host.password:
                    self.send_error(403); return False
            except ValueError:
                self.send_error(403); return False
            relative = unquote(urlsplit(self.path).path).lstrip('/') or 'index.html'
            if relative not in allowed or '\\' in relative or '..' in Path(relative).parts:
                self.send_error(404); return False
            target = artifact / relative
            if target.is_symlink() or not target.is_file() or artifact not in target.resolve().parents:
                self.send_error(404); return False
            return True
        def do_GET(self):
            if self.allowed():
                super().do_GET()
        def do_HEAD(self):
            if self.allowed():
                super().do_HEAD()
        def end_headers(self):
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            super().end_headers()
        def log_message(self, *_):
            pass
    return partial(PublicPreview, directory=str(artifact))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'dashboard')
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--serve-existing', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Use an unprivileged loopback port')
    try:
        if args.serve_existing:
            report = inspect(args.source, args.artifact)
        else:
            report = prepare(args.source, args.artifact)
        print('Exact Pages preview validated:', report['artifact_files'], 'allowlisted files; no private APIs or deployment.', flush=True)
        if not args.build_only:
            server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(args.artifact, expected_assets(args.source)))
            print(f'Public judge preview: http://127.0.0.1:{args.port}/', flush=True)
            server.serve_forever(poll_interval=.5)
    except Exception as exc:
        parser.exit(1, f'Public preview stopped ({type(exc).__name__}); no private diagnostics printed.\n')
