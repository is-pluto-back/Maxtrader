#!/usr/bin/env python3
"""
Maxtrader Content Engine — CLI
==============================
Autonomous content-revenue pipeline: turns the trading system's daily
output (regime, rotations, P&L) into monetized content and publishes it.

Usage:
    python run_content_pipeline.py                    # today's due content, publish everywhere configured
    python run_content_pipeline.py --dry-run          # generate + preview, publish nowhere
    python run_content_pipeline.py --types daily_brief social_thread
    python run_content_pipeline.py --provider template --offline   # zero keys, zero network
    python run_content_pipeline.py stats              # what's been published + revenue
    python run_content_pipeline.py revenue 125.50 --source newsletter --note "July payout"
    python run_content_pipeline.py schedule           # print the cron lines to install

Run it daily after market close via cron (see `schedule`) and it needs
no further attention: content is generated, monetized, published, and
logged on its own.
"""

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from content_pipeline import ContentPipeline, load_pipeline_config  # noqa: E402

CRON_TEMPLATE = """\
# Maxtrader Content Engine — install with `crontab -e`
# Daily brief + social thread, 45 min after US market close (Mon-Fri):
45 16 * * 1-5  cd {root} && python run_content_pipeline.py >> logs/content_pipeline.log 2>&1
# Weekly newsletter goes out automatically on the configured weekday
# (newsletter_weekday in content_pipeline.yaml) by the same daily run —
# on that day, add a Sunday run if the weekday falls on a weekend:
0 10 * * 0     cd {root} && python run_content_pipeline.py --types newsletter >> logs/content_pipeline.log 2>&1
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Maxtrader Content Engine")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "stats", "revenue", "schedule", "research", "metrics", "review"],
    )
    parser.add_argument("amount", nargs="?", type=float, help="revenue amount (for 'revenue')")
    parser.add_argument("--types", nargs="+", help="content types to generate")
    parser.add_argument("--dry-run", action="store_true", help="generate but do not publish")
    parser.add_argument("--offline", action="store_true", help="skip all network data fetches")
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai", "template"],
        help="force a specific generation provider",
    )
    parser.add_argument("--source", default="other", help="revenue source (newsletter/affiliate/sponsor)")
    parser.add_argument("--note", default="", help="note for revenue/metrics entries")
    parser.add_argument("--channel", default="", help="channel for metrics entries")
    parser.add_argument("--views", type=int, default=0, help="views for metrics")
    parser.add_argument("--retention", type=float, default=0.0, help="avg retention %% for metrics")
    parser.add_argument("--ctr", type=float, default=0.0, help="link CTR %% for metrics")
    args = parser.parse_args()

    cfg = load_pipeline_config()
    pipeline = ContentPipeline(cfg)

    if args.command == "schedule":
        print(CRON_TEMPLATE.format(root=PROJECT_ROOT))
        return 0

    if args.command == "stats":
        import json

        print(json.dumps(pipeline.ledger.stats(), indent=2))
        return 0

    if args.command == "research":
        from content_pipeline.trends import research_ideas

        ideas = research_ideas(cfg, offline=args.offline)
        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        from datetime import date

        path = cfg.output_dir / f"{date.today().isoformat()}-ideas.md"
        path.write_text(ideas)
        print(ideas)
        print(f"\nSaved to {path}")
        return 0

    if args.command == "review":
        print(pipeline.ledger.review(days=7))
        return 0

    if args.command == "metrics":
        entry = pipeline.ledger.record_metrics(
            args.channel or "unknown",
            views=args.views,
            retention_pct=args.retention,
            ctr_pct=args.ctr,
            note=args.note,
        )
        print(f"Logged metrics (id={entry})")
        import json as _json

        print(_json.dumps(pipeline.ledger.stats(), indent=2))
        return 0

    if args.command == "revenue":
        if args.amount is None:
            parser.error("revenue requires an amount, e.g. `revenue 125.50 --source newsletter`")
        entry = pipeline.ledger.record_revenue(args.amount, args.source, args.note)
        print(f"Recorded ${args.amount:.2f} from '{args.source}' (id={entry})")
        print(f"Total revenue to date: ${pipeline.ledger.total_revenue():,.2f}")
        return 0

    report = pipeline.run(
        content_types=args.types,
        dry_run=args.dry_run,
        offline=args.offline,
        force_provider=args.provider,
    )
    print("\n" + "=" * 60)
    print(report.summary())
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
