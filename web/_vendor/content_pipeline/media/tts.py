"""Voiceover synthesis for the daily short video.

Provider tiers (first configured wins):

1. ElevenLabs  — set ``ELEVENLABS_API_KEY`` (voice id configurable in
   ``content_pipeline.yaml``; defaults to the multilingual 'Rachel')
2. OpenAI TTS  — uses the existing ``OPENAI_API_KEY``
3. none        — the video is rendered silent

The narration text is the joined 'VO:' lines of the generated video
script, so the audio always matches the on-screen scenes.
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional

import requests

from ..config import PipelineConfig

log = logging.getLogger("content-pipeline.media.tts")


def extract_narration(video_script_md: str) -> str:
    """Pull the spoken lines out of a VISUAL:/VO: scene script."""
    lines = re.findall(r"^VO:\s*(.+)$", video_script_md, flags=re.MULTILINE)
    return " ".join(line.strip() for line in lines)


def _elevenlabs(text: str, cfg: PipelineConfig, path: Path) -> Optional[Path]:
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        return None
    voice = cfg.media.elevenlabs_voice_id
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=120,
    )
    r.raise_for_status()
    path.write_bytes(r.content)
    return path


def _openai_tts(text: str, cfg: PipelineConfig, path: Path) -> Optional[Path]:
    key = os.getenv("OPENAI_API_KEY", "")
    if not key or key.startswith("your_"):
        return None
    r = requests.post(
        "https://api.openai.com/v1/audio/speech",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": cfg.media.openai_tts_model,
            "voice": cfg.media.openai_tts_voice,
            "input": text,
        },
        timeout=120,
    )
    r.raise_for_status()
    path.write_bytes(r.content)
    return path


def synthesize_voiceover(
    video_script_md: str, cfg: PipelineConfig, out_dir: Path
) -> Optional[Path]:
    text = extract_narration(video_script_md)
    if not text:
        return None
    path = out_dir / "voiceover.mp3"
    for name, fn in (("elevenlabs", _elevenlabs), ("openai", _openai_tts)):
        try:
            result = fn(text, cfg, path)
            if result:
                log.info(f"Voiceover via {name}")
                return result
        except Exception as e:
            log.warning(f"{name} TTS failed ({e}); trying next tier")
    log.info("No TTS provider configured — video will be silent")
    return None
