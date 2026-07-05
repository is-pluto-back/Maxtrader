"""Trend research: what should today's content be about?

Pulls trending signals from free, keyless sources and ranks them into
concrete content ideas scored for virality + monetization fit:

- Google Trends daily RSS (per-region trending searches)
- Reddit top posts (any subreddits you configure for your niche)
- Hacker News front page (tech niches)

Ranking uses the configured LLM when available; otherwise a heuristic
ranker keys on the niche keywords. Fully offline it emits evergreen
idea patterns, clearly flagged.

CLI: ``python run_content_pipeline.py research``
"""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from typing import List

import requests

log = logging.getLogger("content-pipeline.trends")

UA = {"User-Agent": "content-engine/1.0 (trend research)"}


@dataclass
class ResearchConfig:
    geo: str = "US"                       # Google Trends region
    subreddits: List[str] = field(default_factory=list)  # e.g. [investing, stocks]
    keywords: List[str] = field(default_factory=list)    # niche terms for ranking
    include_hackernews: bool = False      # useful for tech niches


def fetch_google_trends(geo: str = "US", limit: int = 10) -> List[str]:
    try:
        r = requests.get(
            f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}",
            headers=UA,
            timeout=15,
        )
        r.raise_for_status()
        root = ET.fromstring(r.content)
        return [t.text for t in root.iter("title") if t.text][1 : limit + 1]
    except Exception as e:
        log.debug(f"Google Trends fetch failed: {e}")
        return []


def fetch_reddit_top(subreddit: str, limit: int = 8) -> List[str]:
    try:
        r = requests.get(
            f"https://www.reddit.com/r/{subreddit}/top.json?t=day&limit={limit}",
            headers=UA,
            timeout=15,
        )
        r.raise_for_status()
        children = r.json().get("data", {}).get("children", [])
        return [c["data"]["title"] for c in children if c.get("data", {}).get("title")]
    except Exception as e:
        log.debug(f"Reddit fetch failed for r/{subreddit}: {e}")
        return []


def fetch_hackernews_top(limit: int = 10) -> List[str]:
    try:
        r = requests.get(
            "https://hn.algolia.com/api/v1/search?tags=front_page",
            headers=UA,
            timeout=15,
        )
        r.raise_for_status()
        return [h["title"] for h in r.json().get("hits", [])[:limit] if h.get("title")]
    except Exception as e:
        log.debug(f"Hacker News fetch failed: {e}")
        return []


EVERGREEN_PATTERNS = [
    "The one mistake beginners in {niche} keep making (and the fix)",
    "I automated {niche} for 30 days — here's what actually happened",
    "5 {niche} tools that feel like cheating in 2026",
    "What nobody tells you about {niche} before you start",
    "The 60-second {niche} routine that outperforms the 2-hour version",
]


def gather_signals(research: ResearchConfig, offline: bool = False) -> List[str]:
    """Collect raw trending titles from all configured sources."""
    if offline:
        return []
    signals: List[str] = []
    signals += fetch_google_trends(research.geo)
    for sub in research.subreddits[:5]:
        signals += fetch_reddit_top(sub)
    if research.include_hackernews:
        signals += fetch_hackernews_top()
    # dedupe, keep order
    seen = set()
    out = []
    for s in signals:
        key = s.lower().strip()
        if key not in seen:
            seen.add(key)
            out.append(s.strip())
    return out


def _heuristic_rank(signals: List[str], keywords: List[str], top_n: int = 5) -> List[str]:
    """No-LLM ranking: keyword hits first, then position (recency/rank)."""
    def score(item):
        idx, text = item
        low = text.lower()
        hits = sum(1 for kw in keywords if kw.lower() in low)
        return (-hits, idx)

    ranked = sorted(enumerate(signals), key=score)
    return [text for _, text in ranked[:top_n]]


def _llm_rank(signals: List[str], cfg, top_n: int = 5) -> str:
    """Rank + reframe signals into content ideas via the LLM tiers."""
    from .generator import _call_anthropic, _call_openai

    system = (
        f"You are a content strategist for '{cfg.brand.name}' "
        f"({cfg.brand.subject}). You know what makes short-form and "
        "long-form content go viral: scroll-stopping hooks, emotional "
        "triggers, clear payoffs — and what monetizes: affiliate-friendly "
        "topics, audience-building angles."
    )
    user = (
        f"Here are today's raw trending signals:\n\n"
        + "\n".join(f"- {s}" for s in signals[:40])
        + f"\n\nSelect and reframe the {top_n} best into content ideas for "
        "our niche. For each, output markdown: a numbered idea title "
        "(written as a scroll-stopping hook), one line on WHY it can go "
        "viral now, one line on the monetization angle (affiliate/lead "
        "magnet/sponsor fit), and the best format (short/long/thread). "
        "Only use the signals provided."
    )
    for fn, key in ((_call_anthropic, cfg.llm.anthropic_api_key),
                    (_call_openai, cfg.llm.openai_api_key)):
        if not key:
            continue
        try:
            return fn(cfg, system, user)
        except Exception as e:
            log.warning(f"LLM ranking failed ({e}); trying next tier")
    return ""


def research_ideas(cfg, offline: bool = False, top_n: int = 5) -> str:
    """Produce today's ranked content-ideas document (markdown)."""
    research = getattr(cfg, "research", ResearchConfig())
    signals = gather_signals(research, offline=offline)
    today = date.today().isoformat()
    header = f"# Content ideas — {today}\n"

    if not signals:
        niche = (research.keywords or ["your niche"])[0]
        ideas = [p.format(niche=niche) for p in EVERGREEN_PATTERNS[:top_n]]
        body = "\n".join(f"{i}. {idea}" for i, idea in enumerate(ideas, 1))
        return (
            f"{header}\n> No live trend feeds reachable — evergreen patterns "
            f"below (flagged, not trends).\n\n{body}\n"
        )

    llm_output = _llm_rank(signals, cfg, top_n)
    if llm_output:
        return f"{header}\n{llm_output}\n"

    top = _heuristic_rank(signals, research.keywords, top_n)
    body = "\n".join(f"{i}. {t}" for i, t in enumerate(top, 1))
    return (
        f"{header}\n> Ranked heuristically by niche-keyword match "
        f"(add an LLM key for hook-rewritten ideas).\n\n{body}\n\n"
        f"<details><summary>All {len(signals)} raw signals</summary>\n\n"
        + "\n".join(f"- {s}" for s in signals)
        + "\n</details>\n"
    )
