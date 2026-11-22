"""Optional local speech engines, including voice cloning.

VibeVoice stays the default engine. These adapters are optional extras:

- they import lazily, so the app starts without them;
- they report honestly whether they are installed and what they cost in memory;
- a missing engine raises a clear error with the install command, never a fake result.

Nothing in this module runs at import time.
"""

from __future__ import annotations

import atexit
import importlib.util
import io
import json
import os
import select
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
from scipy.io import wavfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MLX_WORKER_PATH = os.path.join(BASE_DIR, "mlx_worker.py")
MLX_ENGINES = {"qwen3-tts", "chatterbox"}
MLX_INSTALL = (
    "cd voice-service && python3.12 -m venv .venv-mlx && "
    ".venv-mlx/bin/pip install -r requirements-mlx.txt"
)


def _mlx_python() -> str:
    return os.environ.get(
        "MLX_AUDIO_PYTHON", os.path.join(BASE_DIR, ".venv-mlx", "bin", "python")
    )


def _mlx_runtime_available() -> bool:
    return os.path.isfile(_mlx_python()) and os.access(_mlx_python(), os.X_OK)


def _mlx_runtime_health(_engine_id: str) -> Dict[str, Any]:
    if not _mlx_runtime_available():
        return {"ok": False, "detail": f"Not installed. {MLX_INSTALL}"}
    try:
        result = subprocess.run(
            [_mlx_python(), MLX_WORKER_PATH, "--check"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "detail": f"MLX runtime check failed: {error}"}
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        return {"ok": False, "detail": f"MLX runtime is broken: {detail[-800:]}"}
    return {"ok": True, "detail": "Ready in the isolated MLX runtime"}


class MLXWorker:
    """Serialize requests to one persistent worker; models stay loaded between calls."""

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def _response(self, timeout: int) -> Dict[str, Any]:
        process = self._process
        if process is None or process.stdout is None:
            raise RuntimeError("MLX worker is not running")
        readable, _, _ = select.select([process.stdout], [], [], timeout)
        if not readable:
            raise TimeoutError(f"MLX generation exceeded {timeout} seconds")
        line = process.stdout.readline()
        if not line:
            raise RuntimeError(f"MLX worker exited with status {process.poll()}")
        return json.loads(line)

    def _start(self, engine_id: str) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        if not _mlx_runtime_available():
            raise EngineUnavailable(engine_id, MLX_INSTALL)
        self._process = subprocess.Popen(
            [_mlx_python(), MLX_WORKER_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            cwd=BASE_DIR,
        )
        ready = self._response(30)
        if not ready.get("ok") or not ready.get("ready"):
            raise RuntimeError(ready.get("detail") or "MLX worker failed to start")

    def synthesize(self, request: Dict[str, Any]) -> bytes:
        timeout = int(os.environ.get("MLX_GENERATION_TIMEOUT", "1800"))
        with self._lock:
            audio_path: Optional[str] = None
            try:
                self._start(str(request["engine"]))
                process = self._process
                if process is None or process.stdin is None:
                    raise RuntimeError("MLX worker is not available")
                process.stdin.write(json.dumps(request).encode("utf-8") + b"\n")
                process.stdin.flush()
                response = self._response(timeout)
                if not response.get("ok"):
                    if response.get("traceback"):
                        print(response["traceback"], file=sys.stderr)
                    raise RuntimeError(response.get("detail") or "MLX generation failed")
                audio_path = response["audio_path"]
                if not isinstance(audio_path, str):
                    raise RuntimeError("MLX worker returned an invalid audio path")
                with open(audio_path, "rb") as handle:
                    return handle.read()
            except Exception:
                self.close()
                raise
            finally:
                if audio_path:
                    try:
                        os.unlink(audio_path)
                    except OSError:
                        pass

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.stdin:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                process.terminate()
            except OSError:
                pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


_mlx_worker = MLXWorker()
atexit.register(_mlx_worker.close)


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
        if self.id in MLX_ENGINES:
            return _mlx_runtime_available()
        try:
            return importlib.util.find_spec(self.module) is not None
        except (ImportError, ValueError):
            return False

    def health(self) -> Dict[str, Any]:
        """Report whether the engine can actually run, not just whether it imports."""
        if self.id in MLX_ENGINES:
            return _mlx_runtime_health(self.id)
        if not self.installed():
            return {"ok": False, "detail": f"Not installed. {self.install}"}
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
            label="Chatterbox Multilingual v3 (MLX)",
            license="MIT",
            commercial=True,
            cloning=True,
            languages="23 languages",
            download="~1-2 GB",
            memory="~4-7 GB on Apple Silicon",
            install=MLX_INSTALL,
            module="mlx_audio",
            notes=(
                "Runs in the isolated MLX runtime, avoiding the PyTorch Chatterbox "
                "dependency conflict with VibeVoice. Give it 5-10 seconds of clean "
                "reference audio to clone a voice; delivery uses exaggeration and CFG."
            ),
        ),
        EngineSpec(
            id="qwen3-tts",
            label="Qwen3-TTS 1.7B (MLX)",
            license="Apache-2.0",
            commercial=True,
            cloning=True,
            languages="10 languages, no Indian languages",
            download="~2 GB per 8-bit CustomVoice/Base model",
            memory="~4-6 GB per loaded model on Apple Silicon",
            install=MLX_INSTALL,
            module="mlx_audio",
            notes=(
                "CustomVoice provides nine preset voices and natural-language delivery "
                "control. Base performs voice cloning and requires the exact reference "
                "transcript, so no separate Whisper model is downloaded. Models stay "
                "loaded in the isolated MLX worker between requests."
            ),
            default_voices=[
                "Ryan", "Aiden", "Vivian", "Serena", "Uncle_Fu",
                "Dylan", "Eric", "Ono_Anna", "Sohee",
            ],
        ),
    ]
}


