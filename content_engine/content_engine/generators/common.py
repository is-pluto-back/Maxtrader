"""Shared formatting helpers for content generators."""

from __future__ import annotations

from typing import List

from ..models import Position, Trade


def fmt_money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def fmt_signed_money(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"


def fmt_pct(value: float) -> str:
    return f"{value:+.2f}%"


def positions_table(positions: List[Position]) -> str:
    if not positions:
        return "_No open positions._"
    lines = [
        "| Ticker | Shares | Avg Cost | Price | Market Value | P&L | P&L % |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for p in sorted(positions, key=lambda x: -abs(x.market_value)):
        lines.append(
            f"| {p.ticker} | {p.shares:g} | {fmt_money(p.avg_cost)} | "
            f"{fmt_money(p.current_price)} | {fmt_money(p.market_value)} | "
            f"{fmt_signed_money(p.pnl)} | {fmt_pct(p.pnl_pct)} |"
        )
    return "\n".join(lines)


def trades_table(trades: List[Trade]) -> str:
    if not trades:
        return "_No trades executed in this period._"
    lines = [
        "| Time | Action | Ticker | Qty | Price | Notional |",
        "|---|---|---|---:|---:|---:|",
    ]
    for t in trades:
        ts = t.timestamp.strftime("%Y-%m-%d %H:%M") if t.timestamp else "—"
        lines.append(
            f"| {ts} | {t.action.upper()} | {t.ticker} | {t.qty:g} | "
            f"{fmt_money(t.price)} | {fmt_money(t.notional)} |"
        )
    return "\n".join(lines)
