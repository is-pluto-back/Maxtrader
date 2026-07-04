"""GET /api/cron — the autonomous heartbeat, invoked by Vercel Cron.

Runs the full pipeline: snapshot -> generate -> monetize -> publish to
every channel whose credentials are set in the Vercel project's
environment variables (Telegram, Discord, X, Buttondown).

Security: when a ``CRON_SECRET`` environment variable is set, Vercel
Cron sends it as ``Authorization: Bearer <secret>`` automatically and
this endpoint rejects any request without it. Always set CRON_SECRET in
production.

Note: the blog channel writes to /tmp on Vercel (ephemeral). Durable
blog posts come from running the pipeline via cron/GitHub Actions in
the repo instead; on Vercel the API-based channels are the distribution.
"""

import os
from http.server import BaseHTTPRequestHandler

from _bootstrap import json_response  # noqa: F401 (sets up paths first)

from content_pipeline import ContentPipeline
from content_pipeline.config import load_pipeline_config


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        secret = os.getenv("CRON_SECRET")
        if secret:
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {secret}":
                json_response(self, 401, {"error": "unauthorized"})
                return

        try:
            cfg = load_pipeline_config()
            # Video rendering needs ffmpeg + long CPU time — not a fit for
            # a serverless function; images still render fine.
            cfg.media.enable_video = os.getenv("VERCEL_ENABLE_VIDEO") == "1"

            pipeline = ContentPipeline(cfg)
            report = pipeline.run()
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "summary": report.summary(),
                    "generated": [c.content_type for c in report.generated],
                    "published": {
                        ct: [
                            {"channel": r.channel, "ok": r.ok, "detail": r.detail}
                            for r in results
                        ]
                        for ct, results in report.results.items()
                    },
                },
            )
        except Exception as e:
            json_response(self, 500, {"ok": False, "error": str(e)})
