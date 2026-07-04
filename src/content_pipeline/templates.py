"""Deterministic template generator — the zero-API-key fallback.

Produces respectable (if formulaic) content directly from the snapshot,
so the pipeline never blocks on a missing LLM key. When an LLM provider
is configured, these templates are bypassed.
"""

from datetime import datetime
from typing import List

from .snapshot import MarketSnapshot


def _regime_narrative(regime: str) -> str:
    narratives = {
        "RISK_ON": (
            "The model is fully risk-on: breadth and momentum support "
            "full allocation to the two strongest asset groups."
        ),
        "NEUTRAL": (
            "The model sits in neutral: allocation is trimmed and capped at "
            "70% per group while trend signals stay mixed."
        ),
        "RISK_OFF": (
            "The model is defensive: group caps drop to 50% with a 30% cash "
            "floor until conditions improve."
        ),
        "FAST_RISK_OFF": (
            "Shock protocol engaged: the daily fast risk-off trigger fired, "
            "moving 50% of the book to cash immediately."
        ),
    }
    return narratives.get(
        (regime or "").upper().replace("-", "_"),
        "The model's regime signal is currently unavailable.",
    )


def daily_brief(snapshot: MarketSnapshot, brand_name: str) -> str:
    s = snapshot
    lines: List[str] = [f"# {brand_name} — Daily Market Brief ({s.as_of})", ""]

    if s.indexes:
        lines.append("## Market Check")
        for ix in s.indexes:
            arrow = "🟢" if ix.change_pct >= 0 else "🔴"
            lines.append(f"- {arrow} **{ix.name}**: {ix.close:,.2f} ({ix.change_pct:+.2f}%)")
        lines.append("")

    if s.regime:
        lines.append("## Regime Signal")
        lines.append(_regime_narrative(s.regime))
        lines.append("")

    if s.target_weights:
        lines.append("## Where the Model Is Rotating")
        top = sorted(s.target_weights.items(), key=lambda kv: kv[1], reverse=True)[:5]
        for sym, w in top:
            lines.append(f"- **{sym}** — {w:.1%} target weight")
        lines.append("")

    if s.equity is not None:
        lines.append("## Portfolio Pulse")
        chg = (
            f", {s.equity_change_pct:+.2f}% vs the prior session"
            if s.equity_change_pct is not None
            else ""
        )
        lines.append(f"Model portfolio equity stands at ${s.equity:,.2f}{chg}.")
        if s.positions:
            best = max(s.positions, key=lambda p: p.pnl)
            worst = min(s.positions, key=lambda p: p.pnl)
            lines.append(
                f"Leader: **{best.ticker}** (${best.pnl:+,.2f} open P&L). "
                f"Laggard: **{worst.ticker}** (${worst.pnl:+,.2f})."
            )
        lines.append("")

    if s.recent_trades:
        lines.append("## Latest Rotations")
        for t in s.recent_trades[-5:]:
            lines.append(
                f"- {str(t.get('action', '?')).upper()} {t.get('qty', '?')} × "
                f"{t.get('ticker', '?')}"
            )
        lines.append("")

    return "\n".join(lines).strip()


def social_thread(snapshot: MarketSnapshot, brand_name: str) -> str:
    """A short X/Twitter thread; tweets separated by a line with '---'."""
    s = snapshot
    tweets: List[str] = []

    hook = f"📊 {brand_name} daily signal — {s.as_of}"
    if s.indexes:
        ix = s.indexes[0]
        direction = "higher" if ix.change_pct >= 0 else "lower"
        hook += f"\n\n{ix.name} closed {direction} at {ix.close:,.0f} ({ix.change_pct:+.2f}%)."
    tweets.append(hook)

    if s.regime:
        tweets.append(
            f"🤖 Our regime model reads the tape as: {s.regime}\n\n"
            + _regime_narrative(s.regime)
        )

    if s.target_weights:
        top = sorted(s.target_weights.items(), key=lambda kv: kv[1], reverse=True)[:4]
        tweets.append(
            "🔄 Where the rotation model is allocating right now:\n\n"
            + "\n".join(f"• ${sym}: {w:.0%}" for sym, w in top)
        )

    tweets.append(
        "Want the full daily brief with position-level detail? "
        "Link in bio. 🔔 Follow for tomorrow's signal.\n\n"
        "Not financial advice — automated research output."
    )
    return "\n---\n".join(tweets)


def newsletter(snapshot: MarketSnapshot, brand_name: str, tagline: str) -> str:
    s = snapshot
    week_of = datetime.strptime(s.as_of, "%Y-%m-%d").strftime("%B %d, %Y")
    body = [
        f"# {brand_name} Weekly — week of {week_of}",
        "",
        f"*{tagline}*",
        "",
        "## The Week in One Paragraph",
        "",
    ]
    if s.indexes:
        parts = ", ".join(
            f"{ix.name} at {ix.close:,.0f} ({ix.change_pct:+.2f}%)" for ix in s.indexes
        )
        body.append(
            f"Markets closed the week with {parts}. "
            + (_regime_narrative(s.regime) if s.regime else "")
        )
    else:
        body.append(_regime_narrative(s.regime) if s.regime else "Quiet week on the data front.")
    body.append("")

    body.append(daily_brief(s, brand_name).split("\n", 2)[-1])
    body += [
        "",
        "## What We're Watching Next Week",
        "",
        "- Whether the regime signal holds or flips at Friday's rebalance",
        "- Relative strength across the four asset groups (Growth/Tech, "
        "Cyclical, Real Assets, Defensive)",
        "- Stop-loss proximity on the weakest open positions",
    ]
    return "\n".join(body).strip()
