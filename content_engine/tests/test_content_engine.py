import json
from datetime import datetime, timedelta
from pathlib import Path

from content_engine.generators import (
    generate_daily_report,
    generate_social_post,
    generate_weekly_review,
)
from content_engine.models import PortfolioState
from content_engine.sources import load_portfolio_state

NOW = datetime(2026, 7, 6, 15, 30)


def sample_state() -> PortfolioState:
    return PortfolioState.from_dict(
        {
            "agent_running": True,
            "last_updated": NOW.isoformat(),
            "equity_curve": [
                {"timestamp": (NOW - timedelta(days=6)).isoformat(), "equity": 100000, "cash": 40000},
                {"timestamp": (NOW - timedelta(days=1)).isoformat(), "equity": 101500, "cash": 35000},
                {"timestamp": NOW.isoformat(), "equity": 102350.5, "cash": 30500.25},
            ],
            "positions": [
                {"ticker": "NVDA", "shares": 20, "avg_cost": 900.0, "current_price": 950.5, "pnl": 1010.0},
                {"ticker": "XLE", "shares": 100, "avg_cost": 92.0, "current_price": 90.0, "pnl": -200.0},
            ],
            "trade_history": [
                {"timestamp": (NOW - timedelta(days=3)).isoformat(), "action": "buy", "ticker": "NVDA", "qty": 20, "price": 900.0},
                {"timestamp": (NOW - timedelta(hours=2)).isoformat(), "action": "sell", "ticker": "AAPL", "qty": 10, "price": 210.0},
            ],
        }
    )


def test_state_properties():
    s = sample_state()
    assert s.equity == 102350.5
    assert s.cash == 30500.25
    assert s.equity_change() == 102350.5 - 101500
    assert len(s.trades_between(start=NOW - timedelta(days=1))) == 1


def test_daily_report_contains_data():
    report = generate_daily_report(sample_state(), as_of=NOW)
    assert "Daily Trading Report — 2026-07-06" in report
    assert "$102,350.50" in report
    assert "NVDA" in report and "XLE" in report
    assert "AAPL" in report  # today's trade
    assert "Not investment advice" in report


def test_weekly_review_aggregates():
    review = generate_weekly_review(sample_state(), as_of=NOW)
    assert "Weekly Review" in review
    assert "2 (1 buys / 1 sells)" in review
    assert "NVDA" in review


def test_social_post_is_short():
    post = generate_social_post(sample_state(), as_of=NOW)
    assert len(post) < 280
    assert "#algotrading" in post


def test_missing_trades_file_degrades_gracefully(tmp_path: Path):
    state = load_portfolio_state(tmp_path / "nope.json")
    assert state.equity == 0.0
    report = generate_daily_report(state, as_of=NOW)
    assert "No open positions" in report


def test_corrupt_trades_file(tmp_path: Path):
    bad = tmp_path / "trades.json"
    bad.write_text("{not json")
    state = load_portfolio_state(bad)
    assert state.positions == []


def test_loads_real_schema(tmp_path: Path):
    f = tmp_path / "trades.json"
    f.write_text(json.dumps({"agent_running": False, "last_updated": None,
                             "equity_curve": [], "positions": [], "trade_history": []}))
    state = load_portfolio_state(f)
    assert state.agent_running is False
