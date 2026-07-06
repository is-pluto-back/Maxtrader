"""Load trading data produced by the Maxtrader agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from .models import PortfolioState

# Default location: trades.json at the Maxtrader repo root (two levels up
# from this package when content_engine/ lives inside the repo).
DEFAULT_TRADES_FILE = Path(__file__).resolve().parents[2] / "trades.json"


def load_portfolio_state(path: Union[str, Path, None] = None) -> PortfolioState:
    """Read trades.json and return a typed PortfolioState.

    Missing or malformed files return an empty state rather than raising, so
    content generation degrades gracefully to "no activity" copy.
    """
    p = Path(path) if path else DEFAULT_TRADES_FILE
    try:
        data = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return PortfolioState()
    if not isinstance(data, dict):
        return PortfolioState()
    return PortfolioState.from_dict(data)
