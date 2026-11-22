"""
AI_VOICEVIBE Voice Service
FastAPI wrapper for Microsoft VibeVoice models on Apple Silicon / M4 Mac
Uses the official vibevoice package APIs (not the broken transformers pipeline)
"""

import os
import io
import copy
import time
import random
import tempfile
import traceback
import re
import threading
import base64
import json
import logging
import logging.handlers
import uuid
import asyncio
import gc
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

# ============== Logging Setup ==============
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Main application log (rotating, 10MB per file, 5 backups)
app_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOGS_DIR, "app.log"),
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
)
app_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

# Dedicated audio generation log (rotating, 20MB per file, 10 backups)
audio_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOGS_DIR, "audio_generation.log"),
    maxBytes=20 * 1024 * 1024,
    backupCount=10,
)
audio_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | [req:%(request_id)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

# Console handler for visibility during dev
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
))

# Configure loggers (guard against duplicate handlers on reload)
if not logging.getLogger("voice_service").handlers:
    logging.basicConfig(level=logging.INFO, handlers=[app_handler, console_handler])
logger = logging.getLogger("voice_service")
logger.setLevel(logging.INFO)

audio_logger = logging.getLogger("audio_generation")
audio_logger.setLevel(logging.DEBUG)
if not audio_logger.handlers:
    audio_logger.addHandler(audio_handler)
    audio_logger.addHandler(console_handler)

# Filter to inject request_id into log records
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "request_id") or getattr(record, "request_id", "-") == "-":
            record.request_id = request_id_var.get("-")
        return True

if not any(isinstance(f, RequestIdFilter) for f in audio_logger.filters):
    audio_logger.addFilter(RequestIdFilter())
if not any(isinstance(f, RequestIdFilter) for f in logger.filters):
    logger.addFilter(RequestIdFilter())

try:
    import psutil
except Exception:
    psutil = None

import torch
import requests
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pydub import AudioSegment
from scipy.io import wavfile

# Shared script contract: turn keys, delivery directives, chunking, voice resolution.
from audio_pipeline import measure_loudness, normalize_loudness, stitch_wav_bytes, wav_duration_seconds
from content_pipeline import generate_content_extras, with_chapter_timing
from engines import EngineUnavailable, get_engine, list_engines, synthesize
from script_pipeline import (
    DEFAULT_STYLE,
    build_units,
    chunk_units_for_engine,
    group_units,
    list_voices,
    normalize_turns,
    plan_generation,
    resolve_voices,
    segment_gap_seconds,
    speaker_order,
    split_sentences,
    split_monologue_turns,
    split_units,
    style_cfg_multiplier,
    style_names,
    style_params,
    turn_content,
    turn_speaker,
    units_to_script_lines,
    voice_paths_by_id,
)

# ============== VibeVoice imports ==============
from vibevoice.modular.modeling_vibevoice_streaming_inference import VibeVoiceStreamingForConditionalGenerationInference
from vibevoice.processor.vibevoice_streaming_processor import VibeVoiceStreamingProcessor
from vibevoice.modular.modeling_vibevoice_inference import VibeVoiceForConditionalGenerationInference
from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor
from vibevoice.modular.modeling_vibevoice_asr import VibeVoiceASRForConditionalGeneration
from vibevoice.processor.vibevoice_asr_processor import VibeVoiceASRProcessor

# ============== Thread pool for blocking TTS generation ==============
# Prevents the asyncio event loop from being blocked during long model.generate() calls.
# This fixes the "socket hang up" errors seen in frontend logs.
_tts_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tts_worker")

# ============== Generation lock for stateful scheduler ==============
# DPMSolverMultistepScheduler tracks step_index as mutable state on the model.
# Without this lock, concurrent longform requests race on the scheduler and crash
# with "index N is out of bounds for dimension 0 with size N".
_tts_generation_lock = threading.Lock()

# ============== Periodic MPS memory cleaner ==============
_mps_clear_active = threading.Event()
_mps_clear_thread: Optional[threading.Thread] = None

_mps_clear_stop = threading.Event()

def _periodic_mps_cache_clear(interval_sec: int = 45):
    """Clear the MPS cache every N seconds while a generation is running.

    Waiting on the *active* event used to return immediately, so the thread exited on
    its first iteration and the cache was never cleared on a timer.
    """
    while _mps_clear_active.is_set() and not _mps_clear_stop.is_set():
        if _mps_clear_stop.wait(timeout=interval_sec):
            break
        if DEVICE == "mps" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            try:
                torch.mps.empty_cache()
            except Exception:
                pass

def start_mps_cache_clear():
    """Start the periodic MPS cache cleaner."""
    global _mps_clear_thread
    if DEVICE != "mps":
        return
    if _mps_clear_thread is not None and _mps_clear_thread.is_alive():
        return
    _mps_clear_stop.clear()
    _mps_clear_active.set()
    _mps_clear_thread = threading.Thread(target=_periodic_mps_cache_clear, daemon=True)
    _mps_clear_thread.start()

def stop_mps_cache_clear():
    """Stop the periodic MPS cache cleaner and let its thread exit."""
    _mps_clear_active.clear()
    _mps_clear_stop.set()

# ============== Model cache detection ==============
HF_HUB_CACHE = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
if os.environ.get("HF_HOME"):
    HF_HUB_CACHE = os.path.join(os.environ["HF_HOME"], "hub")

def is_model_cached(model_name: str) -> bool:
    """Check if a HuggingFace model has been downloaded to local cache."""
    cache_dir = os.path.join(HF_HUB_CACHE, f"models--{model_name.replace('/', '--')}")
    if not os.path.isdir(cache_dir):
        return False
    # Look for snapshot directory with actual model files
    snapshots_dir = os.path.join(cache_dir, "snapshots")
    if not os.path.isdir(snapshots_dir):
        return False
    for snapshot in os.listdir(snapshots_dir):
        snapshot_path = os.path.join(snapshots_dir, snapshot)
        if os.path.isdir(snapshot_path):
            # Check for model weights (safetensors or bin)
            files = os.listdir(snapshot_path)
            if any(f.endswith(('.safetensors', '.bin')) for f in files):
                return True
    return False

def get_cache_size(model_name: str) -> int:
    """Return cached model size in bytes."""
    cache_dir = os.path.join(HF_HUB_CACHE, f"models--{model_name.replace('/', '--')}")
    if not os.path.isdir(cache_dir):
        return 0
    total = 0
    for dirpath, dirnames, filenames in os.walk(cache_dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total

# Global model holders (lazy loaded)
models = {}

# Loading locks to prevent double-loading
_longform_load_lock = threading.Lock()
_realtime_load_lock = threading.Lock()
_asr_load_lock = threading.Lock()

# ASR readiness flag
asr_ready = threading.Event()
ASR_PRELOAD_AT_STARTUP = os.environ.get("ASR_PRELOAD_AT_STARTUP", "false").lower() in ("true", "1", "yes")

# Longform TTS readiness flag
longform_ready = threading.Event()
LONGFORM_PRELOAD_AT_STARTUP = os.environ.get("LONGFORM_PRELOAD_AT_STARTUP", "false").lower() in ("true", "1", "yes")

# Detect best device for M4 Mac
def get_device():
    if torch.backends.mps.is_available():
        print("🍎 Using Apple Silicon MPS acceleration")
        return "mps"
    print("🖥️  Using CPU fallback")
    return "cpu"

DEVICE = get_device()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Read voice-service/.env before any environment-derived constant below. The setup
# guide tells users to put their keys in that file; without this it was ignored.
from env_loader import load_env_file

load_env_file(os.path.join(BASE_DIR, ".env"))

CONFIG_PATH = os.path.join(BASE_DIR, "user_config.json")

# Configurable paths (env vars override defaults)
VOICES_DIR = os.environ.get(
    "VOICES_DIR",
    os.path.join(BASE_DIR, "..", "vibevoice-src", "demo", "voices", "streaming_model")
)
LONGFORM_VOICES_DIR = os.environ.get(
    "LONGFORM_VOICES_DIR",
    os.path.join(BASE_DIR, "..", "vibevoice-src", "demo", "voices")
)
OUTPUT_DIR = os.environ.get(
    "OUTPUT_DIR",
    os.path.join(BASE_DIR, "outputs")
)

# ============== Request ID helper ==============
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

def get_request_id() -> str:
    return request_id_var.get()

def log_audio_event(level: str, message: str, extra: Optional[Dict[str, Any]] = None, req_id: Optional[str] = None):
    """Log an audio generation event with request ID correlation."""
    req_id = req_id or get_request_id()
    extra = extra or {}
    extra_str = " | ".join(f"{k}={v}" for k, v in extra.items())
    full_msg = message
    if extra_str:
        full_msg += f" | {extra_str}"
    
    if level == "error":
        audio_logger.error(full_msg)
    elif level == "warning":
        audio_logger.warning(full_msg)
    elif level == "debug":
        audio_logger.debug(full_msg)
    else:
        audio_logger.info(full_msg)

# ============== User Config (API Keys) ==============

_config_cache: Dict[str, Any] = {"mtime": None, "data": {}}

def get_config() -> Dict[str, str]:
    """Read user_config.json, cached on the file's modification time.

    A parse failure is logged, not swallowed: silently returning {} is how a truncated
    file used to make every provider look unconfigured.
    """
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
    except OSError:
        _config_cache["mtime"] = None
        _config_cache["data"] = {}
        return {}

    if _config_cache["mtime"] == mtime:
        return dict(_config_cache["data"])

    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Could not parse %s: %s", CONFIG_PATH, e)
        return {}

    if not isinstance(data, dict):
        logger.error("%s does not contain a JSON object", CONFIG_PATH)
        return {}

    _config_cache["mtime"] = mtime
    _config_cache["data"] = data
    return dict(data)

def write_config(cfg: Dict[str, str]) -> None:
    """Write the key file atomically, readable only by this user."""
    tmp_path = CONFIG_PATH + ".tmp"
    descriptor = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(cfg, handle, indent=2)
    os.replace(tmp_path, CONFIG_PATH)
    _config_cache["mtime"] = None  # force a re-read

def get_api_key(name: str) -> str:
    """Read API key from environment first, then user config file."""
    env_val = os.environ.get(name, "")
    if env_val:
        return str(env_val)
    val = get_config().get(name, "")
    return str(val) if val is not None else ""

def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "..." + key[-4:]

# ============== Duration Config ==============
DURATION_CONFIG = {
    2: {"words": 300, "max_tokens": 800, "chapters": None, "label": "2 min"},
    5: {"words": 750, "max_tokens": 1500, "chapters": None, "label": "5 min"},
    10: {"words": 1500, "max_tokens": 2500, "chapters": None, "label": "10 min"},
    15: {"words": 2250, "max_tokens": 3500, "chapters": 4, "label": "15 min"},
    30: {"words": 4500, "max_tokens": 5500, "chapters": 6, "label": "30 min"},
}

# ============== Pydantic Models ==============

class TTSRealtimeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    speaker_name: Optional[str] = "Carter"
    cfg_scale: Optional[float] = 1.5
    save_to_disk: Optional[bool] = False
    topic: Optional[str] = None
    format: Optional[str] = "monologue"
    language: Optional[str] = "en"
    duration_minutes: Optional[int] = None
    style: Optional[str] = None  # episode wide delivery style, directives can override
    extras: Optional[Dict[str, Any]] = None

class TTSLongformRequest(BaseModel):
    script: List[Dict[str, Any]] = Field(..., min_length=1)  # [{"speaker": "Host", "content": "Hello"}]
    voice_names: Optional[List[str]] = None
    engine: str = "vibevoice"
    cfg_scale: Optional[float] = 1.3
    save_to_disk: Optional[bool] = True
    topic: Optional[str] = None
    format: Optional[str] = "interview"
    language: Optional[str] = "en"
    duration_minutes: Optional[int] = None
    style: Optional[str] = None  # episode wide delivery style, directives can override
    extras: Optional[Dict[str, Any]] = None

LANGUAGE_MAP = {
    "en": "English",
    "hi-IN": "Hindi",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
    "kn-IN": "Kannada",
    "bn-IN": "Bengali",
    "mr-IN": "Marathi",
    "gu-IN": "Gujarati",
    "ml-IN": "Malayalam",
    "pa-IN": "Punjabi",
    "od-IN": "Odia",
}

# Sarvam uses ISO 639-1 language codes, the app uses ISO 639-3 for a few languages.
SARVAM_LANGUAGE_CODES = {
    "od-IN": "or-IN",
}
SARVAM_DEFAULT_VOICES = ["shubh", "shreya", "manan"]

class PodcastGenerateRequest(BaseModel):
    topic: str
    duration_minutes: int = Field(default=2, ge=2, le=30)
    format: str = Field(default="monologue", pattern="^(monologue|interview|panel)$")
    speakers: Optional[List[str]] = Field(default=None, max_length=3)
    language: str = Field(default="en", pattern="^(en|hi-IN|ta-IN|te-IN|kn-IN|bn-IN|mr-IN|gu-IN|ml-IN|pa-IN|od-IN)$")
    style: Optional[str] = Field(default=None, pattern="^(neutral|calm|narrative|serious|warm|excited)$")
    include_extras: bool = False

class PodcastScriptResponse(BaseModel):
    topic: str
    duration_minutes: int
    format: str
    script: List[Dict[str, str]]
    word_count: int
    generation_time_seconds: float
    target_words: Optional[int] = None
    under_target: Optional[bool] = None
    extras: Optional[Dict[str, Any]] = None
    extras_error: Optional[str] = None

class ContentExtrasRequest(BaseModel):
    topic: str
    script: List[Dict[str, Any]] = Field(..., min_length=1)
    duration_minutes: int = Field(default=2, ge=2, le=30)
    format: str = Field(default="monologue", pattern="^(monologue|interview|panel)$")
    language: str = "en"

class SarvamTTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    target_language_code: str = Field(default="en-IN", pattern="^[a-z]{2}-[A-Z]{2}$")
    speaker: str = Field(default="shubh")
    pace: float = Field(default=1.0, ge=0.5, le=2.0)
    temperature: float = Field(default=0.6, ge=0.01, le=1.0)
    model: str = Field(default="bulbul:v3", pattern="^(bulbul:v4-flash|bulbul:v3|bulbul:v2)$")
    output_audio_codec: str = Field(default="wav", pattern="^(wav|mp3|aac|opus|flac|pcm|mulaw|alaw)$")
    save_to_disk: Optional[bool] = False
    topic: Optional[str] = None
    format: Optional[str] = "monologue"
    language: Optional[str] = "en"
    duration_minutes: Optional[int] = None
    pitch: Optional[float] = Field(default=None, ge=-0.5, le=0.5)
    loudness: Optional[float] = Field(default=None, ge=0.1, le=2.5)
    dict_id: Optional[str] = None  # Sarvam pronunciation dictionary id
    extras: Optional[Dict[str, Any]] = None
    script: Optional[List[Dict[str, Any]]] = None
    voice_names: Optional[List[str]] = None
    style: Optional[str] = Field(default=None, pattern="^(neutral|calm|narrative|serious|warm|excited)$")

# ============== Model Loaders ==============

def load_realtime_tts():
    if "realtime_tts" in models:
        return models["realtime_tts"]
    with _realtime_load_lock:
        if "realtime_tts" in models:
            return models["realtime_tts"]
        print("⬇️  Loading VibeVoice-Realtime-0.5B (~2GB)...")
        processor = VibeVoiceStreamingProcessor.from_pretrained("microsoft/VibeVoice-Realtime-0.5B")
        
        if DEVICE == "mps":
            model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                "microsoft/VibeVoice-Realtime-0.5B",
                torch_dtype=torch.float32,
                attn_implementation="sdpa",
                device_map=None,
            )
            model.to("mps")
        else:
            model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                "microsoft/VibeVoice-Realtime-0.5B",
                torch_dtype=torch.float32,
                device_map="cpu",
                attn_implementation="sdpa",
            )
        
        model.eval()
        model.set_ddpm_inference_steps(num_steps=5)
        
        models["realtime_tts"] = (processor, model)
        print("✅ Realtime TTS loaded!")
    return models["realtime_tts"]

