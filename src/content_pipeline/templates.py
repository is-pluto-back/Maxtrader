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
    lines: List[str] = [f"# {brand_name} — Daily Brief ({s.as_of})", ""]

    if s.headline:
        lines += [f"## {s.headline}", ""]
    if s.facts:
        lines += ["## Today's Facts", ""]
        lines += [f"- {fact}" for fact in s.facts]
        lines.append("")

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
    if s.headline:
        hook += f"\n\n{s.headline}"
    if s.indexes:
        ix = s.indexes[0]
        direction = "higher" if ix.change_pct >= 0 else "lower"
        hook += f"\n\n{ix.name} closed {direction} at {ix.close:,.0f} ({ix.change_pct:+.2f}%)."
    tweets.append(hook)

    if s.facts:
        tweets.append("🔍 " + " ".join(s.facts[:2])[:250])

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


def video_script(snapshot: MarketSnapshot, brand_name: str) -> str:
    """~60-second vertical short script with VISUAL/VO scene blocks."""
    s = snapshot
    scenes: List[str] = [f"# {brand_name} — Daily Short Script ({s.as_of})", ""]

    if s.headline and not s.indexes:
        scenes += [
            "## SCENE 1 (hook, 3s)",
            f"VISUAL: Bold headline text: {s.headline}",
            f"VO: {s.headline} — here's what you need to know today.",
            "",
        ]
        for i, fact in enumerate(s.facts[:3], start=2):
            scenes += [
                f"## SCENE {i} (12s)",
                f"VISUAL: Key point graphic #{i - 1}",
                f"VO: {fact}",
                "",
            ]

    if s.indexes:
        ix = max(s.indexes, key=lambda i: abs(i.change_pct))
        direction = "up" if ix.change_pct >= 0 else "down"
        scenes += [
            "## SCENE 1 (hook, 3s)",
            f"VISUAL: Bold full-screen number: {ix.change_pct:+.2f}% over a {direction}-trending chart",
            f"VO: {ix.name} just moved {ix.change_pct:+.2f} percent. Here's what our AI model did about it.",
            "",
        ]

    if s.regime:
        scenes += [
            "## SCENE 2 (regime, 12s)",
            f"VISUAL: Regime dial graphic pointing to '{s.regime}'",
            f"VO: Our regime model reads the market as {s.regime.lower().replace('_', ' ')}. "
            + _regime_narrative(s.regime).split(":")[-1].strip(),
            "",
        ]

    if s.target_weights:
        top = sorted(s.target_weights.items(), key=lambda kv: kv[1], reverse=True)[:3]
        tickers = ", ".join(sym for sym, _ in top)
        scenes += [
            "## SCENE 3 (rotation, 15s)",
            f"VISUAL: Animated bar list of top allocations: "
            + ", ".join(f"{sym} {w:.0%}" for sym, w in top),
            f"VO: The rotation engine is concentrating in {tickers} this week — "
            "systematic weights, no gut feel, rebalanced every Friday.",
            "",
        ]

    if s.equity is not None and s.equity_change_pct is not None:
        scenes += [
            "## SCENE 4 (portfolio pulse, 10s)",
            "VISUAL: Equity curve ticking up-to-date",
            f"VO: The model portfolio moved {s.equity_change_pct:+.2f} percent on the session, "
            "with stop-losses monitored daily.",
            "",
        ]

    scenes += [
        "## SCENE 5 (CTA, 8s)",
        "VISUAL: Logo + subscribe button animation",
        "VO: Follow for tomorrow's signal, and grab the free daily brief — link in bio. "
        "Not financial advice.",
    ]
    return "\n".join(scenes).strip()


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


