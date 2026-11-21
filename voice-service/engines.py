"""Optional local speech engines, including voice cloning.

VibeVoice stays the default engine. These adapters are optional extras:

- they import lazily, so the app starts without them;
- they report honestly whether they are installed and what they cost in memory;
- a missing engine raises a clear error with the install command, never a fake result.

Nothing in this module runs at import time.
"""

from __future__ import annotations

import importlib.util
import io
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np
from scipy.io import wavfile


class EngineUnavailable(RuntimeError):
    """Raised when an optional engine is not installed on this machine."""

    def __init__(self, engine_id: str, install: str):
        super().__init__(
            f"Engine '{engine_id}' is not installed. Install it with: {install}"
        )
        self.engine_id = engine_id
        self.install = install


@dataclass(frozen=True)
class EngineSpec:
    id: str
    label: str
    license: str
    commercial: bool
    cloning: bool
    languages: str
    download: str
    memory: str
    install: str
    module: str
    notes: str
    wired: bool = True
    default_voices: List[str] = field(default_factory=list)

    def installed(self) -> bool:
        if not self.wired:
            return False
        try:
            return importlib.util.find_spec(self.module) is not None
        except (ImportError, ValueError):
            return False

    def health(self) -> Dict[str, Any]:
        """Report whether the engine can actually run, not just whether it imports.

        A package can be installed and still fail at runtime because one of its own
        dependencies is broken. Chatterbox is the example that matters here: perth,
        its watermarking dependency, needs librosa.resample, which is not importable
        on every Python version.
        """
        if not self.installed():
            return {"ok": False, "detail": f"Not installed. {self.install}"}
        if self.id == "chatterbox":
            try:
                from perth.perth_net import PerthImplicitWatermarker  # noqa: F401
            except ImportError as error:
                return {
                    "ok": False,
                    "detail": (
                        "Installed but broken on this Python: the perth watermarker "
                        f"cannot import librosa.resample ({error}). Use Python 3.10-3.12 "
                        "with the versions chatterbox-tts pins, or install Qwen3-TTS instead."
                    ),
                }
        if self.id == "kokoro":
            import shutil

            if shutil.which("espeak-ng") is None and shutil.which("espeak") is None:
                return {
                    "ok": False,
                    "detail": "Kokoro needs the espeak-ng binary for phonemisation (brew install espeak).",
                }
        return {"ok": True, "detail": "Ready"}

    def describe(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "license": self.license,
            "commercial": self.commercial,
            "cloning": self.cloning,
            "languages": self.languages,
            "download": self.download,
            "memory": self.memory,
            "install": self.install,
            "notes": self.notes,
            "wired": self.wired,
            "installed": self.installed(),
            "health": self.health(),
            "voices": self.default_voices,
        }


ENGINES: Dict[str, EngineSpec] = {
    spec.id: spec
    for spec in [
        EngineSpec(
            id="vibevoice",
            label="VibeVoice 1.5B / Realtime 0.5B",
            license="MIT weights, model card: research use",
            commercial=False,
            cloning=False,
            languages="English and Chinese",
            download="~7.4 GB",
            memory="~6-16 GB",
            install="bundled in vibevoice-src",
            module="vibevoice",
            notes=(
                "The default engine. The TTS inference code was removed from the "
                "upstream repository, so the vendored copy is pinned. The model card "
                "embeds an audible AI disclaimer and a watermark in the output."
            ),
        ),
        EngineSpec(
            id="kokoro",
            label="Kokoro 82M",
            license="Apache-2.0",
            commercial=True,
            cloning=False,
            languages="English, plus Hindi and other language packs",
            download="~300 MB",
            memory="~1 GB, CPU is enough",
            install="pip install kokoro  (needs the espeak-ng binary)",
            module="kokoro",
            notes=(
                "The smallest useful engine: 82M parameters, runs on CPU, good for "
                "drafts and previews. No voice cloning. Hindi voices are graded low "
                "by the upstream model card."
            ),
            default_voices=["af_heart", "af_bella", "am_adam", "am_michael", "bf_emma", "bm_george"],
        ),
        EngineSpec(
            id="chatterbox",
            label="Chatterbox (Resemble AI)",
            license="MIT",
            commercial=True,
            cloning=True,
            languages="English (Turbo), 23 languages (Multilingual)",
            download="~1-2 GB",
            memory="~4-7 GB, runs on MPS or CPU",
            install="pip install chatterbox-tts",
            module="chatterbox",
            notes=(
                "The voice cloning engine: give it 5-10 seconds of clean reference "
                "audio and it speaks new text in that voice. Slower on Apple Silicon "
                "than on a GPU, but it works."
            ),
        ),
        EngineSpec(
            id="qwen3-tts",
            label="Qwen3-TTS 0.6B / 1.7B (MLX)",
            license="Apache-2.0",
            commercial=True,
            cloning=True,
            languages="10 languages, no Indian languages",
            download="~2 GB (0.6B) or ~3 GB (1.7B)",
            memory="~4 GB (0.6B) or ~6-8 GB (1.7B)",
            install="pip install mlx-audio",
            module="mlx_audio",
            notes=(
                "Recommended next step, not wired into the API yet: the fastest "
                "cloning engine on Apple Silicon because it runs on MLX instead of "
                "PyTorch MPS. The 0.6B checkpoint clones noticeably worse than the "
                "1.7B, so use 1.7B if quality matters."
            ),
            wired=False,
        ),
    ]
}


