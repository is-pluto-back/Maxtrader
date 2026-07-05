"""Branded image cards rendered with Pillow — no API key required.

Produces:
- 1080x1080 square cards for social posts (market check + rotation)
- 1080x1920 vertical frames used as video slides

If ``OPENAI_API_KEY`` is set and ``media.use_ai_images`` is enabled in
``content_pipeline.yaml``, an additional AI-generated hero image is
requested from the OpenAI image API; failures fall back silently to the
Pillow cards, which are always rendered.
"""

import base64
import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from ..config import PipelineConfig
from ..snapshot import MarketSnapshot

log = logging.getLogger("content-pipeline.media.image")

# Brand palette (dark theme)
BG = (13, 17, 23)
PANEL = (22, 27, 34)
FG = (230, 237, 243)
MUTED = (139, 148, 158)
GREEN = (63, 185, 80)
RED = (248, 81, 73)
ACCENT = (88, 166, 255)

REGIME_COLORS = {
    "RISK_ON": GREEN,
    "NEUTRAL": (210, 153, 34),
    "RISK_OFF": RED,
    "FAST_RISK_OFF": RED,
}


def _font(size: int) -> ImageFont.FreeTypeFont:
    """Best available font without shipping font files."""
    for name in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


def _new_card(size: Tuple[int, int]) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", size, BG)
    return img, ImageDraw.Draw(img)


def _header(draw, width: int, brand: str, date_str: str, y: int = 60) -> int:
    draw.text((60, y), brand, font=_font(52), fill=ACCENT)
    draw.text((60, y + 70), date_str, font=_font(34), fill=MUTED)
    return y + 150


def _market_card(snap: MarketSnapshot, cfg: PipelineConfig, size, path: Path) -> Path:
    img, draw = _new_card(size)
    w, h = size
    y = _header(draw, w, cfg.brand.name, f"Daily Brief — {snap.as_of}")

    if snap.headline:
        import textwrap as _tw

        for line in _tw.wrap(snap.headline, width=32)[:3]:
            draw.text((60, y), line, font=_font(48), fill=FG)
            y += 62
        y += 20
        for fact in snap.facts[:4]:
            for line in _tw.wrap(f"• {fact}", width=48)[:2]:
                draw.text((60, y), line, font=_font(32), fill=MUTED)
                y += 44
            y += 10

    for ix in snap.indexes[:4]:
        color = GREEN if ix.change_pct >= 0 else RED
        draw.rounded_rectangle([60, y, w - 60, y + 110], radius=18, fill=PANEL)
        draw.text((90, y + 28), ix.name, font=_font(40), fill=FG)
        chg = f"{ix.change_pct:+.2f}%"
        draw.text((w - 90 - draw.textlength(chg, font=_font(44)), y + 26), chg, font=_font(44), fill=color)
        draw.text((90, y + 74), f"{ix.close:,.2f}", font=_font(28), fill=MUTED)
        y += 130

    if snap.regime:
        color = REGIME_COLORS.get(snap.regime.upper().replace("-", "_"), MUTED)
        y += 20
        draw.text((60, y), "MODEL REGIME", font=_font(30), fill=MUTED)
        draw.rounded_rectangle([60, y + 45, 60 + 420, y + 125], radius=18, fill=color)
        draw.text((90, y + 62), snap.regime.upper(), font=_font(44), fill=BG)
        y += 150

    if snap.demo_mode:
        draw.text((60, h - 120), "SAMPLE DATA", font=_font(28), fill=RED)
    draw.text((60, h - 70), "Automated research — not financial advice", font=_font(26), fill=MUTED)
    img.save(path)
    return path


def _rotation_card(snap: MarketSnapshot, cfg: PipelineConfig, size, path: Path) -> Path:
    img, draw = _new_card(size)
    w, h = size
    y = _header(draw, w, cfg.brand.name, f"Where the model is rotating — {snap.as_of}")

    top = sorted(snap.target_weights.items(), key=lambda kv: kv[1], reverse=True)[:6]
    max_w = max((wgt for _, wgt in top), default=0) or 1
    bar_area = w - 120 - 260
    for sym, wgt in top:
        draw.text((60, y + 10), sym, font=_font(40), fill=FG)
        bar_len = int(bar_area * (wgt / max_w))
        draw.rounded_rectangle([260, y, 260 + max(bar_len, 20), y + 60], radius=12, fill=ACCENT)
        draw.text((260 + max(bar_len, 20) + 20, y + 10), f"{wgt:.1%}", font=_font(36), fill=MUTED)
        y += 90

    if not top:
        draw.text((60, y), "Rebalance pending — cash preserved", font=_font(40), fill=MUTED)

    if snap.demo_mode:
        draw.text((60, h - 120), "SAMPLE DATA", font=_font(28), fill=RED)
    draw.text((60, h - 70), "Automated research — not financial advice", font=_font(26), fill=MUTED)
    img.save(path)
    return path


