"""Persistent MLX speech worker.

Run in the isolated .venv-mlx environment. The parent process sends one JSON request
per line on stdin; the worker answers with one JSON response per line on stdout. Audio
is written to a temporary WAV so model/log output can never corrupt the protocol.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import traceback
from typing import Any, Dict, Iterable, Optional, Tuple

import numpy as np
import soundfile as sf

QWEN_CUSTOM_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit"
QWEN_BASE_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit"
CHATTERBOX_MODEL = "mlx-community/chatterbox-multilingual-v3"

LANGUAGE_NAMES = {
    "en": "English",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "de": "German",
    "fr": "French",
    "ru": "Russian",
    "pt": "Portuguese",
    "es": "Spanish",
    "it": "Italian",
}

STYLE_INSTRUCTIONS = {
    "neutral": None,
    "calm": "Speak calmly and gently, with relaxed pacing and restrained emotion.",
    "narrative": "Use an engaging storytelling delivery with clear phrasing and natural emphasis.",
    "serious": "Use a serious, measured, authoritative tone without sounding severe.",
    "warm": "Sound warm, friendly, and conversational, as though speaking to one listener.",
    "excited": "Sound genuinely excited and energetic, with lively but intelligible pacing.",
}

_models: Dict[str, Any] = {}
_protocol = None


def _load_model(engine: str, cloning: bool) -> Any:
    if engine == "qwen3-tts":
        key = "qwen-base" if cloning else "qwen-custom"
        default = QWEN_BASE_MODEL if cloning else QWEN_CUSTOM_MODEL
        variable = "QWEN3_TTS_BASE_MODEL" if cloning else "QWEN3_TTS_MODEL"
    elif engine == "chatterbox":
        key = "chatterbox"
        default = CHATTERBOX_MODEL
        variable = "CHATTERBOX_MLX_MODEL"
    else:
        raise ValueError(f"Unsupported MLX engine: {engine}")

    if key not in _models:
        from mlx_audio.tts.utils import load_model

        model_id = os.environ.get(variable, default)
        print(f"Loading {engine} model: {model_id}", file=sys.stderr, flush=True)
        _models[key] = load_model(model_id)
    return _models[key]


def _language(code: Optional[str]) -> str:
    normalized = (code or "en").strip()
    return LANGUAGE_NAMES.get(normalized, LANGUAGE_NAMES.get(normalized[:2], normalized))


def _generate(request: Dict[str, Any]) -> Tuple[Iterable[Any], Any]:
    engine = request["engine"]
    text = str(request["text"]).strip()
    reference_path = request.get("reference_path")
    model = _load_model(engine, bool(reference_path))
    language = _language(request.get("language"))

    if engine == "qwen3-tts":
        kwargs: Dict[str, Any] = {
            "text": text,
            "lang_code": language,
            "speed": float(request.get("speed", 1.0)),
            "verbose": False,
        }
        if reference_path:
            reference_text = str(request.get("reference_text") or "").strip()
            if not reference_text:
                raise ValueError(
                    "Qwen3-TTS cloning requires the exact transcript of the reference recording."
                )
            # mlx-audio 0.6.7 fingerprints reference audio too weakly for a persistent
            # process. Clear its ICL cache per request so one voice can never inherit
            # another reference's codec tokens, and unbounded entries cannot accumulate.
            icl_cache = getattr(model, "_icl_cache", None)
            if isinstance(icl_cache, dict):
                icl_cache.clear()
            kwargs.update(ref_audio=reference_path, ref_text=reference_text)
        else:
            kwargs.update(
                voice=request.get("voice") or "Ryan",
                instruct=STYLE_INSTRUCTIONS.get(request.get("style") or "neutral"),
            )
        return model.generate(**kwargs), model

    kwargs = {
        "text": text,
        "ref_audio": reference_path,
        "exaggeration": float(request.get("exaggeration", 0.5)),
        "cfg_weight": float(request.get("cfg_weight", 0.5)),
        "lang_code": (request.get("language") or "en").split("-", 1)[0],
        "verbose": False,
    }
    return model.generate(**kwargs), model


def synthesize(request: Dict[str, Any]) -> bytes:
    results, model = _generate(request)
    chunks = []
    sample_rate = int(getattr(model, "sample_rate", 24000))
    for result in results:
        audio = np.asarray(result.audio, dtype=np.float32).reshape(-1)
        if audio.size:
            chunks.append(audio)
        sample_rate = int(getattr(result, "sample_rate", sample_rate))
    if not chunks:
        raise RuntimeError("The MLX engine produced no audio")

    buffer = io.BytesIO()
    sf.write(buffer, np.concatenate(chunks), sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def respond(payload: Dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
    if _protocol is not None:
        _protocol.write(data)
        _protocol.flush()
    else:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


def main() -> int:
    global _protocol
    # Preserve stdout as the protocol channel, then redirect every library/model log
    # (including native and tqdm output) to stderr at the file-descriptor level.
    _protocol = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    if "--check" in sys.argv:
        from mlx_audio.tts.utils import load_model  # noqa: F401

        respond({"ok": True, "detail": "MLX Audio runtime is ready"})
        return 0

    respond({"ok": True, "ready": True})
    for raw_line in sys.stdin.buffer:
        audio_path: Optional[str] = None
        try:
            request = json.loads(raw_line)
            audio = synthesize(request)
            with tempfile.NamedTemporaryFile(prefix="voicevibe-mlx-", suffix=".wav", delete=False) as handle:
                audio_path = handle.name
                handle.write(audio)
            respond({"ok": True, "audio_path": audio_path, "audio_bytes": len(audio)})
        except Exception as error:
            if audio_path:
                try:
                    os.unlink(audio_path)
                except OSError:
                    pass
            respond({"ok": False, "detail": str(error), "traceback": traceback.format_exc()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
