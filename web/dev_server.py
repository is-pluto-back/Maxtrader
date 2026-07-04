#!/usr/bin/env python3
"""Local dev server mirroring Vercel's routing for this app.

    python web/dev_server.py [port]

Serves:
    /               -> index.html (static, like Vercel)
    /api/brief      -> api/brief.py handler
    /api/cron       -> api/cron.py handler

Uses the same vendored package and the same BaseHTTPRequestHandler
classes Vercel invokes, so behavior locally == behavior deployed.
"""

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(WEB_ROOT / "api"))

import brief  # noqa: E402
import cron  # noqa: E402


class Dispatcher(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/brief"):
            brief.handler.do_GET(self)
        elif self.path.startswith("/api/cron"):
            cron.handler.do_GET(self)
        elif self.path in ("/", "/index.html"):
            body = (WEB_ROOT / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")

    def log_message(self, fmt, *args):
        print(f"[dev] {self.address_string()} {fmt % args}")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    print(f"Maxtrader web dev server -> http://localhost:{port}")
    HTTPServer(("", port), Dispatcher).serve_forever()
