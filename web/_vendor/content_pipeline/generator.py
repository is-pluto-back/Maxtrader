"""Content generation with graceful degradation:

    Anthropic API  ->  OpenAI API  ->  deterministic templates

Providers are called over plain HTTPS (``requests``) so no SDK
dependencies are needed. A provider is used only if its key is present;
any provider error falls through to the next tier rather than failing
the pipeline.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import requests

from . import templates
from .config import PipelineConfig
from .snapshot import MarketSnapshot

log = logging.getLogger("content-pipeline.generator")

CONTENT_TYPES = ("daily_brief", "social_thread", "newsletter", "video_script")


@dataclass
class GeneratedContent:
    content_type: str  # one of CONTENT_TYPES
    title: str
    body: str  # markdown; social threads use '---' between tweets
    provider: str  # 'anthropic' | 'openai' | 'template'
    images: List[Path] = field(default_factory=list)  # attached media
    video: Optional[Path] = None


_PROMPTS = {
    "daily_brief": (
        "Write a daily market brief in markdown (350-500 words) titled "
        "'{brand} — Daily Market Brief ({date})'. Structure: market check "
        "(index moves), the strategy's regime signal explained for a smart "
        "retail audience, where the rotation model is allocating, and a "
        "portfolio pulse section. Use ONLY the facts provided below — do not "
        "invent numbers. End without a sign-off; a footer is added later."
    ),
    "social_thread": (
        "Write a 4-5 tweet X thread about today's market and our quant "
        "model's signal. Each tweet under 270 characters, separated by a "
        "line containing only '---'. Tweet 1 is a strong hook with the "
        "biggest index move. Include the regime signal and top allocations. "
        "Final tweet: soft CTA to follow + 'Not financial advice'. Use ONLY "
        "the facts provided; never fabricate numbers."
    ),
    "newsletter": (
        "Write a weekly markdown newsletter (600-800 words) titled "
        "'{brand} Weekly'. Sections: 'The Week in One Paragraph', a regime "
        "deep-dive explaining what the signal means in plain English, "
        "'Where the Model Is Rotating' with the target weights, and 'What "
        "We're Watching Next Week' (3 bullets). Voice: {voice}. Use ONLY "
        "the facts provided; never fabricate numbers."
    ),
    "video_script": (
        "Write a 55-60 second vertical short-form video script (YouTube "
        "Shorts / TikTok / Reels) about today's market and our quant "
        "model's signal. Format as markdown with numbered SCENE blocks. "
        "Each scene has 'VISUAL:' (one line describing the on-screen shot "
        "or graphic) and 'VO:' (the spoken narration, conversational, max "
        "~25 words). Scene 1 is a 3-second hook stating the biggest move. "
        "Include the regime signal and the top rotations. Final scene: "
        "soft follow/subscribe CTA plus a spoken 'not financial advice'. "
        "Use ONLY the facts provided; never fabricate numbers."
    ),
}


def _system_prompt(cfg: PipelineConfig) -> str:
    return (
        f"You are the writer for '{cfg.brand.name}' — {cfg.brand.tagline} "
        f"Voice: {cfg.brand.voice} You write about an automated adaptive "
        "rotation trading strategy. Never give direct buy/sell advice, never "
        "promise returns, and never invent data that was not provided."
    )


def _user_prompt(content_type: str, cfg: PipelineConfig, snap: MarketSnapshot) -> str:
    instructions = _PROMPTS[content_type].format(
        brand=cfg.brand.name, date=snap.as_of, voice=cfg.brand.voice
    )
    facts = "\n".join(snap.summary_lines())
    return f"{instructions}\n\nToday's facts:\n{facts}"


def _call_anthropic(cfg: PipelineConfig, system: str, user: str) -> str:
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": cfg.llm.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": cfg.llm.anthropic_model,
            "max_tokens": cfg.llm.max_tokens,
            "temperature": cfg.llm.temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=cfg.llm.request_timeout,
    )
    r.raise_for_status()
    return "".join(
        block.get("text", "") for block in r.json().get("content", [])
    ).strip()


def _call_openai(cfg: PipelineConfig, system: str, user: str) -> str:
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {cfg.llm.openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": cfg.llm.openai_model,
            "max_tokens": cfg.llm.max_tokens,
            "temperature": cfg.llm.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=cfg.llm.request_timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _template_fallback(content_type: str, cfg: PipelineConfig, snap: MarketSnapshot) -> str:
    if content_type == "daily_brief":
        return templates.daily_brief(snap, cfg.brand.name)
    if content_type == "social_thread":
        return templates.social_thread(snap, cfg.brand.name)
    if content_type == "video_script":
        return templates.video_script(snap, cfg.brand.name)
    return templates.newsletter(snap, cfg.brand.name, cfg.brand.tagline)


def _title_for(content_type: str, cfg: PipelineConfig, snap: MarketSnapshot) -> str:
    if content_type == "daily_brief":
        return f"{cfg.brand.name} — Daily Market Brief ({snap.as_of})"
    if content_type == "social_thread":
        return f"{cfg.brand.name} — Daily Thread ({snap.as_of})"
    if content_type == "video_script":
        return f"{cfg.brand.name} — Daily Short Script ({snap.as_of})"
    return f"{cfg.brand.name} Weekly ({snap.as_of})"


def generate(
    content_type: str,
    cfg: PipelineConfig,
    snap: MarketSnapshot,
    force_provider: Optional[str] = None,
) -> GeneratedContent:
    """Generate one piece of content, falling through provider tiers."""
    if content_type not in CONTENT_TYPES:
        raise ValueError(f"Unknown content type: {content_type}")

    system = _system_prompt(cfg)
    user = _user_prompt(content_type, cfg, snap)
    title = _title_for(content_type, cfg, snap)

    tiers = []
    if cfg.llm.anthropic_api_key:
        tiers.append(("anthropic", _call_anthropic))
    if cfg.llm.openai_api_key:
        tiers.append(("openai", _call_openai))
    if force_provider == "template":
        tiers = []
    elif force_provider:
        tiers = [t for t in tiers if t[0] == force_provider]

    for name, fn in tiers:
        try:
            body = fn(cfg, system, user)
            if body:
                log.info(f"Generated {content_type} via {name}")
                return GeneratedContent(content_type, title, body, name)
        except Exception as e:
            log.warning(f"{name} generation failed ({e}); trying next tier")

    log.info(f"Generated {content_type} via templates (no LLM available)")
    body = _template_fallback(content_type, cfg, snap)
    return GeneratedContent(content_type, title, body, "template")