def _do_load_longform_tts():
    """Actual loading logic (always runs under lock)."""
    with _longform_load_lock:
        if "longform_tts" in models:
            return models["longform_tts"]
        
        print("⬇️  Loading VibeVoice-TTS-1.5B (~5.4GB)... This may take 2-3 minutes.")
        processor = VibeVoiceProcessor.from_pretrained("microsoft/VibeVoice-1.5B")
        
        if DEVICE == "mps":
            # Use float16 on MPS to save ~50% memory (float32 causes swap thrashing on 24GB)
            dtype = torch.float16 if torch.backends.mps.is_available() else torch.float32
            model = VibeVoiceForConditionalGenerationInference.from_pretrained(
                "microsoft/VibeVoice-1.5B",
                torch_dtype=dtype,
                attn_implementation="sdpa",
                device_map=None,
            )
            model.to("mps")
        else:
            model = VibeVoiceForConditionalGenerationInference.from_pretrained(
                "microsoft/VibeVoice-1.5B",
                torch_dtype=torch.float32,
                device_map="cpu",
                attn_implementation="sdpa",
            )
        
        model.eval()
        # Allow overriding DDPM steps via env var. Lower = faster + less memory.
        # Default dropped from 10 → 5 for 24GB Macs. Quality is still good.
        ddpm_steps = int(os.environ.get("LONGFORM_DDPM_STEPS", "5"))
        model.set_ddpm_inference_steps(num_steps=ddpm_steps)
        models["longform_tts"] = (processor, model)
        print(f"✅ Longform TTS loaded! (DDPM steps={ddpm_steps})")
        return models["longform_tts"]

def load_longform_tts():
    if "longform_tts" in models:
        return models["longform_tts"]
    
    # If preloading was started, wait for it instead of loading again
    if LONGFORM_PRELOAD_AT_STARTUP and not longform_ready.is_set():
        print("⏳ Longform TTS preloading in progress — waiting...")
        longform_ready.wait(timeout=900)  # 15 min max
        if "longform_tts" in models:
            return models["longform_tts"]
        print("⚠️ Preloading seems to have failed — loading manually...")
    
    return _do_load_longform_tts()

def load_asr():
    if "asr" in models:
        asr_ready.set()
        return models["asr"]
    with _asr_load_lock:
        if "asr" in models:
            asr_ready.set()
            return models["asr"]
        print("⬇️  Loading VibeVoice-ASR (~14-16GB)... This may take 3-5 minutes.")
        processor = VibeVoiceASRProcessor.from_pretrained(
            "microsoft/VibeVoice-ASR",
            language_model_pretrained_name="Qwen/Qwen2.5-7B"
        )
        
        dtype = torch.float32 if DEVICE in ("mps", "cpu") else torch.bfloat16
        model = VibeVoiceASRForConditionalGeneration.from_pretrained(
            "microsoft/VibeVoice-ASR",
            dtype=dtype,
            device_map="auto" if DEVICE == "mps" else None,
            attn_implementation="sdpa",
            trust_remote_code=True
        )
        if DEVICE != "auto":
            model = model.to(DEVICE)
        
        model.eval()
        models["asr"] = (processor, model)
        print("✅ ASR loaded!")
    asr_ready.set()
    return models["asr"]

def _preload_asr_worker():
    try:
        load_asr()
    except Exception:
        traceback.print_exc()

def _preload_longform_worker():
    try:
        _do_load_longform_tts()
        longform_ready.set()
        print("✅ Longform TTS preloaded and ready!")
    except Exception:
        traceback.print_exc()
        print("❌ Longform TTS preloading failed — will retry on first request")

# ============== RSS ==============
from rss_generator import generate_podcast_rss

# ============== Helpers ==============

LOUDNESS_NORMALIZATION = os.environ.get("NORMALIZE_LOUDNESS", "true").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)