def production_pack(snapshot: MarketSnapshot, cfg) -> str:
    """Daily production toolchain doc: platform scripts, copy-paste
    prompts for image/video/voice tools, distribution metadata."""
    s = snapshot
    brand = cfg.brand.name
    hook_fact = s.headline or (
        f"{max(s.indexes, key=lambda i: abs(i.change_pct)).name} moved "
        f"{max(s.indexes, key=lambda i: abs(i.change_pct)).change_pct:+.2f}% today"
        if s.indexes
        else "today's update"
    )
    persona_block = (
        cfg.persona.consistency_block()
        if cfg.persona.enabled
        else "No persona configured — use brand-graphic visuals (see media cards)"
    )
    topic = s.headline or f"{cfg.brand.subject} — {s.as_of}"

    return f"""# {brand} — Production Pack ({s.as_of})

## 1. Scripts (retention structure: hook → agitate → deliver → CTA)

### Short-form primary (TikTok / Reels / Shorts, 45-60s)
- **HOOK (0-3s)**: "{hook_fact} — here's what almost everyone missed."
  - On-screen text: bold 4-6 word version of the hook
  - VO emotion: urgent, confident
- **AGITATE (3-12s)**: why this matters to the viewer today
- **DELIVER (12-45s)**: the 3 key facts, one per beat:
{chr(10).join(f"  - {fact}" for fact in (s.facts[:3] or s.summary_lines()[1:4]))}
  - On-screen text: one stat per beat, large type
- **CTA (45-60s)**: "Follow for tomorrow's update — full brief free, link in bio."
  - VO emotion: warm, direct

### Platform adaptations
- **YouTube Shorts**: same script; add end-screen loop line ("watch this next")
- **X thread**: use today's social_thread output (generated separately)
- **YouTube long-form (8-12min)**: expand each DELIVER beat to 2-3 min with
  examples; add chapter markers per beat; mid-roll CTA at ~40%

## 2. Visuals — copy-paste prompts

### Character consistency block (prepend to EVERY visual prompt)
> {persona_block}

### Image generation (Midjourney / Flux / Leonardo)
> Editorial cover image about {topic}. Dark premium palette, single accent
> color, cinematic soft light, negative space for title text, no words,
> 4k detail --ar 9:16

### AI video (Runway Gen-3 / Kling / Luma / Pika)
> {persona_block}. Medium close-up, speaking to camera about {topic},
> natural hand gestures, shallow depth of field, soft key light,
> subtle push-in, photorealistic, 5s

### Talking head (HeyGen / Synthesia / Hedra)
- Paste the short-form VO lines below into the avatar tool
- Camera: waist-up, eye contact, 10% headroom; captions ON (85% watch muted)

## 3. Voiceover (ElevenLabs / OpenAI TTS)
- Voice: {cfg.media.openai_tts_voice} (or your ElevenLabs voice
  {cfg.media.elevenlabs_voice_id})
- Direction: conversational pace ~150wpm; punch the hook; pause after
  each stat; upward energy into the CTA
- The pipeline auto-generates this narration from today's video_script
  VO lines when a TTS key is set

## 4. Edit checklist (CapCut / Descript / Premiere)
- Cut on every sentence; max 2s without visual change
- Auto-captions, keyword highlights in accent color
- Trending low-volume music bed (-18dB under VO)
- First frame = hook text already visible (thumbnail-safe)

## 5. Distribution
- **Title options**:
  1. {hook_fact} (what it means for you)
  2. Nobody is talking about this: {topic}
  3. The 60-second read on {topic}
- **Description**: 1-line summary + newsletter link + disclaimer
- **Hashtags**: 3-5 niche + 1-2 broad; platform-native (no cross-paste)
- **Schedule**: post short-form within 2h of this pack; thread at peak
  audience hour; long-form weekly
- **Track**: 3s hold rate (target >70%), avg retention (>45%), CTR on
  bio link — log with `run_content_pipeline.py metrics`

## 6. Monetization hooks in this piece
- Newsletter CTA: {cfg.monetization.newsletter_signup_url or "(set newsletter_signup_url)"}
- Premium tier: {cfg.monetization.premium_url or "(set premium_url)"}
- Affiliate slots auto-match keywords: {", ".join(a.name for a in cfg.monetization.affiliates) or "(none configured)"}
"""
