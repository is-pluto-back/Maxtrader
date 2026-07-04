"""Market + strategy snapshot: the raw material for every piece of content.

Pulls from what the trading system already produces, degrading gracefully
at each step so the pipeline always has *something* to write about:

1. ``trades.json``            -> live equity curve, positions, P&L
2. strategy weights output    -> latest rotation targets + regime
3. index data                 -> free daily OHLC from Stooq (no API key),
                                 or yfinance if installed
4. otherwise                  -> clearly-flagged sample data (demo mode)
"""

import csv
import io
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

log = logging.getLogger("content-pipeline.snapshot")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRADES_FILE = PROJECT_ROOT / "trades.json"
WEIGHTS_DIR = PROJECT_ROOT / "src" / "strategies" / "output" / "weights" / "adaptive_rotation"

# Stooq is a free, keyless source for daily index data.
STOOQ_SYMBOLS = {
    "S&P 500": "^spx",
    "Nasdaq Comp": "^ndq",
    "Dow Jones": "^dji",
}


@dataclass
class IndexMove:
    name: str
    close: float
    change_pct: float  # 1-day % change


@dataclass
class Position:
    ticker: str
    shares: float
    avg_cost: float
    current_price: float
    pnl: float


@dataclass
class MarketSnapshot:
    as_of: str
    indexes: List[IndexMove] = field(default_factory=list)
    regime: Optional[str] = None
    equity: Optional[float] = None
    cash: Optional[float] = None
    equity_change_pct: Optional[float] = None  # since previous snapshot
    positions: List[Position] = field(default_factory=list)
    target_weights: Dict[str, float] = field(default_factory=dict)
    recent_trades: List[dict] = field(default_factory=list)
    demo_mode: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def summary_lines(self) -> List[str]:
        """Compact human-readable facts, used as LLM context and by the
        template fallback generator."""
        lines = [f"Date: {self.as_of}"]
        if self.demo_mode:
            lines.append("NOTE: sample/demo data (no live feeds connected)")
        for ix in self.indexes:
            lines.append(f"{ix.name}: {ix.close:,.2f} ({ix.change_pct:+.2f}%)")
        if self.regime:
            lines.append(f"Strategy regime: {self.regime}")
        if self.equity is not None:
            chg = (
                f" ({self.equity_change_pct:+.2f}% vs prior)"
                if self.equity_change_pct is not None
                else ""
            )
            lines.append(f"Portfolio equity: ${self.equity:,.2f}{chg}")
        if self.positions:
            winners = sorted(self.positions, key=lambda p: p.pnl, reverse=True)
            top = winners[0]
            bottom = winners[-1]
            lines.append(
                f"Top position P&L: {top.ticker} ${top.pnl:+,.2f}; "
                f"weakest: {bottom.ticker} ${bottom.pnl:+,.2f}"
            )
            lines.append(
                "Holdings: " + ", ".join(p.ticker for p in self.positions[:12])
            )
        if self.target_weights:
            top5 = sorted(
                self.target_weights.items(), key=lambda kv: kv[1], reverse=True
            )[:5]
            lines.append(
                "Top target weights: "
                + ", ".join(f"{sym} {w:.1%}" for sym, w in top5)
            )
        if self.recent_trades:
            lines.append(
                "Recent trades: "
                + "; ".join(
                    f"{t.get('action', '?').upper()} {t.get('qty', '?')} {t.get('ticker', '?')}"
                    for t in self.recent_trades[-5:]
                )
            )
        return lines


def _fetch_stooq_index(symbol: str, timeout: int = 15) -> Optional[IndexMove]:
    """Fetch last two daily closes from Stooq's free CSV endpoint."""
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(r.text)))
        if len(rows) < 2:
            return None
        prev, last = float(rows[-2]["Close"]), float(rows[-1]["Close"])
        return IndexMove(name=symbol, close=last, change_pct=(last / prev - 1) * 100)
    except Exception as e:  # network-optional by design
        log.debug(f"Stooq fetch failed for {symbol}: {e}")
        return None


