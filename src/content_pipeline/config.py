"""Configuration for the content pipeline.

All settings live in ``content_pipeline.yaml`` at the repo root, with
secrets (API keys/tokens) read from the environment / ``.env`` so the
YAML file is safe to commit.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "content_pipeline.yaml"


@dataclass
class AffiliateProduct:
    """A product/service we link to for affiliate revenue."""

    name: str
    url: str
    blurb: str
    keywords: List[str] = field(default_factory=list)


@dataclass
class MonetizationConfig:
    newsletter_cta: str = ""
    newsletter_signup_url: str = ""
    premium_cta: str = ""
    premium_url: str = ""
    sponsor_slot: str = ""  # empty = no sponsor booked
    affiliates: List[AffiliateProduct] = field(default_factory=list)
    utm_source: str = "maxtrader"
    disclaimer: str = (
        "This content is generated from an automated trading research system "
        "and is for informational and educational purposes only. It is not "
        "financial advice. Past performance does not guarantee future results. "
        "Do your own research before making investment decisions."
    )


@dataclass
class BrandConfig:
    name: str = "Maxtrader Signals"
    tagline: str = "AI-driven market regime & rotation intelligence, daily."
    voice: str = (
        "Confident, data-driven, concise. Explains quant concepts in plain "
        "English. Never hypes, never gives direct buy/sell advice."
    )
    site_url: str = ""
    author: str = "Maxtrader Bot"


@dataclass
class LLMConfig:
    # Provider preference order; each is skipped if its key is missing.
    anthropic_model: str = "claude-sonnet-5"
    openai_model: str = "gpt-4o-mini"
    max_tokens: int = 2000
    temperature: float = 0.7
    request_timeout: int = 60

    @property
    def anthropic_api_key(self) -> Optional[str]:
        return os.getenv("ANTHROPIC_API_KEY") or None

    @property
    def openai_api_key(self) -> Optional[str]:
        key = os.getenv("OPENAI_API_KEY", "")
        # ignore the placeholder from .env.example
        return key if key and not key.startswith("your_") else None


@dataclass
class ChannelConfig:
    """Which content types go to which channels."""

    daily_brief: List[str] = field(
        default_factory=lambda: ["blog", "telegram", "discord"]
    )
    social_thread: List[str] = field(default_factory=lambda: ["twitter", "telegram"])
    newsletter: List[str] = field(default_factory=lambda: ["buttondown", "blog"])


@dataclass
class PipelineConfig:
    brand: BrandConfig = field(default_factory=BrandConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    monetization: MonetizationConfig = field(default_factory=MonetizationConfig)
    channels: ChannelConfig = field(default_factory=ChannelConfig)
    output_dir: Path = PROJECT_ROOT / "content" / "generated"
    blog_dir: Path = PROJECT_ROOT / "content" / "posts"
    ledger_path: Path = PROJECT_ROOT / "data" / "content_ledger.json"
    # Weekday (0=Mon .. 6=Sun) on which the weekly newsletter goes out.
    newsletter_weekday: int = 6


def load_pipeline_config(path: Optional[Path] = None) -> PipelineConfig:
    """Load config from YAML, falling back to sane defaults for any
    missing section so a bare repo still runs."""
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    cfg = PipelineConfig()
    if not path.exists():
        return cfg

    raw = yaml.safe_load(path.read_text()) or {}

    brand = raw.get("brand", {})
    for k, v in brand.items():
        if hasattr(cfg.brand, k):
            setattr(cfg.brand, k, v)

    llm = raw.get("llm", {})
    for k, v in llm.items():
        if hasattr(cfg.llm, k) and not isinstance(getattr(LLMConfig, k, None), property):
            setattr(cfg.llm, k, v)

    mon = raw.get("monetization", {})
    for k, v in mon.items():
        if k == "affiliates":
            cfg.monetization.affiliates = [
                AffiliateProduct(
                    name=a.get("name", ""),
                    url=a.get("url", ""),
                    blurb=a.get("blurb", ""),
                    keywords=a.get("keywords", []),
                )
                for a in (v or [])
            ]
        elif hasattr(cfg.monetization, k):
            setattr(cfg.monetization, k, v)

    ch = raw.get("channels", {})
    for k, v in ch.items():
        if hasattr(cfg.channels, k):
            setattr(cfg.channels, k, list(v))

    if "newsletter_weekday" in raw:
        cfg.newsletter_weekday = int(raw["newsletter_weekday"])
    if "output_dir" in raw:
        cfg.output_dir = PROJECT_ROOT / raw["output_dir"]
    if "blog_dir" in raw:
        cfg.blog_dir = PROJECT_ROOT / raw["blog_dir"]

    return cfg
