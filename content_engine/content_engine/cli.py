"""Command-line interface: python -m content_engine <daily|weekly|social>."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .generators import (
    generate_daily_report,
    generate_social_post,
    generate_weekly_review,
)
from .llm import DEFAULT_MODEL, polish
from .sources import DEFAULT_TRADES_FILE, load_portfolio_state

GENERATORS = {
    "daily": generate_daily_report,
    "weekly": generate_weekly_review,
    "social": generate_social_post,
}

OUTPUT_NAMES = {
    "daily": "daily_report_{date}.md",
    "weekly": "weekly_review_{date}.md",
    "social": "social_post_{date}.txt",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="content_engine",
        description="Generate publishable content from Maxtrader trading data.",
    )
    parser.add_argument("kind", choices=sorted(GENERATORS), help="content type")
    parser.add_argument(
        "--trades",
        type=Path,
        default=DEFAULT_TRADES_FILE,
        help=f"path to trades.json (default: {DEFAULT_TRADES_FILE})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output directory; omit to print to stdout",
    )
    parser.add_argument(
        "--polish",
        action="store_true",
        help="rewrite the draft with the Claude API (needs anthropic + API key)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Claude model for --polish (default: {DEFAULT_MODEL})",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    state = load_portfolio_state(args.trades)
    content = GENERATORS[args.kind](state)
    if args.polish:
        content = polish(content, model=args.model)

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        name = OUTPUT_NAMES[args.kind].format(date=datetime.now().strftime("%Y%m%d"))
        path = args.out / name
        path.write_text(content)
        print(f"Wrote {path}")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
