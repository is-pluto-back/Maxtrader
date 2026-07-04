"""Media generation: branded images, voiceover, and short-form video.

Everything is tiered so the pipeline never blocks on a missing tool:

- images:  OpenAI image API (if key)  ->  Pillow-rendered brand cards (no key)
- voice:   ElevenLabs  ->  OpenAI TTS  ->  silent video
- video:   ffmpeg (system or the binary bundled with `imageio-ffmpeg`)
           ->  skipped gracefully if neither exists

Media is attached to content and picked up by publishers that support
it (Telegram photos/videos, Discord attachments, blog embeds).
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ..config import PipelineConfig
from ..snapshot import MarketSnapshot

log = logging.getLogger("content-pipeline.media")


@dataclass
class MediaBundle:
    images: List[Path] = field(default_factory=list)  # square social cards
    frames: List[Path] = field(default_factory=list)  # vertical video frames
    video: Optional[Path] = None
    voiceover: Optional[Path] = None


def build_media(
    snap: MarketSnapshot,
    cfg: PipelineConfig,
    out_dir: Path,
    video_script_md: Optional[str] = None,
) -> MediaBundle:
    """Generate the day's media bundle. Any stage that can't run (missing
    library, binary, or key) logs and is skipped."""
    bundle = MediaBundle()
    out_dir.mkdir(parents=True, exist_ok=True)

    if cfg.media.enable_images:
        try:
            from .image_gen import render_cards

            bundle.images, bundle.frames = render_cards(snap, cfg, out_dir)
            log.info(f"Rendered {len(bundle.images)} card(s), {len(bundle.frames)} frame(s)")
        except ImportError:
            log.info("Pillow not installed — skipping image generation")
        except Exception as e:
            log.warning(f"Image generation failed: {e}")

    if cfg.media.enable_video and bundle.frames:
        voiceover = None
        if video_script_md:
            try:
                from .tts import synthesize_voiceover

                voiceover = synthesize_voiceover(video_script_md, cfg, out_dir)
                if voiceover:
                    log.info(f"Voiceover synthesized: {voiceover.name}")
            except Exception as e:
                log.warning(f"TTS failed (video will be silent): {e}")
        bundle.voiceover = voiceover

        try:
            from .video_gen import render_video

            bundle.video = render_video(bundle.frames, cfg, out_dir, voiceover)
            if bundle.video:
                log.info(f"Video rendered: {bundle.video.name}")
        except Exception as e:
            log.warning(f"Video rendering failed: {e}")

    return bundle
