"""Tests for the content pipeline — all offline, no keys required."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from content_pipeline.config import (
    AffiliateProduct,
    MonetizationConfig,
    PipelineConfig,
    load_pipeline_config,
)
from content_pipeline.generator import GeneratedContent, generate
from content_pipeline.ledger import ContentLedger
from content_pipeline.monetizer import add_utm, monetize
from content_pipeline.publishers import PUBLISHERS
from content_pipeline.publishers.blog import BlogPublisher, slugify
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


def test_yaml_config_loads():
    cfg = load_pipeline_config(PROJECT_ROOT / "content_pipeline.yaml")
    assert cfg.brand.name
    assert cfg.monetization.disclaimer
    assert "blog" in cfg.channels.daily_brief


def test_template_generation_all_types(cfg, snapshot):
    for ct in ("daily_brief", "social_thread", "newsletter"):
        out = generate(ct, cfg, snapshot, force_provider="template")
        assert out.provider == "template"
        assert out.body.strip()
        assert "2026-07-04" in out.title


def test_social_thread_tweets_fit(cfg, snapshot):
    out = generate("social_thread", cfg, snapshot, force_provider="template")
    for tweet in out.body.split("\n---\n"):
        assert len(tweet) <= 280


def test_add_utm_preserves_existing_params():
    url = add_utm("https://x.com/?ref=abc", "mybrand", "content", "daily")
    assert "ref=abc" in url
    assert "utm_source=mybrand" in url
    assert "utm_campaign=daily" in url


def test_monetize_appends_disclaimer_and_cta(snapshot):
    mon = MonetizationConfig(
        newsletter_cta="Subscribe!",
        newsletter_signup_url="https://news.example.com",
    )
    content = GeneratedContent("daily_brief", "T", "The market did things.", "template")
    out = monetize(content, mon)
    assert "financial advice" in out.body.lower()
    assert "utm_source=content-engine" in out.body
    assert out.body.startswith("The market did things.")


def test_monetize_affiliate_keyword_matching():
    mon = MonetizationConfig(
        affiliates=[
            AffiliateProduct("ChartCo", "https://chartco.example", "charts", ["momentum"]),
            AffiliateProduct("NopeCo", "https://nope.example", "nope", ["quilting"]),
        ]
    )
    content = GeneratedContent("daily_brief", "T", "Momentum is strong today.", "template")
    out = monetize(content, mon)
    assert "ChartCo" in out.body
    assert "NopeCo" not in out.body


def test_monetize_social_is_light_touch():
    mon = MonetizationConfig(
        newsletter_signup_url="https://news.example.com",
        sponsor_slot="BIG SPONSOR",
    )
    content = GeneratedContent("social_thread", "T", "tweet one\n---\ntweet two", "template")
    out = monetize(content, mon)
    assert "BIG SPONSOR" not in out.body  # no sponsor blocks in threads
    assert "news.example.com" in out.body


def test_blog_publisher_writes_front_matter(cfg, snapshot):
    content = GeneratedContent("daily_brief", "My Brief (2026-07-04)", "Body here.", "template")
    result = BlogPublisher(cfg).publish(content)
    assert result.ok
    text = Path(result.detail).read_text()
    assert text.startswith("---")
    assert 'title: "My Brief (2026-07-04)"' in text
    assert "Body here." in text


def test_slugify():
    assert slugify("Maxtrader — Daily Brief (2026-07-04)!") == "maxtrader-daily-brief-2026-07-04"


def test_unconfigured_publishers_skip(cfg, monkeypatch):
    for var in (
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "DISCORD_WEBHOOK_URL",
        "TWITTER_OAUTH2_ACCESS_TOKEN",
        "BUTTONDOWN_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    for name, cls in PUBLISHERS.items():
        configured = cls(cfg).is_configured()
        assert configured == (name == "blog"), f"{name} should be gated by credentials"


def test_ledger_records_and_stats(cfg):
    ledger = ContentLedger(cfg.ledger_path)
    ledger.record_publish("daily_brief", "T", "template", "blog", "ok")
    ledger.record_publish("daily_brief", "T", "template", "blog", "dry_run", dry_run=True)
    ledger.record_revenue(100.0, "newsletter")
    ledger.record_revenue(25.5, "affiliate")

    stats = ledger.stats()
    assert stats["total_published"] == 1  # dry runs excluded
    assert stats["total_runs"] == 2
    assert stats["total_revenue"] == 125.5
    assert stats["revenue_by_source"] == {"newsletter": 100.0, "affiliate": 25.5}

    # persistence across instances
    assert ContentLedger(cfg.ledger_path).total_revenue() == 125.5


def test_pipeline_dry_run_end_to_end(cfg):
    from content_pipeline.pipeline import ContentPipeline

    pipeline = ContentPipeline(cfg)
    report = pipeline.run(
        content_types=["daily_brief", "social_thread"],
        dry_run=True,
        offline=True,
        force_provider="template",
    )
    assert len(report.generated) == 2
    assert len(report.preview_files) == 2
    for f in report.preview_files:
        assert f.exists() and f.read_text().strip()
    assert "daily_brief" in report.summary()


def test_custom_facts_source(tmp_path):
    from content_pipeline.snapshot import build_snapshot

    facts = tmp_path / "today.yaml"
    facts.write_text(
        "headline: Big launch day\nfacts:\n  - Model X shipped\n  - Benchmarks up 12%\n"
    )
    cfg = PipelineConfig()
    cfg.source.type = "custom"
    cfg.source.facts_file = str(facts)
    snap = build_snapshot(cfg, offline=True)
    assert snap.headline == "Big launch day"
    assert snap.facts == ["Model X shipped", "Benchmarks up 12%"]
    assert not snap.demo_mode

    out = generate("daily_brief", cfg, snap, force_provider="template")
    assert "Big launch day" in out.body
    assert "Model X shipped" in out.body


def test_trends_offline_evergreen():
    from content_pipeline.trends import research_ideas

    cfg = PipelineConfig()
    cfg.research.keywords = ["quant trading"]
    ideas = research_ideas(cfg, offline=True)
    assert "quant trading" in ideas
    assert "evergreen" in ideas.lower()


def test_trends_heuristic_ranking():
    from content_pipeline.trends import _heuristic_rank

    signals = ["Celebrity gossip news", "Fed cuts rates again", "Sports final"]
    top = _heuristic_rank(signals, ["fed", "rates"], top_n=2)
    assert top[0] == "Fed cuts rates again"


def test_production_pack_template(cfg, snapshot):
    cfg.persona.name = "Adaline"
    cfg.persona.appearance = "mid-20s, warm smile"
    out = generate("production_pack", cfg, snapshot, force_provider="template")
    assert "HOOK (0-3s)" in out.body
    assert "Adaline" in out.body                 # persona consistency block
    assert "Midjourney" in out.body
    assert "Runway" in out.body
    assert "Title options" in out.body


def test_persona_config_loads(tmp_path):
    yaml_file = tmp_path / "cfg.yaml"
    yaml_file.write_text(
        "persona:\n  name: Adaline\n  wardrobe: neutral knitwear\n"
    )
    cfg = load_pipeline_config(yaml_file)
    assert cfg.persona.enabled
    assert "neutral knitwear" in cfg.persona.consistency_block()


def test_ledger_metrics(cfg):
    ledger = ContentLedger(cfg.ledger_path)
    ledger.record_metrics("youtube", views=1000, retention_pct=50, ctr_pct=4)
    ledger.record_metrics("tiktok", views=3000, retention_pct=40)
    stats = ledger.stats()
    assert stats["total_views"] == 4000
    assert stats["avg_retention_pct"] == 45.0
    assert stats["metrics_logged"] == 2


def test_thumbnail_renders(cfg, snapshot, tmp_path):
    pytest.importorskip("PIL")
    from content_pipeline.media.image_gen import _thumbnail_card, hook_text
    from PIL import Image

    assert hook_text(snapshot)  # non-empty for demo data
    path = _thumbnail_card(snapshot, cfg, tmp_path / "thumb.png")
    img = Image.open(path)
    assert img.size == (1280, 720)


def test_ledger_review_report(cfg):
    ledger = ContentLedger(cfg.ledger_path)
    ledger.record_publish("daily_brief", "T", "template", "telegram", "ok")
    ledger.record_revenue(50, "newsletter")
    ledger.record_metrics("youtube", views=9000, retention_pct=52, ctr_pct=2.5, note="short #2")
    report = ledger.review(days=7)
    assert "Posts published: **1**" in report
    assert "$50.00" in report
    assert "9,000" in report
    assert "Next iteration" in report