def list_engines() -> List[Dict[str, Any]]:
    """Describe every engine, whether it is installed and what it can do."""
    return [spec.describe() for spec in ENGINES.values()]


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


# ============== Adapters ==============

_kokoro_pipelines: Dict[str, Any] = {}


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


def _synthesize_mlx(
    engine_id: str,
    text: str,
    voice: Optional[str],
    reference_path: Optional[str],
    reference_text: Optional[str],
    speed: float,
    exaggeration: float,
    cfg_weight: float,
    language: str,
    style: str,
) -> bytes:
    spec = get_engine(engine_id)
    _require(spec)
    return _mlx_worker.synthesize({
        "engine": engine_id,
        "text": text,
        "voice": voice,
        "reference_path": reference_path,
        "reference_text": reference_text,
        "speed": speed,
        "exaggeration": exaggeration,
        "cfg_weight": cfg_weight,
        "language": language,
        "style": style,
    })


def synthesize(
    engine_id: str,
    text: str,
    voice: Optional[str] = None,
    reference_path: Optional[str] = None,
    speed: float = 1.0,
    exaggeration: float = 0.5,
    cfg_weight: float = 0.5,
    language: str = "en",
    style: str = "neutral",
    reference_text: Optional[str] = None,
) -> bytes:
    """Render text with an optional engine and return WAV bytes.

    ``reference_path`` and ``reference_text`` describe a consented voice clone.
    """
    if not text.strip():
        raise ValueError("text is empty")

    spec = get_engine(engine_id)
    if engine_id == "kokoro":
        return _synthesize_kokoro(text, voice or "", speed)
    if engine_id in MLX_ENGINES:
        return _synthesize_mlx(
            engine_id, text, voice, reference_path, reference_text,
            speed, exaggeration, cfg_weight, language, style,
        )
    if engine_id == "vibevoice":
        raise EngineUnavailable(
            "vibevoice",
            "use the /tts/longform or /tts/realtime endpoints for the built-in engine",
        )
    raise EngineUnavailable(spec.id, spec.install)