def _load_indexes() -> List[IndexMove]:
    moves = []
    for name, sym in STOOQ_SYMBOLS.items():
        m = _fetch_stooq_index(sym)
        if m:
            m.name = name
            moves.append(m)
    return moves


def _load_trades_state() -> dict:
    if TRADES_FILE.exists():
        try:
            return json.loads(TRADES_FILE.read_text())
        except Exception as e:
            log.warning(f"Could not parse trades.json: {e}")
    return {}


def _load_latest_weights() -> Dict[str, float]:
    """Read the most recent weights CSV emitted by the rotation strategy."""
    if not WEIGHTS_DIR.exists():
        return {}
    candidates = sorted(WEIGHTS_DIR.glob("*.csv"))
    if not candidates:
        return {}
    weights: Dict[str, float] = {}
    try:
        with open(candidates[-1]) as f:
            for row in csv.DictReader(f):
                sym = row.get("symbol") or row.get("ticker") or row.get("asset")
                w = row.get("weight") or row.get("target_weight")
                if sym and w:
                    try:
                        weights[sym] = float(w)
                    except ValueError:
                        continue
    except Exception as e:
        log.warning(f"Could not read weights file {candidates[-1]}: {e}")
    return weights


def _demo_snapshot(as_of: str) -> MarketSnapshot:
    """Deterministic sample so the whole pipeline can be exercised with
    no data files and no network. Always flagged as demo."""
    return MarketSnapshot(
        as_of=as_of,
        demo_mode=True,
        indexes=[
            IndexMove("S&P 500", 6104.25, 0.42),
            IndexMove("Nasdaq Comp", 19987.10, 0.77),
            IndexMove("Dow Jones", 44210.50, -0.11),
        ],
        regime="NEUTRAL",
        equity=104_532.18,
        cash=21_450.00,
        equity_change_pct=0.35,
        positions=[
            Position("NVDA", 40, 118.20, 131.55, 534.00),
            Position("MSFT", 25, 415.30, 427.80, 312.50),
            Position("XLE", 80, 88.10, 86.95, -92.00),
            Position("GLD", 30, 215.40, 221.10, 171.00),
        ],
        target_weights={"NVDA": 0.12, "MSFT": 0.10, "GLD": 0.08, "XLE": 0.07, "TLT": 0.06},
        recent_trades=[
            {"action": "buy", "ticker": "GLD", "qty": 10},
            {"action": "sell", "ticker": "XLE", "qty": 15},
        ],
    )


def build_snapshot(offline: bool = False) -> MarketSnapshot:
    """Assemble today's snapshot from all available sources."""
    as_of = date.today().isoformat()

    indexes = [] if offline else _load_indexes()
    state = _load_trades_state()
    weights = _load_latest_weights()

    has_live_data = bool(indexes or state or weights)
    if not has_live_data:
        log.info("No live data sources available — using demo snapshot")
        return _demo_snapshot(as_of)

    snap = MarketSnapshot(as_of=as_of, indexes=indexes, target_weights=weights)

    curve = state.get("equity_curve") or []
    if curve:
        snap.equity = curve[-1].get("equity")
        snap.cash = curve[-1].get("cash")
        if len(curve) >= 2 and curve[-2].get("equity"):
            snap.equity_change_pct = (
                curve[-1]["equity"] / curve[-2]["equity"] - 1
            ) * 100

    snap.positions = [
        Position(
            ticker=p.get("ticker", "?"),
            shares=float(p.get("shares", 0)),
            avg_cost=float(p.get("avg_cost", 0)),
            current_price=float(p.get("current_price", 0)),
            pnl=float(p.get("pnl", 0)),
        )
        for p in state.get("positions", [])
    ]
    snap.recent_trades = state.get("trade_history", [])[-10:]
    snap.regime = state.get("regime")

    return snap
