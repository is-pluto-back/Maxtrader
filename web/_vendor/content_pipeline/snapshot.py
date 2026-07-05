"""Daily snapshot: the factual raw material for every piece of content.

Two source types (``source.type`` in ``content_pipeline.yaml``):

- ``market``  — free daily index data from Stooq (no API key) plus, when
  configured, any trading system's state: a trades/positions JSON
  (``SOURCE_TRADES_FILE``) and a directory of target-weight CSVs
  (``SOURCE_WEIGHTS_DIR``). See docs/CONTENT_PIPELINE.md for the format.
- ``custom``  — a YAML/JSON facts file (``SOURCE_FACTS_FILE``) written by
  you or another job: ``{headline: str, facts: [str, ...]}`` — so any
  niche can drive the engine.

Every step degrades gracefully; with no sources at all the pipeline
runs on clearly-flagged sample data so it never blocks.
"""

import csv
import io
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

import requests
import yaml

log = logging.getLogger("content-pipeline.snapshot")

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
    # market source fields
    indexes: List[IndexMove] = field(default_factory=list)
    regime: Optional[str] = None
    equity: Optional[float] = None
    cash: Optional[float] = None
    equity_change_pct: Optional[float] = None  # since previous snapshot
    positions: List[Position] = field(default_factory=list)
    target_weights: Dict[str, float] = field(default_factory=dict)
    recent_trades: List[dict] = field(default_factory=list)
    # custom source fields
    headline: Optional[str] = None
    facts: List[str] = field(default_factory=list)
    demo_mode: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def summary_lines(self) -> List[str]:
        """Compact human-readable facts, used as LLM context and by the
        template fallback generator."""
        lines = [f"Date: {self.as_of}"]
        if self.demo_mode:
            lines.append("NOTE: sample/demo data (no live feeds connected)")
        if self.headline:
            lines.append(f"Headline: {self.headline}")
        lines.extend(self.facts)
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


def _load_trades_state(trades_file: Optional[Path]) -> dict:
    if trades_file and trades_file.exists():
        try:
            return json.loads(trades_file.read_text())
        except Exception as e:
            log.warning(f"Could not parse {trades_file}: {e}")
    return {}


def _load_latest_weights(weights_dir: Optional[Path]) -> Dict[str, float]:
    """Read the most recent target-weights CSV (columns: symbol/ticker
    /asset + weight/target_weight)."""
    if not weights_dir or not weights_dir.exists():
        return {}
    candidates = sorted(weights_dir.glob("*.csv"))
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


def _load_custom_facts(facts_file: Optional[Path]) -> dict:
    if facts_file and facts_file.exists():
        try:
            return yaml.safe_load(facts_file.read_text()) or {}
        except Exception as e:
            log.warning(f"Could not parse facts file {facts_file}: {e}")
    return {}


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


def build_snapshot(cfg=None, offline: bool = False) -> MarketSnapshot:
    """Assemble today's snapshot from the configured source."""
    from .config import PipelineConfig

    cfg = cfg or PipelineConfig()
    as_of = date.today().isoformat()

    if cfg.source.type == "custom":
        data = _load_custom_facts(cfg.source.resolved_facts_file())
        facts = [str(f) for f in data.get("facts", [])]
        if facts or data.get("headline"):
            return MarketSnapshot(
                as_of=as_of, headline=data.get("headline"), facts=facts
            )
        log.info("Custom facts file empty/missing — using demo snapshot")
        return _demo_snapshot(as_of)

    indexes = [] if offline else _load_indexes()
    state = _load_trades_state(cfg.source.resolved_trades_file())
    weights = _load_latest_weights(cfg.source.resolved_weights_dir())

    if not (indexes or state or weights):
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