# Expand a script that came out far short of the target length with a second pass.
EXPAND_SHORT_SCRIPTS = os.environ.get("EXPAND_SHORT_SCRIPTS", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

def _finalize_audio(audio_bytes: bytes, metadata: Optional[Dict[str, Any]] = None) -> bytes:
    """Normalise loudness for podcast delivery and record the measurement.

    Every export goes through here, so the file on disk and the audio the browser
    plays are always the same normalised audio.
    """
    normalized = normalize_loudness(audio_bytes, enabled=LOUDNESS_NORMALIZATION)
    if metadata is not None:
        extras = metadata.get("extras")
        if isinstance(extras, dict):
            metadata.setdefault("title", extras.get("title"))
            metadata.setdefault("description", extras.get("description"))
        # Record whether the export was really normalised: a missing ffmpeg used to
        # pass silently and publish whatever level the model produced.
        metadata["loudness_normalised"] = normalized is not audio_bytes
        measurement = measure_loudness(normalized)
        if measurement:
            metadata["loudness"] = measurement
    return normalized

def _save_transcript_sidecar(
    saved_filename: str,
    script: List[Dict[str, Any]],
    metadata: Dict[str, Any],
) -> Optional[str]:
    """Write the episode transcript next to the audio for the RSS feed.

    Podcasting 2.0 hosts can show the transcript, and the file is also a plain text
    transcript for anything else that wants the words of the episode.
    """
    if not saved_filename:
        return None
    try:
        # save_to_outputs returns a bare filename, so anchor it in OUTPUT_DIR. Writing
        # it relative to the process working directory is what put the transcript in
        # voice-service/ and left the RSS feed without a transcript element.
        audio_path = saved_filename
        if not os.path.isabs(audio_path):
            audio_path = os.path.join(OUTPUT_DIR, saved_filename)
        base = os.path.splitext(audio_path)[0]
        path = f"{base}.transcript.json"
        payload = {
            "title": metadata.get("title") or metadata.get("topic") or os.path.basename(base),
            "topic": metadata.get("topic"),
            "language": metadata.get("language"),
            "format": metadata.get("format"),
            "duration_minutes": metadata.get("duration_minutes"),
            "duration_seconds": metadata.get("duration_seconds"),
            "engine": metadata.get("engine"),
            "voice_names": metadata.get("voice_names") or [],
            "speaker_name": metadata.get("speaker_name"),
            "extras": metadata.get("extras"),
            "script": [
                {
                    "speaker": turn_speaker(item),
                    "content": turn_content(item),
                }
                for item in normalize_turns(script)
            ],
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

        extras = metadata.get("extras")
        chapters = extras.get("chapters") if isinstance(extras, dict) else None
        if chapters and all(
            isinstance(chapter, dict) and isinstance(chapter.get("startTime"), (int, float))
            for chapter in chapters
        ):
            chapter_payload = {
                "version": "1.2.0",
                "chapters": [
                    {
                        "startTime": round(float(chapter["startTime"]), 3),
                        "title": chapter["title"],
                    }
                    for chapter in chapters
                ],
            }
            with open(f"{base}.chapters.json", "w", encoding="utf-8") as handle:
                json.dump(chapter_payload, handle, indent=2, ensure_ascii=False)
        return path
    except Exception as e:
        logger.warning("Could not write transcript sidecar: %s", e)
        return None

def save_to_outputs(audio_bytes: bytes, prefix: str = "podcast", metadata: Optional[Dict[str, Any]] = None, subdirectory: str = "") -> str:
    """Save audio bytes to the outputs directory with a timestamp.

    ``subdirectory`` keeps one-shot previews out of the episode library and the RSS
    feed: those scan only the top level of the outputs directory.
    """
    target_dir = os.path.join(OUTPUT_DIR, subdirectory) if subdirectory else OUTPUT_DIR
    os.makedirs(target_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
    topic = ""
    if metadata:
        raw_topic = metadata.get("topic", "")
        if isinstance(raw_topic, str):
            topic = raw_topic.strip()
    if topic:
        # Sanitize for filesystem: lowercase, replace non-alphanumerics with underscore,
        # collapse multiple underscores, strip leading/trailing underscores.
        safe_topic = re.sub(r"[^a-zA-Z0-9]", "_", topic)
        safe_topic = re.sub(r"_+", "_", safe_topic).strip("_")
        # Cap length to avoid extremely long filenames
        safe_topic = safe_topic[:80]
        filename = f"podcast_{safe_topic}_{timestamp}.wav"
    else:
        filename = f"{prefix}_{timestamp}.wav"
    path = os.path.join(target_dir, filename)
    with open(path, "wb") as f:
        f.write(audio_bytes)

    # Duration comes from the WAV that was actually written. If the header cannot be
    # parsed, estimate from the byte count (24 kHz mono 16-bit = 48000 B/s) and say so
    # in the log rather than silently recording 0.0.
    duration_seconds = 0.0
    try:
        with io.BytesIO(audio_bytes) as bio:
            rate, data = wavfile.read(bio)
            duration_seconds = float(len(data)) / float(rate)
    except Exception as e:
        duration_seconds = len(audio_bytes) / 48000.0
        logger.warning("Could not read the WAV header for %s (%s); estimated duration", filename, e)

    if metadata:
        metadata["duration_seconds"] = round(duration_seconds, 2)
        meta_path = os.path.splitext(path)[0] + ".json"
        meta_payload = {
            "created_at": datetime.now().isoformat(),
            # A stable identity for the RSS guid: renaming the file must not make a
            # podcast client treat the episode as new.
            "episode_id": metadata.get("episode_id") or str(uuid.uuid4()),
            "duration_seconds": round(duration_seconds, 2),
            **metadata,
        }
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_payload, f, indent=2)
        except Exception as e:
            print(f"Failed to write metadata: {e}")

    return os.path.join(subdirectory, filename) if subdirectory else filename

def tavily_research(topic: str) -> str:
    """Get deep research summary from Tavily."""
    tavily_key = get_api_key("TAVILY_API_KEY")
    if not tavily_key:
        return ""
    
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": tavily_key,
                "query": topic,
                "search_depth": "advanced",
                "include_answer": "advanced",
                "max_results": 8,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        
        answer = data.get("answer", "")
        results = data.get("results", [])
        snippets = [f"- {r.get('content', '')}" for r in results[:5]]
        
        return f"{answer}\n\nKey sources:\n" + "\n".join(snippets)
    except Exception as e:
        print(f"Tavily research failed: {e}")
        return ""

def _model_id(env_key: str, default: str) -> str:
    """Model id for a provider, overridable by environment variable.

    Providers retire model ids regularly, so every id lives here and can be changed
    without touching code.
    """
    return os.environ.get(env_key, default).strip() or default


def groq_chat(messages: List[Dict[str, str]], max_tokens: int = 600, temperature: float = 0.7) -> str:
    """Call Groq API with fast capped retry so fallback happens quickly."""
    groq_key = get_api_key("GROQ_API_KEY")
    if not groq_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured on server")

    last_exception = None
    for attempt in range(2):
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _model_id("GROQ_MODEL", "openai/gpt-oss-120b"),
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=25,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            last_exception = e
            status = getattr(getattr(e, "response", None), "status_code", 0)
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                wait = min(2 ** attempt, 5) + random.uniform(0, 1)
                print(f"Groq connection issue, retrying in {wait:.1f}s... (attempt {attempt+1}/2)")
                time.sleep(wait)
                continue
            if status == 429:
                # Fail immediately on rate limit so fallback happens fast
                print(f"Groq rate limited ({status}), failing fast to fallback.")
                raise HTTPException(status_code=429, detail=f"Groq API rate-limited: {last_exception}")
            if status in (503, 502, 500):
                wait = min(2 ** attempt, 5) + random.uniform(0, 1)
                print(f"Groq server error ({status}), retrying in {wait:.1f}s... (attempt {attempt+1}/2)")
                time.sleep(wait)
                continue
            raise
    # Report the real failure class: a 5xx after retries is not a rate limit.
    final_status = getattr(getattr(last_exception, "response", None), "status_code", 0)
    if final_status == 429:
        raise HTTPException(status_code=429, detail=f"Groq API rate-limited after retries: {last_exception}")
    raise HTTPException(status_code=503, detail=f"Groq API unavailable after retries: {last_exception}")

def deepseek_chat(messages: List[Dict[str, str]], max_tokens: int = 600, temperature: float = 0.7) -> str:
    """Call DeepSeek API (OpenAI-compatible)."""
    api_key = get_api_key("DEEPSEEK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="DEEPSEEK_API_KEY not configured")
    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": _model_id("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=25,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def gemini_chat(messages: List[Dict[str, str]], max_tokens: int = 600, temperature: float = 0.7) -> str:
    """Call Google Gemini as fallback (OpenAI-compatible endpoint)."""
    api_key = get_api_key("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY not configured")
    resp = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": _model_id("GEMINI_MODEL", "gemini-2.5-flash"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=25,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def mistral_chat(messages: List[Dict[str, str]], max_tokens: int = 600, temperature: float = 0.7) -> str:
    """Call Mistral AI API."""
    api_key = get_api_key("MISTRAL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="MISTRAL_API_KEY not configured")
    resp = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": _model_id("MISTRAL_MODEL", "mistral-small-latest"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=25,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def together_chat(messages: List[Dict[str, str]], max_tokens: int = 600, temperature: float = 0.7) -> str:
    """Call Together AI API."""
    api_key = get_api_key("TOGETHER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="TOGETHER_API_KEY not configured")
    resp = requests.post(
        "https://api.together.xyz/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": _model_id("TOGETHER_MODEL", "together_ai/deepseek-ai/DeepSeek-V4.1-Flash-1017"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=25,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def ollama_chat(messages: List[Dict[str, str]], max_tokens: int = 600, temperature: float = 0.7) -> str:
    """Call local Ollama server (OpenAI-compatible endpoint)."""
    model = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
    base = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
    try:
        resp = requests.post(
            f"{base}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise HTTPException(status_code=503, detail=f"Ollama not reachable at {base}")
    except Exception as e:
        print(f"[ollama debug] Unexpected error: {type(e).__name__}: {e}")
        raise

_openrouter_free_model: Optional[str] = None

def _openrouter_model() -> str:
    """Pick a free OpenRouter model that is routable right now.

    Free model ids churn constantly, so the catalogue is read at runtime instead of
    hard coding an id that silently stops working.
    """
    override = os.environ.get("OPENROUTER_MODEL", "").strip()
    if override:
        return override

    global _openrouter_free_model
    if _openrouter_free_model:
        return _openrouter_free_model

    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=15)
        resp.raise_for_status()
        free = [m.get("id", "") for m in resp.json().get("data", [])]
        free = [model_id for model_id in free if model_id.endswith(":free")]
    except Exception as e:
        print(f"[openrouter] free model lookup failed: {e}")
        free = []

    if not free:
        raise HTTPException(
            status_code=503,
            detail="No free OpenRouter model is available right now. Set OPENROUTER_MODEL to a model id.",
        )

    # Prefer the families that write scripts well, then fall back to alphabetical order.
    preferred = [
        model_id
        for model_id in free
        if any(tag in model_id for tag in ("gpt-oss", "llama-3.3", "qwen3"))
    ]
    chosen = sorted(preferred or free)[0]
    _openrouter_free_model = chosen
    print(f"[openrouter] using free model {chosen}")
    return chosen

def openrouter_chat(messages: List[Dict[str, str]], max_tokens: int = 600, temperature: float = 0.7) -> str:
    """Call OpenRouter as final fallback."""
    api_key = get_api_key("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": _openrouter_model(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=25,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def dialogram_chat(messages: List[Dict[str, str]], max_tokens: int = 600, temperature: float = 0.7) -> str:
    """Call Dialogram (Nexum) router endpoint for Qwen models."""
    api_key = get_api_key("DIALOGRAM_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="DIALOGRAM_API_KEY not configured")
    resp = requests.post(
        "https://www.dialogram.me/router/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": _model_id("DIALOGRAM_MODEL", "qwen-3.6-plus"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def llm_chat(messages: List[Dict[str, str]], max_tokens: int = 600, temperature: float = 0.7) -> str:
    """Try providers in order of likelihood to work based on current env."""
    errors = []
    providers = [
        ("Dialogram", dialogram_chat),
        ("Groq", groq_chat),
        ("DeepSeek", deepseek_chat),
        ("Ollama", ollama_chat),
        ("Gemini", gemini_chat),
        ("Mistral", mistral_chat),
        ("Together", together_chat),
        ("OpenRouter", openrouter_chat),
    ]
    for i, (name, fn) in enumerate(providers):
        try:
            if i > 0:
                print(f"[llm fallback] {providers[i-1][0]} failed, trying {name}...")
            return fn(messages, max_tokens=max_tokens, temperature=temperature)
        except (requests.RequestException, HTTPException, KeyError, IndexError, ValueError) as e:
            # Only provider failures belong in the fallback chain. A TypeError in our
            # own code must surface as a 500, not as eight "provider" failures.
            detail = getattr(e, "detail", None) or str(e)
            errors.append(f"{name}: {detail}")
    raise HTTPException(
        status_code=503,
        detail=(
            "No LLM provider could write the script. Configure at least one provider "
            "key in Settings, or run a local Ollama model. "
            f"Attempts: {' | '.join(errors)}"
        ),
    )

def _delivery_instructions(style: Optional[str]) -> str:
    """Prompt block that tells the scriptwriter how to mark delivery.

    The markers are the same ones the TTS layer understands: ``[[pause:0.6]]`` inserts
    silence, ``[[style:calm]]`` changes delivery for the rest of that turn.
    """
    rules = """
Delivery directions, written inline where they belong:
- Insert [[pause:0.6]] at natural beats: after a question, before an answer, after a key fact, and at the end of a section. Use 0.3 to 1.2 seconds and never two in a row.
- Mark a genuine tonal shift with [[style:calm]], [[style:excited]], [[style:serious]] or [[style:narrative]], at most twice in the whole script.
- Write no other bracket markers, no stage directions and no sound effects."""

    if style and style != DEFAULT_STYLE:
        rules += f"\n- The overall delivery of this episode is {style}."
    return rules

def parse_conversation_script(raw_text: str, speakers: List[str]) -> List[Dict[str, str]]:
    """Parse raw conversation text into a structured script array.

    Two traps are handled explicitly:
    - longer names are matched first, so "Guest A" is not read as "Guest";
    - a line that starts with a name the cast does not contain is dropped and counted,
      not silently appended to the previous speaker's turn.
    """
    script = []
    lines = raw_text.strip().split('\n')
    ordered = sorted(speakers, key=len, reverse=True)
    speaker_pattern = re.compile(
        rf'^({"|".join(re.escape(s) for s in ordered)})\s*[:\-]\s*(.*)$', re.IGNORECASE
    )
    unknown_prefix = re.compile(r"^([A-Za-z][A-Za-z0-9 _.'-]{0,40})\s*[:\-]\s+")
    dropped_lines = 0

    current_speaker = None
    current_content = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = speaker_pattern.match(line)
        if match:
            if current_speaker and current_content:
                script.append({"speaker": current_speaker, "content": current_content.strip()})
            spoken_name = match.group(1)
            canonical = next((s for s in speakers if s.lower() == spoken_name.lower()), speakers[0])
            current_speaker = canonical
            current_content = match.group(2)
        elif unknown_prefix.match(line):
            # Looks like "Somebody: text" for a speaker we do not have. Attributing it
            # to the previous host would quietly corrupt the script.
            dropped_lines += 1
            logger.warning("Dropping a line from an unknown speaker: %s", line[:60])
        else:
            if current_content:
                current_content += " " + line
            else:
                current_content = line

    if current_speaker and current_content:
        script.append({"speaker": current_speaker, "content": current_content.strip()})

    if dropped_lines:
        logger.warning("Dropped %d line(s) from unknown speakers", dropped_lines)
    return script

def build_speaker_list(format_type: str, speakers: Optional[List[str]]) -> List[str]:
    defaults = {
        "monologue": ["Host"],
        "interview": ["Host", "Guest"],
        "panel": ["Host", "Guest A", "Guest B"],
    }
    default = defaults.get(format_type, ["Host"])
    if speakers and len(speakers) >= len(default):
        cleaned = [s for s in speakers[:len(default)] if isinstance(s, str) and s.strip()]
        if len(cleaned) == len(default):
            return cleaned
    return default

# ============== FastAPI App ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"\n🚀 AI_VOICEVIBE Voice Service starting...")
    print(f"   Device: {DEVICE.upper()}")
    if LONGFORM_PRELOAD_AT_STARTUP:
        print("   LONGFORM_PRELOAD_AT_STARTUP=true — starting background longform TTS load thread")
        threading.Thread(target=_preload_longform_worker, daemon=True).start()
    if ASR_PRELOAD_AT_STARTUP:
        print("   ASR_PRELOAD_AT_STARTUP=true — starting background ASR load thread")
        threading.Thread(target=_preload_asr_worker, daemon=True).start()
    if not LONGFORM_PRELOAD_AT_STARTUP and not ASR_PRELOAD_AT_STARTUP:
        print("   Models load lazily on first request (set *_PRELOAD_AT_STARTUP=true to preload)\n")
    yield
    print("\n👋 Shutting down voice service")
    stop_mps_cache_clear()
    _tts_executor.shutdown(wait=False)
    models.clear()
    if DEVICE == "mps":
        try:
            torch.mps.empty_cache()
        except Exception:
            pass

STATIC_DIR = os.path.join(BASE_DIR, "static")
# The static mount must serve the same directory the writers use, otherwise setting
# OUTPUT_DIR makes every saved episode unreachable.
OUTPUTS_DIR = OUTPUT_DIR

# Ensure outputs directory exists for static file serving
os.makedirs(OUTPUTS_DIR, exist_ok=True)

app = FastAPI(title="AI_VOICEVIBE Voice Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        *[
            origin.strip()
            for origin in os.environ.get("FRONTEND_ORIGINS", "").split(",")
            if origin.strip()
        ],
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Saved-Filename",
        "X-Chunks-Used",
        "X-Gen-Time-Sec",
        "X-TTS-Provider",
        "X-Language-Fallback",
    ],
)

# Request ID middleware for log correlation
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    request_id_var.set(request_id)
    start_time = time.time()
    
    # Log incoming request
    logger.info(
        f"→ {request.method} {request.url.path} | req:{request_id} | client:{request.client.host if request.client else '-'}"
    )
    
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"← {request.method} {request.url.path} | req:{request_id} | status:{response.status_code} | {duration_ms:.1f}ms"
        )
        return response
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"✕ {request.method} {request.url.path} | req:{request_id} | ERROR after {duration_ms:.1f}ms | {str(e)}"
        )
        raise

# Mount static files only if directory exists (legacy HTML frontend, optional)
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")

@app.get("/", response_class=HTMLResponse)
async def root():
    # Prefer index.html, fallback to legacy name
    if os.path.isdir(STATIC_DIR):
        for filename in ["index.html", "podcast_brain_frontend.html"]:
            path = os.path.join(STATIC_DIR, filename)
            if os.path.exists(path):
                with open(path, "r") as f:
                    return f.read()
    return HTMLResponse(content="<h1>Podcast Brain Pro</h1><p>API is running. Use the Next.js frontend at http://localhost:3000</p>")

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "device": DEVICE,
        "loaded_models": list(models.keys()),
        "asr_ready": asr_ready.is_set(),
        "torch_version": torch.__version__,
        "mps_available": torch.backends.mps.is_available(),
    }

@app.get("/voices")
async def voices_catalog():
    """List the voice presets available for longform and streaming synthesis.

    The UI uses this to offer a voice per speaker instead of guessing one.
    """
    longform_voices = [
        {
            "id": voice["id"],
            "language": voice["language"],
            "gender": voice["gender"],
            "name": voice["name"],
        }
        for voice in list_voices(LONGFORM_VOICES_DIR)
        if voice["ext"] == "wav"
    ]
    streaming_voices = [
        {
            "id": voice["id"],
            "language": voice["language"],
            "gender": voice["gender"],
            "name": voice["name"],
        }
        for voice in list_voices(VOICES_DIR)
        if voice["ext"] == "pt"
    ]
    cloned_voices = [
        {
            "id": voice["id"],
            "language": voice["language"],
            "gender": voice["gender"],
            "name": voice["name"],
            "engine": voice["engine"],
        }
        for voice in _consented_references()
    ]
    return {
        "longform": longform_voices,
        "streaming": streaming_voices,
        "cloned": cloned_voices,
        "styles": style_names(),
    }

@app.get("/models/status")
async def models_status():
    """Return detailed status of all TTS/ASR models: cached, loaded, sizes."""
    realtime_cached = is_model_cached("microsoft/VibeVoice-Realtime-0.5B")
    longform_cached = is_model_cached("microsoft/VibeVoice-1.5B")
    asr_cached = is_model_cached("microsoft/VibeVoice-ASR")

    try:
        ram_gb = round(psutil.virtual_memory().total / 1024 / 1024 / 1024, 2) if psutil is not None else None
    except Exception:
        ram_gb = None
    
    return {
        "realtime": {
            "name": "VibeVoice-Realtime-0.5B",
            "cached": realtime_cached,
            "loaded": "realtime_tts" in models,
            "cache_size_mb": round(get_cache_size("microsoft/VibeVoice-Realtime-0.5B") / 1024 / 1024, 1),
            "expected_size_mb": 2048,
        },
        "longform": {
            "name": "VibeVoice-TTS-1.5B",
            "cached": longform_cached,
            "loaded": "longform_tts" in models,
            "cache_size_mb": round(get_cache_size("microsoft/VibeVoice-1.5B") / 1024 / 1024, 1),
            "expected_size_mb": 5530,
        },
        "asr": {
            "name": "VibeVoice-ASR-7B",
            "cached": asr_cached,
            "loaded": "asr" in models,
            "cache_size_mb": round(get_cache_size("microsoft/VibeVoice-ASR") / 1024 / 1024, 1),
            "expected_size_mb": 14336,
        },
        "preload_config": {
            "longform_preload_at_startup": LONGFORM_PRELOAD_AT_STARTUP,
            "asr_preload_at_startup": ASR_PRELOAD_AT_STARTUP,
        },
        "limits": {
            "max_longform_words": get_max_longform_words(),
            "chunking_enabled": True,
            "device": DEVICE,
            "longform_ddpm_steps": int(os.environ.get("LONGFORM_DDPM_STEPS", "5")),
        },
        "system": {
            "ram_gb": ram_gb,
            "torch_version": torch.__version__,
            "mps_available": torch.backends.mps.is_available(),
            "device": DEVICE,
        }
    }

@app.get("/config")
async def get_config_endpoint():
    keys = [
        "DIALOGRAM_API_KEY",
        "SARVAM_API_KEY",
        "GROQ_API_KEY",
        "TAVILY_API_KEY",
        "DEEPSEEK_API_KEY",
        "GEMINI_API_KEY",
        "MISTRAL_API_KEY",
        "TOGETHER_API_KEY",
        "OPENROUTER_API_KEY",
    ]
    result = {}
    for k in keys:
        val = get_api_key(k)
        result[k] = {"configured": bool(val), "masked": mask_key(val)}
    return result

@app.post("/config")
async def post_config_endpoint(request: Request):
    req = await request.json()
    allowed = [
        "DIALOGRAM_API_KEY",
        "SARVAM_API_KEY",
        "GROQ_API_KEY",
        "TAVILY_API_KEY",
        "DEEPSEEK_API_KEY",
        "GEMINI_API_KEY",
        "MISTRAL_API_KEY",
        "TOGETHER_API_KEY",
        "OPENROUTER_API_KEY",
    ]
    cfg = get_config()
    saved: List[str] = []
    removed: List[str] = []
    invalid: List[str] = []
    for k in allowed:
        if k not in req:
            continue
        v = req[k]
        if isinstance(v, str) and v.strip():
            cfg[k] = v.strip()
            saved.append(k)
        elif v is None or (isinstance(v, str) and not v.strip()):
            if k in cfg:
                del cfg[k]
                removed.append(k)
        else:
            # A number, list or object is a client error, not a silent no-op.
            invalid.append(k)

    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"These keys must be a string or null: {', '.join(invalid)}",
        )

    if saved or removed:
        write_config(cfg)
    return {"status": "ok", "updated": bool(saved or removed), "saved": saved, "removed": removed}

# ============== Safety Limits ==============
# Longform 1.5B on MPS with float32 consumes ~23GB+ RAM for large inputs.
# float16 helps, but we still enforce a word limit to prevent swap thrashing.
# For Mac M4 24GB: more aggressive chunking is required to avoid MPS OOM / swap thrashing.
MAX_LONGFORM_WORDS_MPS = int(os.environ.get("MAX_LONGFORM_WORDS_MPS", "350"))
MAX_LONGFORM_WORDS_CPU = int(os.environ.get("MAX_LONGFORM_WORDS_CPU", "300"))

def get_max_longform_words() -> int:
    return MAX_LONGFORM_WORDS_MPS if DEVICE == "mps" else MAX_LONGFORM_WORDS_CPU

# ============== Auto-Chunking for Longform TTS ==============
# Chunking, sentence splitting and voice assignment live in script_pipeline so the
# generator, the longform path and the realtime path cannot drift apart.

_mps_cleanup_calls = 0

def _mps_cleanup():
    """Clear the MPS cache, and run a full GC only occasionally.

    gc.collect() is a stop-the-world collection over the whole heap; running it after
    every segment costs seconds on a large model for no measurable benefit.
    """
    global _mps_cleanup_calls
    if DEVICE == "mps":
        try:
            torch.mps.empty_cache()
        except Exception:
            pass
        _mps_cleanup_calls += 1
        if _mps_cleanup_calls % 4 == 0:
            gc.collect()

def _generate_longform_chunk(
    processor, model,
    segment: List[Dict[str, Any]],
    voice_samples: List[str],
    cfg_scale: float,
    target_device: str
) -> bytes:
    """Generate audio for one synthesis segment. Returns WAV bytes.

    ``segment`` is a list of units with a stable global ``speaker_id``; the script the
    model sees is ``Speaker N: text`` where N is that global id, so the voice sample
    list stays aligned with the speakers across every segment of the episode.
    """
    full_script = units_to_script_lines(segment).replace("’", "'")

    inputs = processor(
        text=[full_script],
        voice_samples=[voice_samples],
        padding=True,
        return_tensors="pt",
        return_attention_mask=True,
    )

    for k, v in inputs.items():
        if torch.is_tensor(v):
            inputs[k] = v.to(target_device)

    # Cap max_new_tokens to avoid runaway generation on MPS.
    # Rough heuristic: ~2.5 tokens per character for this model's speech representation.
    estimated_tokens = min(int(len(full_script) * 2.5) + 512, 8192)

    with _tts_generation_lock, torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=estimated_tokens,
            cfg_scale=cfg_scale,
            tokenizer=processor.tokenizer,
            generation_config={'do_sample': False},
            verbose=False,
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            processor.save_audio(outputs.speech_outputs[0], output_path=tmp.name)
            tmp_path = tmp.name
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    try:
        del inputs
    except NameError:
        pass
    try:
        del outputs
    except NameError:
        pass

    # Critical: clear MPS cache after each chunk to prevent accumulation
    _mps_cleanup()

    return audio_bytes

# ============== TTS Endpoints ==============

def _do_tts_realtime_sync(text: str, speaker_name: Optional[str], cfg_scale: Optional[float], save_to_disk: Optional[bool], topic: Optional[str], format: Optional[str], language: Optional[str], style: Optional[str] = None, extras: Optional[Dict[str, Any]] = None, duration_minutes: Optional[int] = None) -> tuple:
    """Synchronous helper for realtime TTS. Runs inside a thread pool.
    Returns (audio_bytes, saved_filename)."""
    processor, model = load_realtime_tts()

    speaker_name = speaker_name or "Carter"
    cfg_scale = cfg_scale if cfg_scale is not None else 1.5

    voices = [voice for voice in list_voices(VOICES_DIR) if voice["ext"] == "pt"]
    if not voices:
        raise HTTPException(status_code=500, detail="No voice presets found")

    assignment, _warnings = resolve_voices([speaker_name], voices)
    # An unknown speaker must not fall back to the alphabetically first voice file,
    # which can be a different language altogether. Prefer an English preset.
    default_voice = next((v for v in voices if v["language"] == "en"), voices[0])
    voice_id = assignment.get(speaker_name, default_voice["id"])
    voice_path = next(voice["path"] for voice in voices if voice["id"] == voice_id)
    logger.info("Realtime voice for %r: %s", speaker_name, voice_id)

    target_device = DEVICE if DEVICE != "cpu" else "cpu"
    all_prefilled_outputs = torch.load(voice_path, map_location=target_device, weights_only=False)

    def synth(unit_text: str, unit_cfg: float) -> bytes:
        """Generate one stretch of speech with the streaming voice."""
        inputs = processor.process_input_with_cached_prompt(
            text=unit_text,
            cached_prompt=all_prefilled_outputs,
            padding=True,
            return_tensors="pt",
            return_attention_mask=True,
        )

        for k, v in inputs.items():
            if torch.is_tensor(v):
                inputs[k] = v.to(target_device)

        try:
            with _tts_generation_lock:
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=None,
                    cfg_scale=unit_cfg,
                    tokenizer=processor.tokenizer,
                    generation_config={'do_sample': False},
                    verbose=False,
                    all_prefilled_outputs=copy.deepcopy(all_prefilled_outputs) if all_prefilled_outputs is not None else None,
                )

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    processor.save_audio(outputs.speech_outputs[0], output_path=tmp.name)
                    tmp_path = tmp.name

                with open(tmp_path, "rb") as f:
                    return f.read()
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        finally:
            try:
                del inputs
            except NameError:
                pass
            try:
                del outputs
            except NameError:
                pass
            _mps_cleanup()

    # Delivery directives split the text into stretches separated by pauses.
    units = split_units(text, default_style=style or DEFAULT_STYLE)
    if not units:
        raise HTTPException(status_code=400, detail="text is empty")

    audios: List[bytes] = []
    gaps_ms: List[int] = []
    for unit in units:
        unit_cfg = cfg_scale * style_cfg_multiplier(unit["style"])
        audios.append(synth(unit["text"], unit_cfg))
        gaps_ms.append(int(round((unit.get("pause_after") or 0.0) * 1000)))

    if len(audios) == 1:
        audio_bytes = audios[0]
    else:
        audio_bytes = stitch_wav_bytes(audios, silence_ms=0, gaps_ms=gaps_ms)

    saved_filename = None
    if save_to_disk:
        word_count = len(text.split())
        meta = {"word_count": word_count, "speaker_name": speaker_name, "voice_names": [voice_id], "format": format, "language": language, "duration_minutes": duration_minutes, "engine": "vibevoice"}
        if extras:
            chapters = extras.get("chapters") or []
            if chapters:
                if len(chapters) != 1 or chapters[0].get("start_turn") != 0:
                    raise HTTPException(
                        status_code=400,
                        detail="Realtime monologue chapters must contain only the opening chapter.",
                    )
                extras = with_chapter_timing(extras, {0: 0.0})
            meta["extras"] = extras
        if topic:
            meta["topic"] = topic
        audio_bytes = _finalize_audio(audio_bytes, meta)
        saved_filename = save_to_outputs(audio_bytes, prefix="podcast_realtime", metadata=meta)
        _save_transcript_sidecar(
            saved_filename,
            [{"speaker": speaker_name or "Host", "content": text}],
            meta,
        )

    return audio_bytes, saved_filename


@app.post("/tts/realtime")
async def tts_realtime(req: TTSRealtimeRequest):
    try:
        loop = asyncio.get_event_loop()
        audio_bytes, saved_filename = await loop.run_in_executor(
            _tts_executor, _do_tts_realtime_sync,
            req.text, req.speaker_name, req.cfg_scale, req.save_to_disk, req.topic, req.format, req.language, req.style, req.extras, req.duration_minutes
        )
        headers = {"X-Saved-Filename": saved_filename} if saved_filename else {}
        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav", headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ============== Optional local engines (Kokoro, Chatterbox, ...) ==============

REFERENCE_DIR = os.path.join(OUTPUT_DIR, "reference_voices")
CONSENT_DIR = os.path.join(OUTPUT_DIR, "voice_consents")


def _consented_references(engine_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List reference voices that have a persisted consent record and existing audio."""
    references: List[Dict[str, Any]] = []
    if not os.path.isdir(CONSENT_DIR):
        return references
    for filename in sorted(os.listdir(CONSENT_DIR), reverse=True):
        if not filename.endswith(".json"):
            continue
        try:
            with open(os.path.join(CONSENT_DIR, filename), encoding="utf-8") as handle:
                record = json.load(handle)
            reference_name = os.path.basename(record["reference_audio"])
            engine = record["engine"]
            reference_path = os.path.join(REFERENCE_DIR, reference_name)
            if engine_id and engine != engine_id:
                continue
            if not os.path.isfile(reference_path):
                continue
            references.append({
                "id": reference_name,
                "name": os.path.splitext(reference_name)[0],
                "language": record.get("language") or "en",
                "gender": "cloned",
                "engine": engine,
                "path": reference_path,
                "reference_text": record.get("reference_text") or "",
                "consent_record": filename,
            })
        except (OSError, ValueError, KeyError, TypeError):
            logger.warning("Ignoring invalid voice consent record: %s", filename)
    return references


def _synthesize_engine_text(
    engine_id: str,
    text: str,
    voice: Optional[str] = None,
    reference_path: Optional[str] = None,
    speed: float = 1.0,
    exaggeration: float = 0.5,
    cfg_weight: float = 0.5,
    language: str = "en",
    style: Optional[str] = None,
    reference_text: Optional[str] = None,
) -> bytes:
    """Render text with an optional engine, honouring the delivery directives.

    Pauses become real silence between the rendered parts, exactly as they do on the
    built-in VibeVoice paths. Qwen also receives each part's style as an instruction.
    """
    units = split_units(text, default_style=style or DEFAULT_STYLE)
    if not units:
        raise HTTPException(status_code=400, detail="text is empty")

    audios: List[bytes] = []
    gaps_ms: List[int] = []
    for unit in units:
        audio = synthesize(
            engine_id,
            unit["text"],
            voice=voice,
            reference_path=reference_path,
            speed=speed,
            exaggeration=(
                max(0.0, min(1.0, exaggeration * style_cfg_multiplier(unit["style"])))
                if engine_id == "chatterbox" else exaggeration
            ),
            cfg_weight=cfg_weight,
            language=language,
            style=unit["style"],
            reference_text=reference_text,
        )
        audios.append(audio)
        gaps_ms.append(int(round((unit.get("pause_after") or 0.0) * 1000)))

    if len(audios) == 1:
        return audios[0]
    return stitch_wav_bytes(audios, silence_ms=0, gaps_ms=gaps_ms)

class EngineTTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    engine: str = "kokoro"
    voice: Optional[str] = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    language: str = "en"
    style: Optional[str] = Field(
        default="neutral", pattern="^(neutral|calm|narrative|serious|warm|excited)$"
    )
    save_to_disk: Optional[bool] = False
    topic: Optional[str] = None

@app.get("/engines")
async def engines_catalog():
    """List the optional local engines, what they cost and whether they are installed."""
    return {"engines": await asyncio.to_thread(list_engines)}

@app.post("/tts/engine")
async def tts_with_engine(req: EngineTTSRequest):
    """Synthesise with a small optional engine such as Kokoro or Chatterbox."""
    loop = asyncio.get_event_loop()
    reference_path = None
    reference_text = None
    if req.voice and req.engine in ("qwen3-tts", "chatterbox"):
        reference = next(
            (voice for voice in _consented_references(req.engine) if voice["id"] == req.voice),
            None,
        )
        if reference:
            reference_path = reference["path"]
            reference_text = reference["reference_text"]
    try:
        audio_bytes = await loop.run_in_executor(
            _tts_executor,
            _synthesize_engine_text,
            req.engine,
            req.text,
            req.voice,
            reference_path,
            req.speed,
            0.5,
            0.5,
            req.language,
            req.style,
            reference_text,
        )
    except EngineUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    meta = {"engine": req.engine, "voice": req.voice, "word_count": len(req.text.split())}
    if req.topic:
        meta["topic"] = req.topic
    audio_bytes = _finalize_audio(audio_bytes, meta)

    saved_filename = None
    if req.save_to_disk:
        saved_filename = save_to_outputs(audio_bytes, prefix=f"podcast_{req.engine}", metadata=meta, subdirectory="previews")

    headers = {"X-Saved-Filename": saved_filename} if saved_filename else {}
    return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav", headers=headers)

@app.post("/tts/clone")
async def tts_clone(
    text: str = Form(...),
    engine: str = Form("chatterbox"),
    consent: bool = Form(False),
    reference: UploadFile = File(...),
    reference_text: Optional[str] = Form(None),
    language: str = Form("en"),
    exaggeration: float = Form(0.5),
    cfg_weight: float = Form(0.5),
    save_to_disk: bool = Form(True),
):
    """Clone a voice from a short reference clip and speak new text with it.

    Cloning is consent gated: the caller must confirm they own the voice or have
    permission to clone it, and the confirmation is stored with the reference file.
    """
    try:
        spec = get_engine(engine)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown voice engine: {engine}")
    if not spec.cloning:
        raise HTTPException(status_code=400, detail=f"{spec.label} does not support voice cloning")
    if engine == "qwen3-tts" and not (reference_text or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Qwen3-TTS requires the exact transcript of the reference recording.",
        )
    if not consent:
        raise HTTPException(
            status_code=400,
            detail=(
                "Voice cloning needs consent. Confirm that this is your own voice or "
                "that you have written permission from the speaker, then try again."
            ),
        )

    data = await reference.read()
    if not data:
        raise HTTPException(status_code=400, detail="reference audio is empty")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="reference audio must be under 25 MB")
    try:
        reference_audio = AudioSegment.from_file(io.BytesIO(data))
    except Exception:
        raise HTTPException(status_code=400, detail="reference audio could not be decoded")
    reference_seconds = len(reference_audio) / 1000
    if reference_seconds < 3 or reference_seconds > 60:
        raise HTTPException(
            status_code=400,
            detail="reference audio must contain 3-60 seconds of clean speech",
        )

    os.makedirs(REFERENCE_DIR, exist_ok=True)
    os.makedirs(CONSENT_DIR, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", os.path.basename(reference.filename or "reference.wav"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    reference_path = os.path.join(REFERENCE_DIR, f"{stamp}_{safe_name}")
    with open(reference_path, "wb") as handle:
        handle.write(data)

    consent_record = {
        "created_at": datetime.now().isoformat(),
        "engine": engine,
        "reference_audio": os.path.basename(reference_path),
        "reference_text": (reference_text or "").strip(),
        "language": language,
        "text_characters": len(text),
        "statement": (
            "The caller confirmed that the reference voice is their own voice or that "
            "they have written permission from the speaker to clone it."
        ),
    }
    consent_path = os.path.join(CONSENT_DIR, f"{stamp}.json")
    with open(consent_path, "w", encoding="utf-8") as handle:
        json.dump(consent_record, handle, indent=2)

    def discard_clone_upload() -> None:
        for path in (reference_path, consent_path):
            try:
                os.unlink(path)
            except OSError:
                pass

    loop = asyncio.get_event_loop()
    try:
        audio_bytes = await loop.run_in_executor(
            _tts_executor,
            _synthesize_engine_text,
            engine,
            text,
            None,
            reference_path,
            1.0,
            exaggeration,
            cfg_weight,
            language,
            None,
            reference_text,
        )
    except EngineUnavailable as e:
        discard_clone_upload()
        raise HTTPException(status_code=503, detail=str(e))
    except KeyError as e:
        discard_clone_upload()
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        discard_clone_upload()
        raise
    except Exception as e:
        discard_clone_upload()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    meta = {
        "engine": engine,
        "cloned_from": os.path.basename(reference_path),
        "word_count": len(text.split()),
        "consent_record": f"{stamp}.json",
    }
    audio_bytes = _finalize_audio(audio_bytes, meta)

    saved_filename = None
    if save_to_disk:
        saved_filename = save_to_outputs(audio_bytes, prefix="podcast_clone", metadata=meta, subdirectory="previews")

    headers = {"X-Saved-Filename": saved_filename} if saved_filename else {}
    return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav", headers=headers)

def _do_tts_engine_script_sync(
    req: TTSLongformRequest,
    turns: List[Dict[str, str]],
    _max_words: int,
    req_id: str,
) -> tuple:
    """Render a multi-host script through a single-voice engine and stitch the turns."""
    t0 = time.time()
    if req.engine not in {"kokoro", "qwen3-tts", "chatterbox"}:
        raise HTTPException(status_code=400, detail=f"Unsupported dialogue engine: {req.engine}")
    spec = get_engine(req.engine)

    speakers = speaker_order(turns)
    requested = {
        speaker: (req.voice_names[index] if req.voice_names and index < len(req.voice_names) else "")
        for index, speaker in enumerate(speakers)
    }
    references = {
        voice["id"]: voice for voice in _consented_references(req.engine)
    }
    if req.engine == "chatterbox" and not references:
        raise HTTPException(
            status_code=400,
            detail="Clone and consent to at least one Chatterbox voice in Voice Lab first.",
        )

    assignments: Dict[str, Dict[str, Any]] = {}
    used: set = set()
    for speaker in speakers:
        candidate = requested.get(speaker) or ""
        reference = references.get(candidate)
        voice_id = candidate if candidate in spec.default_voices else ""
        if req.engine == "chatterbox" and reference is None:
            reference = next(
                (voice for key, voice in references.items() if key not in used), None
            )
        if not reference and not voice_id:
            voice_id = next(
                (voice for voice in spec.default_voices if voice not in used),
                spec.default_voices[0] if spec.default_voices else "",
            )
        if reference:
            if req.engine == "qwen3-tts" and not reference["reference_text"]:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Clone '{reference['name']}' has no stored reference transcript. "
                        "Create it again in Voice Lab before using it in an episode."
                    ),
                )
            voice_id = reference["id"]
            assignments[speaker] = {
                "id": voice_id,
                "voice": None,
                "reference_path": reference["path"],
                "reference_text": reference["reference_text"],
            }
        elif voice_id:
            assignments[speaker] = {
                "id": voice_id,
                "voice": voice_id,
                "reference_path": None,
                "reference_text": None,
            }
        else:
            raise HTTPException(status_code=400, detail=f"No voice available for {speaker}")
        used.add(voice_id)

    req.voice_names = [assignments[name]["id"] for name in speakers]
    log_audio_event(
        "info", "ENGINE_DIALOGUE_PLAN",
        extra={
            "engine": req.engine,
            "speakers": speakers,
            "voices": {name: selected["voice"] or "consented-clone" for name, selected in assignments.items()},
        },
        req_id=req_id,
    )

    audios: List[bytes] = []
    gaps_ms: List[int] = []
    engine_word_limit = {"chatterbox": 180, "qwen3-tts": 500, "kokoro": 300}[req.engine]
    units = chunk_units_for_engine(
        build_units(turns, default_style=req.style or DEFAULT_STYLE),
        min(_max_words, engine_word_limit),
    )
    chapter_turns = {
        chapter["start_turn"] for chapter in (req.extras or {}).get("chapters", [])
    }
    chapter_starts: Dict[int, float] = {}
    elapsed = 0.0
    for unit in units:
        turn_index = unit["turn_index"]
        if turn_index in chapter_turns and turn_index not in chapter_starts:
            chapter_starts[turn_index] = elapsed
        selected = assignments[unit["speaker"]]
        style = unit["style"]
        audio = synthesize(
            req.engine,
            unit["text"],
            voice=selected["voice"],
            reference_path=selected["reference_path"],
            reference_text=selected["reference_text"],
            speed=style_params(style)["pace"] if req.engine == "kokoro" else 1.0,
            exaggeration=(
                max(0.0, min(1.0, 0.5 * style_cfg_multiplier(style)))
                if req.engine == "chatterbox" else 0.5
            ),
            language=req.language or "en",
            style=style,
        )
        audios.append(audio)
        pause = unit.get("pause_after") or 0.0
        gap_ms = int(round(pause * 1000)) if pause else 250
        gaps_ms.append(gap_ms)
        elapsed += wav_duration_seconds(audio) + gap_ms / 1000

    return (
        stitch_wav_bytes(audios, silence_ms=250, gaps_ms=gaps_ms),
        len(audios),
        round(time.time() - t0, 2),
        chapter_starts,
    )


def _do_tts_longform_sync(
    req: TTSLongformRequest,
    turns: List[Dict[str, str]],
    max_words: int,
    req_id: str,
) -> tuple:
    """Synchronous helper that performs the actual longform TTS generation.
    Runs inside a thread pool so the asyncio event loop stays responsive."""
    t0 = time.time()
    audio_bytes = b""
    chunks_used = 0

    log_audio_event("info", "LONGFORM_LOADING_MODEL", req_id=req_id)
    processor, model = load_longform_tts()
    load_time = round(time.time() - t0, 2)
    log_audio_event("info", "LONGFORM_MODEL_READY", extra={"load_time_sec": load_time}, req_id=req_id)

    # The script was validated before the model was loaded, so it is usable here.
    speakers = speaker_order(turns)
    voices = list_voices(LONGFORM_VOICES_DIR)
    assignment, voice_warnings = resolve_voices(speakers, voices, req.voice_names)
    for warning in voice_warnings:
        log_audio_event("warning", "LONGFORM_VOICE_WARNING", extra={"detail": warning}, req_id=req_id)

    req.voice_names = [assignment[name] for name in speakers if name in assignment]
    voice_samples = voice_paths_by_id(assignment, voices)
    if not voice_samples:
        raise HTTPException(
            status_code=500, detail="no voice files found in the longform voices directory"
        )

    chapter_turns = {
        chapter["start_turn"] for chapter in (req.extras or {}).get("chapters", [])
    }
    grouped = group_units(
        build_units(turns, default_style=req.style or DEFAULT_STYLE),
        break_before_turns=chapter_turns,
    )
    segments = plan_generation(grouped, max_words, break_before_turns=chapter_turns)
    chunks_used = len(segments)
    total_words = sum(len(unit["text"].split()) for unit in grouped)

    log_audio_event("info", "LONGFORM_PLAN",
                    extra={"words": total_words, "segments": chunks_used, "speakers": speakers,
                           "voices": assignment, "max_words_per_segment": max_words}, req_id=req_id)

    target_device = DEVICE if DEVICE != "cpu" else "cpu"
    base_cfg = req.cfg_scale if req.cfg_scale is not None else 1.3

    # Start periodic MPS cache clear for long generations
    start_mps_cache_clear()
    try:
        segment_audios: List[bytes] = []
        gaps_ms: List[int] = []
        chapter_starts: Dict[int, float] = {}
        elapsed = 0.0
        for idx, segment in enumerate(segments):
            turn_index = segment[0]["turn_index"]
            if turn_index in chapter_turns and turn_index not in chapter_starts:
                chapter_starts[turn_index] = elapsed
            segment_words = sum(len(unit["text"].split()) for unit in segment)
            style = segment[0]["style"]
            cfg = base_cfg * style_cfg_multiplier(style)
            segment_t0 = time.time()
            log_audio_event("info", f"LONGFORM_SEGMENT_{idx+1}_START",
                            extra={"segment_words": segment_words, "segment_idx": idx + 1,
                                   "total_segments": chunks_used, "style": style}, req_id=req_id)

            segment_bytes = _generate_longform_chunk(
                processor, model, segment, voice_samples, cfg, target_device
            )
            log_audio_event("info", f"LONGFORM_SEGMENT_{idx+1}_COMPLETE",
                            extra={"segment_time_sec": round(time.time() - segment_t0, 2),
                                   "segment_bytes": len(segment_bytes)}, req_id=req_id)
            segment_audios.append(segment_bytes)
            gap_ms = int(round(segment_gap_seconds(segment) * 1000))
            gaps_ms.append(gap_ms)
            elapsed += wav_duration_seconds(segment_bytes) + gap_ms / 1000

        # Stitch every segment together, honouring the pause after each one
        stitch_t0 = time.time()
        audio_bytes = stitch_wav_bytes(segment_audios, silence_ms=400, gaps_ms=gaps_ms)
        log_audio_event("info", "LONGFORM_STITCH_COMPLETE",
                        extra={"stitch_time_sec": round(time.time() - stitch_t0, 2),
                               "total_bytes": len(audio_bytes)}, req_id=req_id)
    finally:
        stop_mps_cache_clear()
        _mps_cleanup()
    
    total_time = round(time.time() - t0, 2)
    return audio_bytes, chunks_used, total_time, chapter_starts


@app.post("/tts/longform")
async def tts_longform(req: TTSLongformRequest):
    req_id = get_request_id()
    turns = normalize_turns(req.script)
    if not turns:
        # Reject before the model is loaded: an empty script must not trigger a
        # multi-gigabyte model download.
        raise HTTPException(status_code=400, detail="script is empty")
    total_words = sum(len(turn["content"].split()) for turn in turns)
    total_chars = sum(len(turn["content"]) for turn in turns)
    max_words = get_max_longform_words()

    log_audio_event("info", "LONGFORM_REQUEST_START",
        extra={"words": total_words, "chars": total_chars, "speakers": len(turns),
               "device": DEVICE, "max_allowed": max_words, "format": req.format, "language": req.language})
    
    t0 = time.time()
    try:
        # Run the blocking generation in a thread pool so FastAPI stays responsive.
        # This prevents "socket hang up" errors on the frontend.
        # We use our custom executor (max 2 workers) to limit concurrent TTS jobs.
        loop = asyncio.get_event_loop()
        handler = _do_tts_longform_sync if req.engine == "vibevoice" else _do_tts_engine_script_sync
        audio_bytes, chunks_used, gen_time, chapter_starts = await loop.run_in_executor(
            _tts_executor, handler, req, turns, max_words, req_id
        )
        
        meta = {
            "word_count": total_words,
            "engine": req.engine,
            "voice_names": req.voice_names or [],
            "format": req.format or "interview",
            "language": req.language,
            "duration_minutes": req.duration_minutes,
            "chunks": chunks_used,
            "device": DEVICE,
        }
        if req.extras:
            meta["extras"] = (
                with_chapter_timing(req.extras, chapter_starts)
                if req.extras.get("chapters") else req.extras
            )
        if req.topic:
            meta["topic"] = req.topic
        audio_bytes = _finalize_audio(audio_bytes, meta)

        saved_filename = None
        if req.save_to_disk:
            saved_filename = save_to_outputs(audio_bytes, prefix="podcast_longform", metadata=meta)
            _save_transcript_sidecar(saved_filename, req.script, meta)
        
        total_time = round(time.time() - t0, 2)
        log_audio_event("info", "LONGFORM_REQUEST_COMPLETE",
            extra={"total_time_sec": total_time, "audio_bytes": len(audio_bytes),
                   "saved": bool(saved_filename), "chunks": chunks_used})
        
        headers = {
            "X-Saved-Filename": saved_filename or "",
            "X-Chunks-Used": str(chunks_used),
            "X-Gen-Time-Sec": str(gen_time),
        }
        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav", headers=headers)
    except HTTPException:
        raise
    except EngineUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        total_time = round(time.time() - t0, 2)
        log_audio_event("error", "LONGFORM_REQUEST_FAILED",
            extra={"total_time_sec": total_time, "error": str(e), "error_type": type(e).__name__})
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

def chunk_text_by_sentences(text: str, max_chars: int = 2400) -> List[str]:
    """Split text into chunks at sentence boundaries, respecting max_chars.

    The sentence split itself lives in script_pipeline so the TTS paths and the
    script contract cannot drift apart.
    """
    chunks = []
    current = ""
    for sentence in split_sentences(text):
        if len(current) + len(sentence) + 1 <= max_chars:
            current = current + " " + sentence if current else sentence
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


async def _sarvam_fallback(req: SarvamTTSRequest):
    """Use the full VibeVoice longform pipeline for English; never fake Indic output."""
    if not req.target_language_code.lower().startswith("en"):
        raise HTTPException(
            status_code=503,
            detail=(
                "Sarvam is unavailable and VibeVoice cannot render the requested "
                "Indian language. Configure/retry Sarvam; no downgraded file was saved."
            ),
        )
    turns = normalize_turns(req.script) if req.script is not None else []
    if not turns:
        turns = [{"speaker": req.speaker, "content": req.text}]
    fallback_req = TTSLongformRequest(
        script=turns,
        voice_names=req.voice_names or [req.speaker],
        engine="vibevoice",
        save_to_disk=req.save_to_disk,
        topic=req.topic,
        format=req.format,
        language="en",
        duration_minutes=req.duration_minutes,
        style=req.style,
        extras=req.extras,
    )
    response = await tts_longform(fallback_req)
    response.headers["X-TTS-Provider"] = "vibevoice-local-fallback"
    response.headers["X-Language-Fallback"] = "true"
    return response


@app.post("/tts/sarvam")
async def tts_sarvam(req: SarvamTTSRequest):
    """Proxy to Sarvam AI Bulbul TTS API for Indian language support.
    Automatically chunks long text and stitches audio segments together.
    Falls back to local VibeVoice TTS if SARVAM_API_KEY is not configured."""
    api_key = get_api_key("SARVAM_API_KEY")
    if not api_key:
        print("[tts/sarvam] SARVAM_API_KEY missing — falling back to local VibeVoice TTS.")
        try:
            return await _sarvam_fallback(req)
        except HTTPException:
            raise
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))
    
    fallback_triggered = False
    try:
        turns = normalize_turns(req.script) if req.script is not None else []
        if req.script is not None and not turns:
            raise HTTPException(status_code=400, detail="script is empty")
        speakers = speaker_order(turns)
        voice_map: Dict[str, str] = {}
        for index, speaker in enumerate(speakers):
            requested_voice = (
                req.voice_names[index]
                if req.voice_names and index < len(req.voice_names) else ""
            )
            voice_map[speaker] = (
                requested_voice
                or (req.speaker if index == 0 else "")
                or SARVAM_DEFAULT_VOICES[index % len(SARVAM_DEFAULT_VOICES)]
            )

        # Delivery directives are honoured per turn; each unit retains its source
        # speaker and turn index for voice selection and measured chapter starts.
        units: List[Dict[str, Any]] = []
        if turns:
            for turn_index, turn in enumerate(turns):
                for unit in split_units(turn["content"], default_style=req.style or DEFAULT_STYLE):
                    units.append({
                        **unit,
                        "speaker": turn["speaker"],
                        "turn_index": turn_index,
                    })
        else:
            units = [
                {**unit, "speaker": req.speaker, "turn_index": 0}
                for unit in split_units(req.text, default_style=req.style or DEFAULT_STYLE)
            ]
        if not units:
            raise HTTPException(status_code=400, detail="text is empty")

        chunks: List[str] = []
        gaps_ms: List[int] = []
        chunk_styles: List[str] = []
        chunk_speakers: List[str] = []
        chunk_turns: List[int] = []
        for unit in units:
            pieces = chunk_text_by_sentences(unit["text"], max_chars=2400) or [unit["text"]]
            for index, piece in enumerate(pieces):
                chunks.append(piece)
                chunk_styles.append(unit["style"])
                chunk_speakers.append(unit["speaker"])
                chunk_turns.append(unit["turn_index"])
                last_piece = index == len(pieces) - 1
                gaps_ms.append(
                    int(round((unit.get("pause_after") or 0.0) * 1000)) if last_piece else 300
                )
        if len(chunks) > 1:
            print(f"Sarvam TTS: rendering {len(chunks)} parts for {len(req.text)} chars")

        language_code = SARVAM_LANGUAGE_CODES.get(req.target_language_code, req.target_language_code)

        segments = []
        wav_segments: List[bytes] = []
        chapter_turns = {
            chapter["start_turn"] for chapter in (req.extras or {}).get("chapters", [])
        }
        chapter_starts: Dict[int, float] = {}
        elapsed = 0.0
        for idx, chunk in enumerate(chunks):
            turn_index = chunk_turns[idx]
            if turn_index in chapter_turns and turn_index not in chapter_starts:
                chapter_starts[turn_index] = elapsed
            style = chunk_styles[idx]
            params = style_params(style)
            payload = {
                "text": chunk,
                "target_language_code": language_code,
                "speaker": voice_map.get(chunk_speakers[idx], req.speaker),
                "pace": req.pace if style == DEFAULT_STYLE else params["pace"],
                "model": req.model,
                "output_audio_codec": req.output_audio_codec,
            }
            if req.model in ("bulbul:v3", "bulbul:v2"):
                payload["temperature"] = (
                    req.temperature if style == DEFAULT_STYLE else params["temperature"]
                )
            else:
                if req.pitch is not None:
                    payload["pitch"] = req.pitch
                if req.loudness is not None:
                    payload["loudness"] = req.loudness
                if req.dict_id:
                    payload["dict_id"] = req.dict_id

            resp = requests.post(
                "https://api.sarvam.ai/text-to-speech",
                headers={
                    "api-subscription-key": api_key,
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=120
            )
            if not resp.ok:
                # Log the exact error and fall back to local TTS instead of hard-failing
                fallback_triggered = True
                print(f"[tts/sarvam] Sarvam API error: {resp.status_code} — {resp.text[:200]}. Falling back to local VibeVoice TTS.")
                return await _sarvam_fallback(req)

            data = resp.json()
            audio_bytes = base64.b64decode(data["audios"][0])

            if req.output_audio_codec == "wav":
                wav_segments.append(audio_bytes)
                elapsed += wav_duration_seconds(audio_bytes) + gaps_ms[idx] / 1000
                continue

            fmt = req.output_audio_codec.replace("mulaw", "wav").replace("alaw", "wav")
            seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format=fmt)
            segments.append(seg)
            elapsed += len(seg) / 1000 + gaps_ms[idx] / 1000

        if req.output_audio_codec == "wav":
            master_wav = stitch_wav_bytes(wav_segments, silence_ms=0, gaps_ms=gaps_ms)
        else:
            # Compressed inputs need decoding before they can become the lossless master.
            final_audio = segments[0]
            for index, seg in enumerate(segments[1:]):
                gap = gaps_ms[index] if index < len(gaps_ms) else 300
                if gap > 0:
                    final_audio = final_audio + AudioSegment.silent(duration=gap) + seg
                else:
                    final_audio = final_audio + seg

            tmp_path = None
            try:
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp_path = tmp.name
                tmp.close()
                final_audio.export(tmp_path, format="wav")
                with open(tmp_path, "rb") as handle:
                    master_wav = handle.read()
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        meta = {
            "word_count": len(req.text.split()),
            "speaker": req.speaker,
            "voice_names": [voice_map[speaker] for speaker in speakers] if turns else [req.speaker],
            "language": req.language or req.target_language_code,
            "duration_minutes": req.duration_minutes,
            "provider": "sarvam",
            "engine": "sarvam",
            "chunks": len(chunks),
            "format": req.format or "monologue",
        }
        if req.extras:
            meta["extras"] = (
                with_chapter_timing(req.extras, chapter_starts)
                if req.extras.get("chapters") else req.extras
            )
        if req.topic:
            meta["topic"] = req.topic
        wav_bytes = _finalize_audio(master_wav, meta)

        if req.output_audio_codec == "wav":
            audio_bytes = wav_bytes
        else:
            final_audio = AudioSegment.from_file(io.BytesIO(wav_bytes), format="wav")
            buf = io.BytesIO()
            export_format = "wav" if req.output_audio_codec in ("pcm", "mulaw", "alaw") else req.output_audio_codec
            final_audio.export(buf, format=export_format)
            audio_bytes = buf.getvalue()

        # The episode library stores WAV, whatever codec the caller asked for, so the
        # history list and the RSS feed never point at a file with the wrong extension.
        saved_filename = None
        if req.save_to_disk:
            saved_filename = save_to_outputs(wav_bytes, prefix="podcast_sarvam", metadata=meta)
            _save_transcript_sidecar(
                saved_filename,
                turns or [{"speaker": req.speaker, "content": req.text}],
                meta,
            )
        
        codec_to_mime = {
            "wav": "audio/wav", "mp3": "audio/mpeg", "aac": "audio/aac",
            "opus": "audio/opus", "flac": "audio/flac", "pcm": "audio/pcm",
            "mulaw": "audio/mulaw", "alaw": "audio/alaw"
        }
        mime = codec_to_mime.get(req.output_audio_codec, "audio/wav")
        headers = {"X-TTS-Provider": "sarvam", "X-Chunks-Used": str(len(chunks))}
        if saved_filename:
            headers["X-Saved-Filename"] = saved_filename
        return StreamingResponse(io.BytesIO(audio_bytes), media_type=mime, headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        if fallback_triggered:
            # Exception came from the fallback itself — don't retry
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))
        # Any unexpected exception (network, timeout, etc.) — fall back to local TTS
        print(f"[tts/sarvam] Exception calling Sarvam: {e}. Falling back to local VibeVoice TTS.")
        traceback.print_exc()
        try:
            return await _sarvam_fallback(req)
        except HTTPException:
            raise
        except Exception as fallback_e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(fallback_e))

# ============== Podcast Generation ==============

@app.post("/podcast/generate", response_model=PodcastScriptResponse)
def podcast_generate(req: PodcastGenerateRequest):
    start_time = time.time()
    try:
        duration_cfg = DURATION_CONFIG.get(req.duration_minutes, DURATION_CONFIG[2])
        target_words = duration_cfg["words"]
        max_tokens = duration_cfg["max_tokens"]
        chapters = duration_cfg["chapters"]
        speakers = build_speaker_list(req.format, req.speakers)
        
        # Tavily research (truncate to avoid Groq payload limits)
        research = tavily_research(req.topic)
        if not research:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            context_file = os.path.join(script_dir, "research_context.txt")
            if os.path.exists(context_file):
                with open(context_file, "r") as f:
                    research = f.read()
        if research and len(research) > 4000:
            research = research[:4000] + "\n[Research truncated for brevity]"
        
        lang_name = LANGUAGE_MAP.get(req.language, "English")
        is_indic = req.language != "en"
        lang_instruction = "" if not is_indic else f"\n- Write the entire script in {lang_name} language only. Do not use English."
        length_instruction = "" if not is_indic else f"\n- You MUST write a comprehensive, detailed script. Include specific examples, facts, historical context, and multiple viewpoints. Do not be brief or summarize."
        
        # Indic scripts need more tokens per word
        groq_max_tokens = int(max_tokens * 1.5) if is_indic else max_tokens
        
        def expand_script_if_needed(script_data, current_words):
            """Expand a script that came out far short of the target length.

            Off by default: the extra round trip costs time on the free tier, and the
            provider that answers first is often the one that under-writes. Turn it on
            with EXPAND_SHORT_SCRIPTS=true when long Indic episodes need filling out.
            """
            if not EXPAND_SHORT_SCRIPTS or current_words >= target_words * 0.6:
                return script_data, current_words
            print(f"[expand fallback] Script too short ({current_words}/{target_words} words). Expanding...")
            time.sleep(2.5)  # delay to avoid immediate back-to-back Groq calls
            if req.format == "monologue":
                existing = script_data[0]["content"]
                prompt = f"""Expand the following monologue to approximately {target_words} words by adding more detail, examples, historical context, statistics, and depth. Keep the tone conversational. Write entirely in {lang_name} only. Output the full expanded text.

Original monologue:
{existing}"""
                expanded = llm_chat([
                    {"role": "system", "content": "You are a podcast scriptwriter who writes detailed, in-depth monologues."},
                    {"role": "user", "content": prompt}
                ], max_tokens=groq_max_tokens)
                return [{"speaker": speakers[0], "content": expanded}], len(expanded.split())
            else:
                existing_lines = "\n".join([f"{item['speaker']}: {item['content']}" for item in script_data])
                prompt = f"""Expand the following podcast conversation to approximately {target_words} words by adding more dialogue turns, examples, facts, and natural back-and-forth. Keep the same format with 'SpeakerName: ...' at the start of each line. Write entirely in {lang_name} only. Output the full expanded script.

Original conversation:
{existing_lines}"""
                expanded = llm_chat([
                    {"role": "system", "content": "You are a podcast scriptwriter who writes detailed, natural conversations."},
                    {"role": "user", "content": prompt}
                ], max_tokens=groq_max_tokens)
                parsed = parse_conversation_script(expanded, speakers)
                if not parsed:
                    parsed = [{"speaker": speakers[0], "content": expanded}]
                return parsed, sum(len(item["content"].split()) for item in parsed)
        
        # Build prompt based on format
        delivery_rules = _delivery_instructions(req.style)
        if req.format == "monologue":
            system_prompt = f"""You are a podcast scriptwriter. Write a single-host monologue that:
- Is approximately {target_words} words (about {req.duration_minutes} minutes when spoken)
- Sounds conversational and natural
- Presents multiple perspectives fairly
- Avoids hype, clickbait, or fear-mongering
- Ends with a brief sign-off
- Do not use markdown, bullet points, or sound effect cues. Just plain spoken text.{lang_instruction}{length_instruction}
{delivery_rules}"""
            user_prompt = f"Topic: {req.topic}\n\nResearch notes:\n{research}\n\nWrite the monologue script in {lang_name}."
            raw_script = llm_chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ], max_tokens=groq_max_tokens)
            script = [{"speaker": speakers[0], "content": raw_script}]
        else:
            # Multi-speaker conversation
            speaker_list_str = ", ".join(speakers)
            system_prompt = f"""You are a podcast scriptwriter. Write a natural podcast conversation between {speaker_list_str}.
- Target length: approximately {target_words} words (about {req.duration_minutes} minutes when spoken)
- Start with {speakers[0]} introducing the show and topic
- Each line must begin with the speaker name followed by a colon (e.g., "{speakers[0]}: Welcome to the show...")
- Sounds conversational, with natural back-and-forth
- Presents multiple perspectives fairly
- Avoids hype, clickbait, or fear-mongering
- Ends with a brief sign-off from {speakers[0]}
- Do not use markdown, bullet points, or sound effect cues.{lang_instruction}{length_instruction}
{delivery_rules}"""
            
            user_prompt = f"Topic: {req.topic}\n\nResearch notes:\n{research}\n\nWrite the full conversation script in {lang_name}."
            
            # For 15-30 min, use 2-pass generation
            if chapters:
                outline_prompt = f"""Create a detailed {chapters}-chapter outline for a {req.duration_minutes}-minute podcast about: {req.topic}
Use this research: {research[:3000]}

Return ONLY the outline as a numbered list with a title and 1-sentence description for each chapter."""
                outline = llm_chat([
                    {"role": "system", "content": "You are a podcast producer."},
                    {"role": "user", "content": outline_prompt}
                ], max_tokens=800)
                
                expansion_prompt = f"""Using this outline, write the FULL conversation script in {lang_name}.

Outline:
{outline}

Format rules:
- Target: {target_words} words (~{req.duration_minutes} min)
- Speakers: {speaker_list_str}
- Each line starts with "SpeakerName: ..."
- Cover all chapters in the outline
- Natural, conversational dialogue
- Write entirely in {lang_name}, do not use English.
{delivery_rules}

Now write the complete script."""
                raw_script = llm_chat([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": expansion_prompt}
                ], max_tokens=groq_max_tokens)
            else:
                raw_script = llm_chat([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ], max_tokens=groq_max_tokens)
            
            script = parse_conversation_script(raw_script, speakers)
            if not script:
                # Fallback: treat entire text as host
                script = [{"speaker": speakers[0], "content": raw_script}]
        
        word_count = sum(len(item["content"].split()) for item in script)
        
        # Auto-expand if significantly under target (common for Indic LLM outputs)
        script, word_count = expand_script_if_needed(script, word_count)
        if req.format == "monologue":
            combined = "\n\n".join(turn["content"] for turn in script)
            script = split_monologue_turns(combined, speakers[0])
            word_count = sum(len(turn["content"].split()) for turn in script)

        extras = None
        extras_error = None
        if req.include_extras:
            chapter_count = (
                1 if req.format == "monologue"
                else chapters or {2: 2, 5: 3, 10: 3}.get(req.duration_minutes, 4)
            )
            try:
                extras = generate_content_extras(
                    req.topic,
                    script,
                    req.duration_minutes,
                    lang_name,
                    chapter_count,
                    llm_chat,
                )
            except Exception as e:
                # The completed script remains useful when an optional metadata pass fails.
                logger.error("Content extras generation failed: %s", e)
                extras_error = f"Script ready, but show notes/chapters/clips failed: {e}"

        gen_time = round(time.time() - start_time, 2)
        
        return {
            "topic": req.topic,
            "duration_minutes": req.duration_minutes,
            "format": req.format,
            "script": script,
            "word_count": word_count,
            # Let the caller see that a "30 minute" request produced a two minute
            # script instead of silently accepting it.
            "target_words": target_words,
            "under_target": word_count < target_words * 0.6,
            "extras": extras,
            "extras_error": extras_error,
            "generation_time_seconds": gen_time,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/podcast/extras")
def podcast_content_extras(req: ContentExtrasRequest):
    """Refresh metadata for an existing or edited script without rewriting it."""
    try:
        chapter_count = (
            1 if req.format == "monologue"
            else DURATION_CONFIG.get(req.duration_minutes, DURATION_CONFIG[2])["chapters"]
                or {2: 2, 5: 3, 10: 3}.get(req.duration_minutes, 4)
        )
        extras = generate_content_extras(
            req.topic,
            req.script,
            req.duration_minutes,
            LANGUAGE_MAP.get(req.language, req.language),
            chapter_count,
            llm_chat,
        )
        return {"extras": extras}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.get("/podcast/history")
async def podcast_history(limit: int = Query(default=20, ge=1, le=100)):
    """List recently generated podcast audio files."""
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        files = []
        for f in os.listdir(OUTPUT_DIR):
            if f.endswith(".wav"):
                path = os.path.join(OUTPUT_DIR, f)
                stat = os.stat(path)
                entry = {
                    "filename": f,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "has_transcript": os.path.exists(os.path.splitext(path)[0] + ".transcript.json"),
                }
                meta_path = path.replace(".wav", ".json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as mf:
                            metadata = json.load(mf)
                        if metadata.get("topic"):
                            entry["topic"] = metadata["topic"]
                        if metadata.get("title"):
                            entry["title"] = metadata["title"]
                        if metadata.get("word_count"):
                            entry["word_count"] = metadata["word_count"]
                        if metadata.get("format"):
                            entry["format"] = metadata["format"]
                        if metadata.get("language"):
                            entry["language"] = metadata["language"]
                        if metadata.get("provider"):
                            entry["provider"] = metadata["provider"]
                        if metadata.get("engine"):
                            entry["engine"] = metadata["engine"]
                        if metadata.get("extras"):
                            entry["extras"] = metadata["extras"]
                        if metadata.get("loudness"):
                            entry["loudness"] = metadata["loudness"]
                        if metadata.get("duration_seconds"):
                            entry["duration_seconds"] = metadata["duration_seconds"]
                    except Exception:
                        pass
                files.append(entry)
        files.sort(key=lambda x: x["created_at"], reverse=True)
        return {"files": files[:limit]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RenameRequest(BaseModel):
    old_filename: str
    new_filename: str

@app.post("/podcast/rename")
async def podcast_rename(payload: RenameRequest):
    """Rename a saved podcast episode file."""
    try:
        old_name = os.path.basename(payload.old_filename.strip())
        new_name = os.path.basename(payload.new_filename.strip())

        if not old_name.endswith(".wav") or not new_name.endswith(".wav"):
            raise HTTPException(status_code=400, detail="Only .wav files can be renamed")

        if old_name != payload.old_filename.strip() or new_name != payload.new_filename.strip():
            raise HTTPException(status_code=400, detail="Invalid filename")

        old_path = os.path.join(OUTPUT_DIR, old_name)
        new_path = os.path.join(OUTPUT_DIR, new_name)

        if not os.path.exists(old_path):
            raise HTTPException(status_code=404, detail="File not found")

        if os.path.exists(new_path):
            raise HTTPException(status_code=409, detail="A file with that name already exists")

        os.rename(old_path, new_path)

        # Move the sidecars too: splitext, not str.replace, so a topic containing
        # "wav" cannot mangle the metadata filename.
        old_base = os.path.splitext(old_path)[0]
        new_base = os.path.splitext(new_path)[0]
        for suffix in (".json", ".transcript.json", ".chapters.json"):
            old_sidecar = old_base + suffix
            if os.path.exists(old_sidecar):
                os.rename(old_sidecar, new_base + suffix)

        stat = os.stat(new_path)
        return {
            "filename": new_name,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/podcast/delete")
async def podcast_delete(filename: str = Query(...)):
    """Delete a saved podcast episode and its metadata."""
    try:
        name = os.path.basename(filename.strip())
        if not name.endswith(".wav"):
            raise HTTPException(status_code=400, detail="Only .wav files can be deleted")
        if name != filename.strip():
            raise HTTPException(status_code=400, detail="Invalid filename")

        wav_path = os.path.join(OUTPUT_DIR, name)
        base_path = os.path.splitext(wav_path)[0]

        if not os.path.exists(wav_path):
            raise HTTPException(status_code=404, detail="File not found")

        os.unlink(wav_path)
        # Remove the metadata and the transcript sidecar as well, otherwise the feed
        # keeps advertising files that no longer exist.
        removed_sidecars = []
        for suffix in (".json", ".transcript.json", ".chapters.json"):
            sidecar = base_path + suffix
            if os.path.exists(sidecar):
                os.unlink(sidecar)
                removed_sidecars.append(os.path.basename(sidecar))

        return {"deleted": name, "sidecars": removed_sidecars}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/feed/podcast.rss")
async def podcast_feed():
    """Return a valid RSS 2.0 podcast feed for all saved episodes.

    ``PUBLIC_BASE_URL`` must point at a host that can reach this machine, otherwise the
    enclosure URLs in the feed point at localhost and no podcast host can fetch them.
    """
    try:
        rss_xml = generate_podcast_rss(
            OUTPUT_DIR,
            base_url=os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
            channel_title=os.environ.get("PODCAST_TITLE", "Podcast Brain Pro"),
            channel_description=os.environ.get(
                "PODCAST_DESCRIPTION", "AI generated podcasts, rendered locally"
            ),
            channel_author=os.environ.get("PODCAST_AUTHOR", "Podcast Brain Pro"),
            channel_language=os.environ.get("PODCAST_LANGUAGE", "en-us"),
            channel_category=os.environ.get("PODCAST_CATEGORY", "Technology"),
            channel_image=os.environ.get("PODCAST_IMAGE_URL", ""),
            channel_email=os.environ.get("PODCAST_EMAIL", ""),
        )
        return Response(content=rss_xml, media_type="application/rss+xml; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _do_asr_sync(tmp_path: str, language: str) -> dict:
    """Synchronous helper for ASR transcription. Runs inside a thread pool."""
    loaded = models.get("asr")
    if loaded is None:
        raise HTTPException(status_code=503, detail="The ASR model is not loaded.")
    processor, model = loaded

    inputs = processor(audio=tmp_path, sampling_rate=None, return_tensors="pt", padding=True, add_generation_prompt=True)
    inputs = {k: v.to(DEVICE) if isinstance(v, torch.Tensor) else v for k, v in inputs.items()}

    # Transcription must be deterministic. do_sample=True with temperature=0.0 is
    # rejected by transformers and would be wrong for ASR anyway.
    generation_config = {
        "max_new_tokens": 512,
        "pad_token_id": processor.pad_id,
        "eos_token_id": processor.tokenizer.eos_token_id,
        "do_sample": False,
    }
    
    try:
        with torch.no_grad():
            output_ids = model.generate(**inputs, **generation_config)
        
        input_length = inputs['input_ids'].shape[1]
        generated_ids = output_ids[0, input_length:]
        eos_positions = (generated_ids == processor.tokenizer.eos_token_id).nonzero(as_tuple=True)[0]
        if len(eos_positions) > 0:
            generated_ids = generated_ids[:eos_positions[0] + 1]
        
        generated_text = processor.decode(generated_ids, skip_special_tokens=True)
        
        try:
            transcription_segments = processor.post_process_transcription(generated_text)
        except Exception:
            transcription_segments = []
    finally:
        del inputs
        if 'output_ids' in dir():
            del output_ids
        if 'generated_ids' in dir():
            del generated_ids
        _mps_cleanup()
    
    return {
        "text": generated_text,
        "segments": transcription_segments,
        "language": language,
    }


# ============== ASR Endpoint ==============

@app.post("/asr/transcribe")
async def asr_transcribe(
    audio: UploadFile = File(...),
    language: Optional[str] = Form("en"),
):
    if not asr_ready.is_set():
        # Load on first use, like the TTS models do. With ASR_PRELOAD_AT_STARTUP=false
        # the endpoint used to return 503 forever and never trigger a load.
        logger.info("ASR requested before preload; loading the model now")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_tts_executor, load_asr)
        if not asr_ready.is_set():
            raise HTTPException(
                status_code=503,
                detail="The ASR model could not be loaded. Check the server log.",
            )
    
    # File size limit: 50MB to prevent OOM
    MAX_ASR_SIZE = 50 * 1024 * 1024
    content = await audio.read()
    if len(content) > MAX_ASR_SIZE:
        raise HTTPException(status_code=413, detail="Audio file too large. Max 50MB.")
    
    tmp_path = None
    try:
        filename = audio.filename or "upload.wav"
        suffix = os.path.splitext(filename)[1] or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_tts_executor, _do_asr_sync, tmp_path, language)
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ============== Main ==============

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
