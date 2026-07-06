"""Content engine for Maxtrader — turns trading data into publishable content.

Generates daily reports, weekly reviews, and short-form social posts from the
trading agent's ``trades.json`` state file. Works standalone with the Python
standard library; installs ``anthropic`` for optional LLM-polished narrative.
"""

__version__ = "0.1.0"

from .models import EquityPoint, PortfolioState, Position, Trade
from .sources import load_portfolio_state

__all__ = [
    "EquityPoint",
    "PortfolioState",
    "Position",
    "Trade",
    "load_portfolio_state",
]
