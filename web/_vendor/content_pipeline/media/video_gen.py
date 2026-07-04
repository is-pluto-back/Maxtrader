"""Short-form video rendering (1080x1920 vertical) with ffmpeg.

Builds a slideshow from the day's rendered frames, muxing in the
voiceover when one was synthesized. ffmpeg is resolved from PATH first,
then from the static binary shipped with the optional ``imageio-ffmpeg``
package (``pip install imageio-ffmpeg`` — no system install needed).

For fully AI-generated footage instead of brand cards, point
``media.replicate_video_model`` at a Replicate model and set
``REPLICATE_API_TOKEN``; the slideshow remains the no-key fallback.
"""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from ..config import PipelineConfig

log = logging.getLogger("content-pipeline.media.video")


def find_ffmpeg() -> Optional[str]:
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def render_video(
    frames: List[Path],
    cfg: PipelineConfig,
    out_dir: Path,
    voiceover: Optional[Path] = None,
) -> Optional[Path]:
    """Concat frames into an H.264 MP4; returns None if ffmpeg is missing."""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        log.info("ffmpeg not found — skipping video (pip install imageio-ffmpeg)")
        return None
    if not frames:
        return None

    seconds = cfg.media.seconds_per_slide
    concat_file = out_dir / "slides.txt"
    # concat demuxer: last file must be listed twice (duration is ignored
    # for the final entry otherwise)
    lines = []
    for f in frames:
        lines.append(f"file '{f.resolve()}'")
        lines.append(f"duration {seconds}")
    lines.append(f"file '{frames[-1].resolve()}'")
    concat_file.write_text("\n".join(lines) + "\n")

    out_path = out_dir / "daily-short.mp4"
    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file)]
    if voiceover and voiceover.exists():
        cmd += ["-i", str(voiceover), "-shortest", "-c:a", "aac", "-b:a", "128k"]
    cmd += [
        "-vf",
        "format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v",
        "libx264",
        "-r",
        "30",
        "-movflags",
        "+faststart",
        str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    concat_file.unlink(missing_ok=True)
    if result.returncode != 0:
        log.warning(f"ffmpeg failed: {result.stderr[-500:]}")
        return None
    return out_path
