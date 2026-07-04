"""GET /api/brief[?type=daily_brief|social_thread|newsletter|video_script]

Generates today's content on demand and returns it as JSON. Uses the
LLM keys configured in the Vercel project (falls back to templates), so
the public site always has fresh content. Cached at the edge for 15
minutes.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from _bootstrap import json_response  # noqa: F401 (sets up paths first)

from content_pipeline.config import load_pipeline_config
from content_pipeline.generator import CONTENT_TYPES, generate
from content_pipeline.monetizer import monetize
from content_pipeline.snapshot import build_snapshot


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        content_type = (query.get("type") or ["daily_brief"])[0]
        if content_type not in CONTENT_TYPES:
            json_response(self, 400, {"error": f"unknown type '{content_type}'"})
            return

        try:
            cfg = load_pipeline_config()
            snap = build_snapshot()
            content = monetize(
                generate(content_type, cfg, snap), cfg.monetization
            )
            json_response(
                self,
                200,
                {
                    "brand": cfg.brand.name,
                    "tagline": cfg.brand.tagline,
                    "type": content.content_type,
                    "title": content.title,
                    "markdown": content.body,
                    "provider": content.provider,
                    "as_of": snap.as_of,
                    "demo_data": snap.demo_mode,
                    "signup_url": cfg.monetization.newsletter_signup_url,
                },
                cache_seconds=900,
            )
        except Exception as e:
            json_response(self, 500, {"error": str(e)})
