"""Shared bootstrap for the Vercel serverless functions.

Must be imported before ``content_pipeline`` — it points every writable
path at /tmp (the only writable location on Vercel) and puts the
vendored package on sys.path.
"""

import os
import sys
from pathlib import Path

# Writable location must be set before content_pipeline.config is imported.
os.environ.setdefault("CONTENT_DATA_DIR", "/tmp/maxtrader")

WEB_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB_ROOT / "_vendor"))


def json_response(handler, status: int, payload: dict, cache_seconds: int = 0):
    import json

    body = json.dumps(payload, default=str).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    if cache_seconds:
        handler.send_header(
            "Cache-Control", f"s-maxage={cache_seconds}, stale-while-revalidate=60"
        )
    handler.end_headers()
    handler.wfile.write(body)
