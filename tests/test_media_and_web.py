"""Tests for media generation and the Vercel web app — all offline."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "web"))

from content_pipeline.config import PipelineConfig
from content_pipeline.generator import generate
from content_pipeline.snapshot import _demo_snapshot


@pytest.fixture
def snapshot():
    return _demo_snapshot("2026-07-04")


@pytest.fixture
def cfg(tmp_path):
    cfg = PipelineConfig()
    cfg.output_dir = tmp_path / "generated"
    cfg.blog_dir = tmp_path / "posts"
    cfg.ledger_path = tmp_path / "ledger.json"
    return cfg


def test_video_script_template(cfg, snapshot):
    out = generate("video_script", cfg, snapshot, force_provider="template")
    assert "SCENE 1" in out.body
    assert "VISUAL:" in out.body
    assert "VO:" in out.body
    assert "ot financial advice" in out.body


def test_narration_extraction():
    from content_pipeline.media.tts import extract_narration

    script = "## SCENE 1\nVISUAL: chart\nVO: Hello market.\n## SCENE 2\nVO: Goodbye."
    assert extract_narration(script) == "Hello market. Goodbye."


def test_image_cards_render(cfg, snapshot, tmp_path):
    pytest.importorskip("PIL")
    from content_pipeline.media.image_gen import render_cards

    images, frames = render_cards(snapshot, cfg, tmp_path)
    assert len(images) == 2 and len(frames) == 3
    for p in images + frames:
        assert p.exists() and p.stat().st_size > 1000

    from PIL import Image

    assert Image.open(images[0]).size == tuple(cfg.media.image_size)
    assert Image.open(frames[0]).size == tuple(cfg.media.video_size)


def test_video_renders_when_ffmpeg_available(cfg, snapshot, tmp_path):
    pytest.importorskip("PIL")
    from content_pipeline.media.image_gen import render_cards
    from content_pipeline.media.video_gen import find_ffmpeg, render_video

    if not find_ffmpeg():
        pytest.skip("no ffmpeg available")

    _, frames = render_cards(snapshot, cfg, tmp_path)
    cfg.media.seconds_per_slide = 1  # keep the test fast
    video = render_video(frames, cfg, tmp_path)
    assert video is not None and video.exists()
    assert video.stat().st_size > 10_000


def test_pipeline_attaches_media(cfg):
    pytest.importorskip("PIL")
    from content_pipeline.pipeline import ContentPipeline

    cfg.media.enable_video = False  # keep the test fast
    report = ContentPipeline(cfg).run(
        content_types=["daily_brief", "social_thread", "video_script"],
        dry_run=True,
        offline=True,
        force_provider="template",
    )
    assert len(report.media_images) == 2
    brief = next(c for c in report.generated if c.content_type == "daily_brief")
    assert brief.images and brief.images[0].exists()


def test_vendored_copy_in_sync():
    """The Vercel app deploys web/_vendor — it must match src/. Run
    `python web/sync_vendor.py` after editing the pipeline."""
    import sync_vendor

    assert sync_vendor.check(), "run: python web/sync_vendor.py"


def test_web_brief_endpoint(monkeypatch, tmp_path):
    """Exercise the Vercel function exactly as its HTTP layer would."""
    import io

    monkeypatch.setenv("CONTENT_DATA_DIR", str(tmp_path))
    sys.path.insert(0, str(PROJECT_ROOT / "web" / "api"))
    import brief

    class FakeHandler:
        path = "/api/brief?type=daily_brief"
        wfile = io.BytesIO()

        def send_response(self, code):
            self.status = code

        def send_header(self, *a):
            pass

        def end_headers(self):
            pass

    fake = FakeHandler()
    brief.handler.do_GET(fake)
    import json

    payload = json.loads(fake.wfile.getvalue())
    assert fake.status == 200
    assert payload["type"] == "daily_brief"
    assert payload["markdown"].startswith("#")


def test_web_cron_requires_secret(monkeypatch, tmp_path):
    import io

    monkeypatch.setenv("CONTENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    sys.path.insert(0, str(PROJECT_ROOT / "web" / "api"))
    import cron

    class FakeHandler:
        path = "/api/cron"
        headers = {}
        wfile = io.BytesIO()

        def send_response(self, code):
            self.status = code

        def send_header(self, *a):
            pass

        def end_headers(self):
            pass

    fake = FakeHandler()
    cron.handler.do_GET(fake)
    assert fake.status == 401