def _cta_frame(cfg: PipelineConfig, size, path: Path) -> Path:
    img, draw = _new_card(size)
    w, h = size
    draw.text((60, h // 3), cfg.brand.name, font=_font(72), fill=ACCENT)
    draw.text((60, h // 3 + 110), cfg.brand.tagline, font=_font(36), fill=FG)
    draw.text((60, h // 3 + 200), "Follow for tomorrow's signal", font=_font(44), fill=FG)
    if cfg.monetization.newsletter_signup_url:
        draw.text((60, h // 3 + 280), "Free daily brief — link in bio", font=_font(36), fill=MUTED)
    draw.text((60, h - 100), "Not financial advice", font=_font(28), fill=MUTED)
    img.save(path)
    return path


def hook_text(snap: MarketSnapshot) -> str:
    """Short scroll-stopping line derived from the day's strongest fact."""
    if snap.headline:
        return snap.headline
    if snap.indexes:
        ix = max(snap.indexes, key=lambda i: abs(i.change_pct))
        return f"{ix.name} {ix.change_pct:+.2f}% — what everyone missed"
    return "Today's signal, in 60 seconds"


def _thumbnail_card(snap: MarketSnapshot, cfg: PipelineConfig, path: Path) -> Path:
    """1280x720 YouTube-style thumbnail: huge hook text, accent bar."""
    import textwrap as _tw

    img, draw = _new_card((1280, 720))
    text = hook_text(snap)
    lines = _tw.wrap(text, width=18)[:3]
    size = 96 if len(lines) <= 2 else 76
    y = (720 - len(lines) * (size + 18)) // 2 - 30
    for line in lines:
        draw.text((70, y), line, font=_font(size), fill=FG)
        y += size + 18
    draw.rounded_rectangle([70, y + 14, 470, y + 30], radius=8, fill=ACCENT)
    draw.text((70, 640), cfg.brand.name.upper(), font=_font(34), fill=ACCENT)
    if snap.demo_mode:
        draw.text((1050, 640), "SAMPLE", font=_font(30), fill=RED)
    img.save(path)
    return path


def _ai_hero_image(snap: MarketSnapshot, cfg: PipelineConfig, path: Path) -> Optional[Path]:
    """Optional AI-generated hero via OpenAI's image API."""
    import requests

    key = os.getenv("OPENAI_API_KEY", "")
    if not key or key.startswith("your_"):
        return None
    mood = (snap.regime or "neutral").lower().replace("_", " ")
    try:
        r = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": cfg.media.openai_image_model,
                "prompt": (
                    f"Minimal dark-themed financial illustration, {mood} market "
                    "mood, abstract chart motifs, deep navy background, single "
                    "accent color, no text, editorial style"
                ),
                "size": "1024x1024",
            },
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()["data"][0]
        if "b64_json" in data:
            path.write_bytes(base64.b64decode(data["b64_json"]))
        else:
            path.write_bytes(requests.get(data["url"], timeout=60).content)
        return path
    except Exception as e:
        log.warning(f"AI hero image failed ({e}); using Pillow cards only")
        return None


def render_cards(
    snap: MarketSnapshot, cfg: PipelineConfig, out_dir: Path
) -> Tuple[List[Path], List[Path]]:
    """Render social cards (square) and video frames (vertical)."""
    square = tuple(cfg.media.image_size)
    vertical = tuple(cfg.media.video_size)
    d = snap.as_of

    images = [
        _market_card(snap, cfg, square, out_dir / f"{d}-card-market.png"),
        _rotation_card(snap, cfg, square, out_dir / f"{d}-card-rotation.png"),
    ]
    if cfg.media.use_ai_images:
        hero = _ai_hero_image(snap, cfg, out_dir / f"{d}-card-hero.png")
        if hero:
            images.insert(0, hero)

    # High-CTR thumbnail for the day's video (kept out of `images` so it
    # isn't posted as a social card; publishers use cards, humans use this)
    _thumbnail_card(snap, cfg, out_dir / f"{d}-thumbnail.png")

    frames = [
        _market_card(snap, cfg, vertical, out_dir / f"{d}-frame-1-market.png"),
        _rotation_card(snap, cfg, vertical, out_dir / f"{d}-frame-2-rotation.png"),
        _cta_frame(cfg, vertical, out_dir / f"{d}-frame-3-cta.png"),
    ]
    return images, frames