def list_engines() -> List[Dict[str, Any]]:
    """Describe every engine, whether it is installed and what it can do."""
    return [spec.describe() for spec in ENGINES.values()]


def cloning_engines() -> List[Dict[str, Any]]:
    return [engine for engine in list_engines() if engine["cloning"]]


def get_engine(engine_id: str) -> EngineSpec:
    spec = ENGINES.get(engine_id)
    if spec is None:
        raise KeyError(f"Unknown engine '{engine_id}'. Known: {sorted(ENGINES)}")
    return spec


def _require(spec: EngineSpec) -> None:
    if not spec.wired:
        raise EngineUnavailable(spec.id, spec.install)
    if not spec.installed():
        raise EngineUnavailable(spec.id, spec.install)


def _to_wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    """Encode float or int samples as 16-bit PCM WAV."""
    data = np.asarray(samples)
    if data.ndim > 1:
        data = data.reshape(-1)
    if data.dtype.kind == "f":
        data = np.clip(data, -1.0, 1.0)
        data = (data * 32767.0).astype(np.int16)
    elif data.dtype != np.int16:
        data = data.astype(np.int16)
    buffer = io.BytesIO()
    wavfile.write(buffer, sample_rate, data)
    buffer.seek(0)
    return buffer.read()


def _device() -> str:
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


# ============== Adapters ==============

_kokoro_pipelines: Dict[str, Any] = {}
_chatterbox_models: Dict[str, Any] = {}


def _synthesize_kokoro(text: str, voice: str, speed: float) -> bytes:
    spec = ENGINES["kokoro"]
    _require(spec)
    from kokoro import KPipeline

    # 'a' is American English, 'b' British. Other packs use their own language code.
    lang_code = os.environ.get("KOKORO_LANG", "a")
    pipeline = _kokoro_pipelines.get(lang_code)
    if pipeline is None:
        pipeline = KPipeline(lang_code=lang_code)
        _kokoro_pipelines[lang_code] = pipeline

    chosen = voice or spec.default_voices[0]
    chunks: List[np.ndarray] = []
    for _graphemes, _phonemes, audio in pipeline(text, voice=chosen, speed=speed):
        data = audio.cpu().numpy() if hasattr(audio, "cpu") else np.asarray(audio)
        chunks.append(data)

    if not chunks:
        raise RuntimeError("Kokoro produced no audio for that text")
    return _to_wav_bytes(np.concatenate(chunks), 24000)


def _synthesize_chatterbox(
    text: str,
    reference_path: Optional[str],
    exaggeration: float,
    cfg_weight: float,
) -> bytes:
    spec = ENGINES["chatterbox"]
    _require(spec)
    import torch
    from chatterbox.tts import ChatterboxTTS

    device = _device()
    model = _chatterbox_models.get(device)
    if model is None:
        model = ChatterboxTTS.from_pretrained(device=device)
        _chatterbox_models[device] = model

    kwargs: Dict[str, Any] = {
        "exaggeration": exaggeration,
        "cfg_weight": cfg_weight,
    }
    if reference_path:
        kwargs["audio_prompt_path"] = reference_path

    with torch.inference_mode():
        wav = model.generate(text, **kwargs)

    samples = wav.squeeze().cpu().numpy() if hasattr(wav, "cpu") else np.asarray(wav)
    sample_rate = int(getattr(model, "sr", 24000))
    return _to_wav_bytes(samples, sample_rate)


def synthesize(
    engine_id: str,
    text: str,
    voice: Optional[str] = None,
    reference_path: Optional[str] = None,
    speed: float = 1.0,
    exaggeration: float = 0.5,
    cfg_weight: float = 0.5,
) -> bytes:
    """Render text with an optional engine and return WAV bytes.

    ``reference_path`` is the audio to clone from, for engines that support it.
    """
    if not text.strip():
        raise ValueError("text is empty")

    spec = get_engine(engine_id)
    if engine_id == "kokoro":
        return _synthesize_kokoro(text, voice or "", speed)
    if engine_id == "chatterbox":
        return _synthesize_chatterbox(text, reference_path, exaggeration, cfg_weight)
    if engine_id == "vibevoice":
        raise EngineUnavailable(
            "vibevoice",
            "use the /tts/longform or /tts/realtime endpoints for the built-in engine",
        )
    raise EngineUnavailable(spec.id, spec.install)
