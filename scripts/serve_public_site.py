"""Serve a freshly audited combined Pages artifact on loopback only."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from build_public_site import ROOT, build
from publication_readiness import expected_assets
from serve_public_preview import handler


def site_handler(artifact, allowed):
    base = handler(artifact, allowed).func

    class OverviewPreview(base):
        def allowed(self):
            if urlsplit(self.path).path == '/overview/':
                self.path = '/overview/index.html'
            return super().allowed()

    return partial(OverviewPreview, directory=str(Path(artifact).resolve()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Use an unprivileged loopback port')
    if (ROOT/'results/public-preview').resolve() not in args.artifact.resolve().parents:
        parser.error('Use a fresh build directory under results/public-preview')
    build(args.artifact)
    allowed = expected_assets(ROOT/'dashboard') | {'overview/index.html', 'overview/style.css', 'overview/paper.pdf'}
    server = ThreadingHTTPServer(('127.0.0.1', args.port), site_handler(args.artifact, allowed))
    print(f'Judge overview: http://127.0.0.1:{args.port}/overview/', flush=True)
    server.serve_forever(poll_interval=.5)
