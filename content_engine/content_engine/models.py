"""Typed views over the trading agent's state (trades.json)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@dataclass
class EquityPoint:
    timestamp: Optional[datetime]
    equity: float
    cash: float

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EquityPoint":
        return cls(
            timestamp=_parse_ts(d.get("timestamp")),
            equity=float(d.get("equity", 0.0)),
            cash=float(d.get("cash", 0.0)),
        )


@dataclass
class Position:
    ticker: str
    shares: float
    avg_cost: float
    current_price: float
    pnl: float

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Position":
        return cls(
            ticker=str(d.get("ticker", "?")),
            shares=float(d.get("shares", 0.0)),
            avg_cost=float(d.get("avg_cost", 0.0)),
            current_price=float(d.get("current_price", 0.0)),
            pnl=float(d.get("pnl", 0.0)),
        )

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def pnl_pct(self) -> float:
        basis = self.shares * self.avg_cost
        return (self.pnl / basis * 100.0) if basis else 0.0


@dataclass
class Trade:
    timestamp: Optional[datetime]
    action: str
    ticker: str
    qty: float
    price: float

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Trade":
        return cls(
            timestamp=_parse_ts(d.get("timestamp")),
            action=str(d.get("action", "unknown")).lower(),
            ticker=str(d.get("ticker", "?")),
            qty=float(d.get("qty", 0.0)),
            price=float(d.get("price", 0.0)),
        )

    @property
    def notional(self) -> float:
        return self.qty * self.price


@dataclass
class PortfolioState:
    agent_running: bool = False
    last_updated: Optional[datetime] = None
    equity_curve: List[EquityPoint] = field(default_factory=list)
    positions: List[Position] = field(default_factory=list)
    trade_history: List[Trade] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioState":
        return cls(
            agent_running=bool(d.get("agent_running", False)),
            last_updated=_parse_ts(d.get("last_updated")),
            equity_curve=[EquityPoint.from_dict(p) for p in d.get("equity_curve", [])],
            positions=[Position.from_dict(p) for p in d.get("positions", [])],
            trade_history=[Trade.from_dict(t) for t in d.get("trade_history", [])],
        )

    @property
    def equity(self) -> float:
        return self.equity_curve[-1].equity if self.equity_curve else 0.0

    @property
    def cash(self) -> float:
        return self.equity_curve[-1].cash if self.equity_curve else 0.0

    def equity_change(self, points_back: int = 1) -> Optional[float]:
        """Absolute equity change vs `points_back` snapshots ago, or None."""
        if len(self.equity_curve) <= points_back:
            return None
        return self.equity_curve[-1].equity - self.equity_curve[-1 - points_back].equity

    def trades_between(
        self, start: Optional[datetime] = None, end: Optional[datetime] = None
    ) -> List[Trade]:
        out = []
        for t in self.trade_history:
            if t.timestamp is None:
                continue
            if start and t.timestamp < start:
                continue
            if end and t.timestamp > end:
                continue
            out.append(t)
        return out
