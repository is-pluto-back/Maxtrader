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
    url = add_utm("https://x.com/?ref=abc", "maxtrader", "content", "daily")
    assert "ref=abc" in url
    assert "utm_source=maxtrader" in url
    assert "utm_campaign=daily" in url


def test_monetize_appends_disclaimer_and_cta(snapshot):
    mon = MonetizationConfig(
        newsletter_cta="Subscribe!",
        newsletter_signup_url="https://news.example.com",
    )
    content = GeneratedContent("daily_brief", "T", "The market did things.", "template")
    out = monetize(content, mon)
    assert "not financial advice" in out.body.lower()
    assert "utm_source=maxtrader" in out.body
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
