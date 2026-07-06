"""Optional Claude-powered polish for generated content.

The template generators produce correct, data-grounded markdown on their own.
This module optionally rewrites that draft into a more readable narrative via
the Claude API. It requires the ``anthropic`` package and an API key
(``ANTHROPIC_API_KEY`` env var or an ``ant auth login`` profile); when neither
is available, ``polish()`` returns the draft unchanged.
"""

from __future__ import annotations

DEFAULT_MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = (
    "You are the editor for an algorithmic trading journal. You receive a "
    "data-generated markdown draft (portfolio report, weekly review, or "
    "social post). Rewrite it into clear, engaging prose while keeping every "
    "number, ticker, table, and the trailing disclaimer exactly as given. "
    "Never invent trades, prices, or performance figures that are not in the "
    "draft. Return only the rewritten markdown."
)


def polish(draft: str, model: str = DEFAULT_MODEL) -> str:
    """Return an LLM-polished version of `draft`, or `draft` on any failure."""
    try:
        import anthropic
    except ImportError:
        return draft

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": draft}],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return text or draft
    except Exception:
        # Content generation must never fail because polish did — the
        # template draft is always a valid deliverable.
        return draft
