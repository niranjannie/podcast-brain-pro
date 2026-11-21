"""Audio post-processing for exported episodes.

Podcast hosts normalise loudness before accepting an episode. Apple Podcasts asks for
-16 LUFS integrated with a true peak of at most -1 dBTP. Speech synthesised by a local
model lands wherever it lands, so every export goes through the same normalisation pass.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Dict, Optional

TARGET_LUFS = -16.0
TRUE_PEAK = -1.5


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def normalize_loudness(
    audio_bytes: bytes,
    target_lufs: float = TARGET_LUFS,
    true_peak: float = TRUE_PEAK,
    enabled: bool = True,
) -> bytes:
    """Normalise a WAV to the podcast loudness target.

    Returns the original bytes when normalisation is disabled, ffmpeg is missing or the
    pass fails, so a missing ffmpeg never costs the user their episode.
    """
    if not enabled or not audio_bytes or not ffmpeg_available():
        return audio_bytes

    command = [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
        "-f", "wav", "-i", "pipe:0",
        "-af", f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11",
        "-ar", "24000", "-ac", "1",
        "-f", "wav", "pipe:1",
    ]
    try:
        result = subprocess.run(
            command, input=audio_bytes, capture_output=True, timeout=600, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return audio_bytes

    if result.returncode != 0 or not result.stdout:
        return audio_bytes
    return result.stdout


def measure_loudness(audio_bytes: bytes) -> Optional[Dict[str, float]]:
    """Measure integrated loudness and true peak with ffmpeg's ebur128 filter."""
    if not audio_bytes or not ffmpeg_available():
        return None

    command = [
        "ffmpeg", "-hide_banner", "-nostdin",
        "-f", "wav", "-i", "pipe:0",
        "-filter_complex", "ebur128=peak=true",
        "-f", "null", "-",
    ]
    try:
        result = subprocess.run(
            command, input=audio_bytes, capture_output=True, timeout=600, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    summary = result.stderr.decode("utf-8", errors="ignore").rsplit("Summary:", 1)
    if len(summary) < 2:
        return None

    values: Dict[str, float] = {}
    for line in summary[1].splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip().rstrip(" LUFS").rstrip(" dBTP").strip()
        try:
            values[key.strip().lower()] = float(value)
        except ValueError:
            continue

    integrated = values.get("i")
    true_peak = values.get("peak")
    if integrated is None:
        return None
    return {
        "integrated_lufs": integrated,
        "true_peak_db": true_peak if true_peak is not None else 0.0,
        "lra": values.get("lra", 0.0),
    }
