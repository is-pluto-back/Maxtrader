"""Monetization layer: turns generated content into revenue-carrying content.

Applied after generation, before publishing:

1. **Affiliate links** — if a configured product's keyword appears in the
   body, a 'Tools we use' section links to it (with UTM tracking).
2. **Newsletter / premium CTAs** — grow the owned audience (the durable
   revenue asset) and upsell the paid tier.
3. **Sponsor slot** — a bookable placement, rendered only when booked.
4. **Compliance disclaimer** — always appended to finance content.

Social threads get a lighter treatment (link + disclaimer only) since
platforms penalize link-stuffed posts.
"""

from typing import List
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from .config import MonetizationConfig
from .generator import GeneratedContent


def add_utm(url: str, source: str, medium: str, campaign: str) -> str:
    """Append UTM parameters, preserving existing query params."""
    if not url:
        return url
    parts = urlparse(url)
    query = dict(parse_qsl(parts.query))
    query.setdefault("utm_source", source)
    query.setdefault("utm_medium", medium)
    query.setdefault("utm_campaign", campaign)
    return urlunparse(parts._replace(query=urlencode(query)))


def _matched_affiliates(body: str, cfg: MonetizationConfig) -> List:
    """Affiliates whose keywords appear in the content (max 2, so the
    footer stays tasteful)."""
    body_lower = body.lower()
    matches = []
    for product in cfg.affiliates:
        keywords = product.keywords or [product.name]
        if any(kw.lower() in body_lower for kw in keywords):
            matches.append(product)
    return matches[:2]


def monetize(content: GeneratedContent, cfg: MonetizationConfig) -> GeneratedContent:
    """Return a copy of the content with revenue blocks appended."""
    campaign = content.content_type
    medium = "social" if content.content_type == "social_thread" else "content"

    if content.content_type == "social_thread":
        # Light touch: signup link woven into the final tweet if configured.
        body = content.body
        if cfg.newsletter_signup_url:
            link = add_utm(cfg.newsletter_signup_url, cfg.utm_source, medium, campaign)
            body += f"\n---\n📬 Free daily brief in your inbox: {link}"
        return GeneratedContent(content.content_type, content.title, body, content.provider)

    sections: List[str] = [content.body, ""]

    if cfg.sponsor_slot:
        sections += ["---", "", f"**Sponsored** — {cfg.sponsor_slot}", ""]

    matched = _matched_affiliates(content.body, cfg)
    if matched:
        sections += ["---", "", "### Tools we use", ""]
        for p in matched:
            link = add_utm(p.url, cfg.utm_source, medium, campaign)
            sections.append(f"- **[{p.name}]({link})** — {p.blurb}")
        sections.append("")

    if cfg.newsletter_cta and cfg.newsletter_signup_url:
        link = add_utm(cfg.newsletter_signup_url, cfg.utm_source, medium, campaign)
        sections += ["---", "", f"📬 **{cfg.newsletter_cta}** [Subscribe free]({link})", ""]

    if cfg.premium_cta and cfg.premium_url:
        link = add_utm(cfg.premium_url, cfg.utm_source, medium, campaign)
        sections += [f"⭐ **{cfg.premium_cta}** [Go premium]({link})", ""]

    if cfg.disclaimer:
        sections += ["---", "", f"*{' '.join(cfg.disclaimer.split())}*"]

    return GeneratedContent(
        content.content_type,
        content.title,
        "\n".join(sections).strip(),
        content.provider,
    )
