"""
Maxtrader Content Engine
========================
Autonomous content-revenue pipeline built on top of the trading system.

Every day the trading agent already produces valuable, perishable
information: the detected market regime, portfolio rotations, position
P&L, and index moves. This package turns that exhaust into publishable,
monetizable content — automatically:

    snapshot  ->  generate  ->  monetize  ->  publish  ->  ledger

- ``snapshot``    gathers market + strategy state (works offline)
- ``generator``   writes content via Anthropic/OpenAI, or templates with no keys
- ``monetizer``   injects CTAs, affiliate links, sponsor slots, disclaimers
- ``publishers``  blog / Telegram / Discord / X / Buttondown newsletter
- ``ledger``      append-only record of everything published + revenue

Entry point: ``run_content_pipeline.py`` at the repo root.
"""

from .pipeline import ContentPipeline
from .config import load_pipeline_config

__all__ = ["ContentPipeline", "load_pipeline_config"]
