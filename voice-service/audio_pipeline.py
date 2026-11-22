"""Audio post-processing for exported episodes.

Podcast hosts normalise loudness before accepting an episode. Apple Podcasts asks for
-16 LUFS integrated with a true peak of at most -1 dBTP. Speech synthesised by a local
model lands wherever it lands, so every export goes through the same normalisation pass.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional

import numpy as np
from scipy.io import wavfile

TARGET_LUFS = -16.0
TRUE_PEAK = -1.5


def wav_duration_seconds(audio_bytes: bytes) -> float:
    """Read duration from the actual WAV frames, not a word-count estimate."""
    rate, data = wavfile.read(io.BytesIO(audio_bytes))
    return float(len(data)) / float(rate)


def _as_pcm16(data: np.ndarray) -> np.ndarray:
    if data.dtype == np.int16:
        return data
    if data.dtype == np.uint8:
        return ((data.astype(np.int16) - 128) * 256).astype(np.int16)
    if np.issubdtype(data.dtype, np.integer):
        limits = np.iinfo(data.dtype)
        scale = float(max(abs(limits.min), limits.max))
        return np.round(data.astype(np.float64) * (32767.0 / scale)).astype(np.int16)
    return (np.clip(data, -1.0, 1.0) * 32767.0).astype(np.int16)


def stitch_wav_bytes(
    chunks: List[bytes], silence_ms: int = 300, gaps_ms: Optional[List[int]] = None
) -> bytes:
    """Join PCM WAVs with real silence and a correctly sized, seekable RIFF header."""
    if not chunks:
        return b""
    if len(chunks) == 1:
        return chunks[0]

    sample_rate: Optional[int] = None
    channel_shape: Optional[tuple] = None
    segments: List[np.ndarray] = []
    for chunk in chunks:
        rate, data = wavfile.read(io.BytesIO(chunk))
        if sample_rate is None:
            sample_rate = rate
        elif rate != sample_rate:
            raise ValueError("Cannot stitch WAVs with different sample rates")
        data = _as_pcm16(data)
        shape = () if data.ndim == 1 else data.shape[1:]
        if channel_shape is None:
            channel_shape = shape
        elif shape != channel_shape:
            raise ValueError("Cannot stitch WAVs with different channel layouts")
        segments.append(data)

    if sample_rate is None:
        raise ValueError("No readable WAV segments")

    pieces = [segments[0]]
    for index, segment in enumerate(segments[1:]):
        gap = gaps_ms[index] if gaps_ms and index < len(gaps_ms) else silence_ms
        if gap > 0:
            frames = int(round(sample_rate * gap / 1000))
            silence_shape = (frames,) + segment.shape[1:]
            pieces.append(np.zeros(silence_shape, dtype=np.int16))
        pieces.append(segment)

    buffer = io.BytesIO()
    wavfile.write(buffer, sample_rate, np.concatenate(pieces))
    return buffer.getvalue()


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

    output_path: Optional[str] = None
    try:
        output = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = output.name
        output.close()
        command = [
            "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
            "-f", "wav", "-i", "pipe:0",
            "-af", f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11",
            "-ar", "24000", "-ac", "1",
            "-f", "wav", output_path,
        ]
        result = subprocess.run(
            command, input=audio_bytes, capture_output=True, timeout=600, check=False
        )
        if result.returncode != 0 or not os.path.getsize(output_path):
            return audio_bytes
        with open(output_path, "rb") as handle:
            return handle.read()
    except (OSError, subprocess.SubprocessError):
        return audio_bytes
    finally:
        if output_path:
            try:
                os.unlink(output_path)
            except OSError:
                pass


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

    # Parse with an explicit unit group. String rstrip() removes characters, not a
    # suffix, so "-1.5 dBFS" lost its unit and the peak was silently dropped.
    pattern = re.compile(r"([A-Za-z ]+):\s*(-?[0-9]+(?:\.[0-9]+)?)\s*(LUFS|dBFS|dBTP|LU)?")
    values: Dict[str, float] = {}
    for key, number, _unit in pattern.findall(summary[1]):
        try:
            values[key.strip().lower()] = float(number)
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
