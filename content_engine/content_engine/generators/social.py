"""Short-form social post generator (X/Twitter-length)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ..models import PortfolioState


def generate_social_post(
    state: PortfolioState, as_of: Optional[datetime] = None
) -> str:
    as_of = as_of or datetime.now()
    day_start = as_of.replace(hour=0, minute=0, second=0, microsecond=0)
    todays_trades = state.trades_between(start=day_start, end=as_of)

    change = state.equity_change()
    if change is not None and state.equity:
        prev = state.equity - change
        pct = (change / prev * 100.0) if prev else 0.0
        move = f"{'📈' if change >= 0 else '📉'} {pct:+.2f}% on the session."
    else:
        move = "📊 Portfolio update."

    if todays_trades:
        tickers = sorted({t.ticker for t in todays_trades})
        activity = f"{len(todays_trades)} trades across {', '.join(tickers[:5])}."
    elif state.positions:
        top = max(state.positions, key=lambda p: abs(p.pnl))
        activity = f"No trades today — largest mover in book: {top.ticker} ({top.pnl:+,.0f})."
    else:
        activity = "Flat in cash, waiting for a setup."

    n = len(state.positions)
    book = f"{n} open position{'s' if n != 1 else ''}."

    return f"{move} {activity} {book} #algotrading #quant"
