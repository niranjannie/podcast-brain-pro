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
import numpy as np
import requests
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pydub import AudioSegment
from scipy.io import wavfile

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

def _periodic_mps_cache_clear(interval_sec: int = 45):
    """Background thread that clears MPS cache every N seconds during active generation."""
    while _mps_clear_active.is_set():
        if _mps_clear_active.wait(timeout=interval_sec):
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
    _mps_clear_active.set()
    _mps_clear_thread = threading.Thread(target=_periodic_mps_cache_clear, daemon=True)
    _mps_clear_thread.start()

def stop_mps_cache_clear():
    """Stop the periodic MPS cache cleaner."""
    _mps_clear_active.clear()

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
LONGFORM_PRELOAD_AT_STARTUP = os.environ.get("LONGFORM_PRELOAD_AT_STARTUP", "true").lower() in ("true", "1", "yes")

# Detect best device for M4 Mac
def get_device():
    if torch.backends.mps.is_available():
        print("🍎 Using Apple Silicon MPS acceleration")
        return "mps"
    print("🖥️  Using CPU fallback")
    return "cpu"

DEVICE = get_device()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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

def get_config() -> Dict[str, str]:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                return {}
        except Exception:
            return {}
    return {}

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

class TTSLongformRequest(BaseModel):
    script: List[Dict[str, Any]] = Field(..., min_length=1)  # [{"role": "Alice", "content": "Hello"}]
    voice_names: Optional[List[str]] = None
    cfg_scale: Optional[float] = 1.3
    save_to_disk: Optional[bool] = True
    topic: Optional[str] = None
    format: Optional[str] = "interview"
    language: Optional[str] = "en"

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

class PodcastGenerateRequest(BaseModel):
    topic: str
    duration_minutes: int = Field(default=2, ge=2, le=30)
    format: str = Field(default="monologue", pattern="^(monologue|interview|panel)$")
    speakers: Optional[List[str]] = Field(default=None, max_length=3)
    language: str = Field(default="en", pattern="^(en|hi-IN|ta-IN|te-IN|kn-IN|bn-IN|mr-IN|gu-IN|ml-IN|pa-IN|od-IN)$")

class PodcastScriptResponse(BaseModel):
    topic: str
    duration_minutes: int
    format: str
    script: List[Dict[str, str]]
    word_count: int
    generation_time_seconds: float

class SarvamTTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    target_language_code: str = Field(default="en-IN", pattern="^[a-z]{2}-[A-Z]{2}$")
    speaker: str = Field(default="shubh")
    pace: float = Field(default=1.0, ge=0.5, le=2.0)
    temperature: float = Field(default=0.6, ge=0.01, le=1.0)
    model: str = Field(default="bulbul:v3", pattern="^(bulbul:v3|bulbul:v2)$")
    output_audio_codec: str = Field(default="wav", pattern="^(wav|mp3|aac|opus|flac|pcm|mulaw|alaw)$")
    save_to_disk: Optional[bool] = False
    topic: Optional[str] = None
    format: Optional[str] = "monologue"
    language: Optional[str] = "en"

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

def save_to_outputs(audio_bytes: bytes, prefix: str = "podcast", metadata: Optional[Dict[str, Any]] = None) -> str:
    """Save audio bytes to outputs directory with timestamp.
    
    If metadata contains a non-empty topic, the filename becomes:
      podcast_{sanitized_topic}_{timestamp}.wav
    Otherwise falls back to:
      {prefix}_{timestamp}.wav
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
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
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "wb") as f:
        f.write(audio_bytes)

    # Calculate actual audio duration from WAV header
    duration_seconds = 0.0
    try:
        with io.BytesIO(audio_bytes) as bio:
            rate, data = wavfile.read(bio)
            duration_seconds = float(len(data)) / float(rate)
    except Exception:
        pass

    if metadata:
        meta_path = os.path.splitext(path)[0] + ".json"
        meta_payload = {
            "created_at": datetime.now().isoformat(),
            "duration_seconds": round(duration_seconds, 2),
            **metadata,
        }
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_payload, f, indent=2)
        except Exception as e:
            print(f"Failed to write metadata: {e}")

    return filename

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
                    "model": "llama-3.3-70b-versatile",
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
    raise HTTPException(status_code=429, detail=f"Groq API rate-limited after retries: {last_exception}")

def deepseek_chat(messages: List[Dict[str, str]], max_tokens: int = 600, temperature: float = 0.7) -> str:
    """Call DeepSeek API (OpenAI-compatible)."""
    api_key = get_api_key("DEEPSEEK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="DEEPSEEK_API_KEY not configured")
    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
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
            "model": "gemini-2.0-flash",
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
            "model": "mistral-small-latest",
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
            "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
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
    model = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
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

def openrouter_chat(messages: List[Dict[str, str]], max_tokens: int = 600, temperature: float = 0.7) -> str:
    """Call OpenRouter as final fallback."""
    api_key = get_api_key("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "mistralai/mistral-7b-instruct:free",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=25,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def github_models_chat(messages: List[Dict[str, str]], max_tokens: int = 600, temperature: float = 0.7) -> str:
    """Call GitHub Models endpoint (free GPT-4o)."""
    api_key = get_api_key("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not api_key:
        raise HTTPException(status_code=503, detail="GITHUB_PERSONAL_ACCESS_TOKEN not configured")
    resp = requests.post(
        "https://models.inference.ai.azure.com/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=60,
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
            "model": "qwen-3.6-plus",
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
        ("GitHub Models", github_models_chat),
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
        except Exception as e:
            detail = str(e)
            if hasattr(e, "detail"):
                detail = e.detail
            errors.append(f"{name}: {detail}")
    raise HTTPException(status_code=429, detail=f"All LLM providers failed: {' | '.join(errors)}")

def parse_conversation_script(raw_text: str, speakers: List[str]) -> List[Dict[str, str]]:
    """Parse raw conversation text into structured script array."""
    script = []
    lines = raw_text.strip().split('\n')
    speaker_pattern = re.compile(rf'^({"|".join(re.escape(s) for s in speakers)})\s*[:\-]\s*(.*)$', re.IGNORECASE)
    
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
            # Find the canonical speaker name
            spoken_name = match.group(1)
            canonical = next((s for s in speakers if s.lower() == spoken_name.lower()), speakers[0])
            current_speaker = canonical
            current_content = match.group(2)
        else:
            if current_content:
                current_content += " " + line
            else:
                current_content = line
    
    if current_speaker and current_content:
        script.append({"speaker": current_speaker, "content": current_content.strip()})
    
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
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

# Ensure outputs directory exists for static file serving
os.makedirs(OUTPUTS_DIR, exist_ok=True)

app = FastAPI(title="AI_VOICEVIBE Voice Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        "GITHUB_PERSONAL_ACCESS_TOKEN",
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
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "TAVILY_API_KEY",
        "DEEPSEEK_API_KEY",
        "GEMINI_API_KEY",
        "MISTRAL_API_KEY",
        "TOGETHER_API_KEY",
        "OPENROUTER_API_KEY",
    ]
    cfg = get_config()
    updated = False
    for k in allowed:
        if k in req:
            v = req[k]
            if isinstance(v, str) and v.strip():
                cfg[k] = v.strip()
                updated = True
            elif v is None or (isinstance(v, str) and not v.strip()):
                if k in cfg:
                    del cfg[k]
                    updated = True
    if updated:
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    return {"status": "ok", "updated": updated}

# ============== Safety Limits ==============
# Longform 1.5B on MPS with float32 consumes ~23GB+ RAM for large inputs.
# float16 helps, but we still enforce a word limit to prevent swap thrashing.
# For Mac M4 24GB: more aggressive chunking is required to avoid MPS OOM / swap thrashing.
MAX_LONGFORM_WORDS_MPS = int(os.environ.get("MAX_LONGFORM_WORDS_MPS", "350"))
MAX_LONGFORM_WORDS_CPU = int(os.environ.get("MAX_LONGFORM_WORDS_CPU", "300"))

def get_max_longform_words() -> int:
    return MAX_LONGFORM_WORDS_MPS if DEVICE == "mps" else MAX_LONGFORM_WORDS_CPU

# ============== Auto-Chunking for Longform TTS ==============

def _split_text_into_sentences(text: str) -> List[str]:
    """Split text into sentences, preserving speaker prefixes if present."""
    # Split on sentence terminators for multiple languages
    sentences = re.split(r'(?<=[.।।|!?।])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def _chunk_script_by_words(script: List[Dict[str, str]], max_words: int) -> List[List[Dict[str, str]]]:
    """
    Split a multi-speaker script into chunks where each chunk has <= max_words.
    Splits at sentence boundaries to avoid cutting mid-sentence.
    Preserves speaker continuity across chunks.
    """
    # Flatten into (speaker, sentence, word_count) tuples
    sentences = []
    for item in script:
        speaker = item.get("role", "Speaker")
        content = item.get("content", "")
        for sent in _split_text_into_sentences(content):
            words = len(sent.split())
            sentences.append({"speaker": speaker, "text": sent, "words": words})
    
    # Group sentences into chunks
    chunks = []
    current_chunk = []
    current_words = 0
    
    for sent in sentences:
        if current_words + sent["words"] > max_words and current_chunk:
            # Finalize current chunk
            chunks.append(current_chunk)
            current_chunk = [sent]
            current_words = sent["words"]
        else:
            current_chunk.append(sent)
            current_words += sent["words"]
    
    if current_chunk:
        chunks.append(current_chunk)
    
    # Convert chunks back into script format (group consecutive same-speaker sentences)
    result = []
    for chunk in chunks:
        script_lines = []
        current_speaker = None
        current_text = ""
        for sent in chunk:
            if sent["speaker"] == current_speaker:
                current_text += " " + sent["text"]
            else:
                if current_speaker and current_text:
                    script_lines.append({"role": current_speaker, "content": current_text.strip()})
                current_speaker = sent["speaker"]
                current_text = sent["text"]
        if current_speaker and current_text:
            script_lines.append({"role": current_speaker, "content": current_text.strip()})
        result.append(script_lines)
    
    return result

def _mps_cleanup():
    """Explicitly clear MPS cache and run GC. Critical for 24GB Macs."""
    if DEVICE == "mps":
        try:
            torch.mps.empty_cache()
        except Exception:
            pass
        gc.collect()

def _generate_longform_chunk(
    processor, model,
    chunk_script: List[Dict[str, str]],
    voice_samples: List[str],
    cfg_scale: float,
    target_device: str
) -> bytes:
    """Generate audio for a single chunk. Returns WAV bytes."""
    lines = []
    for i, item in enumerate(chunk_script):
        role = item.get("role", f"Speaker {i+1}")
        content = item.get("content", "")
        lines.append(f"Speaker {i+1}: {content}")
    
    full_script = '\n'.join(lines).replace("’", "'")
    
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

def _stitch_wav_bytes(chunks: List[bytes], silence_ms: int = 300) -> bytes:
    """Stitch multiple WAV byte arrays with silence gaps. Returns combined WAV bytes."""
    if not chunks:
        return b""
    if len(chunks) == 1:
        return chunks[0]
    
    segments = []
    for chunk in chunks:
        seg = AudioSegment.from_file(io.BytesIO(chunk), format="wav")
        segments.append(seg)
    
    # Concatenate with silence gaps
    silence = AudioSegment.silent(duration=silence_ms)
    final = segments[0]
    for seg in segments[1:]:
        final = final + silence + seg
    
    buf = io.BytesIO()
    final.export(buf, format="wav")
    buf.seek(0)
    return buf.read()

# ============== TTS Endpoints ==============

def _do_tts_realtime_sync(text: str, speaker_name: str, cfg_scale: float, save_to_disk: bool, topic: Optional[str], format: Optional[str], language: Optional[str]) -> tuple:
    """Synchronous helper for realtime TTS. Runs inside a thread pool.
    Returns (audio_bytes, saved_filename)."""
    processor, model = load_realtime_tts()
    
    voice_name = speaker_name.lower()
    voice_path = None
    for f in os.listdir(VOICES_DIR):
        if f.lower().endswith(".pt") and voice_name in f.lower():
            voice_path = os.path.join(VOICES_DIR, f)
            break
    
    if not voice_path:
        pt_files = [f for f in os.listdir(VOICES_DIR) if f.endswith(".pt")]
        if not pt_files:
            raise HTTPException(status_code=500, detail="No voice presets found")
        voice_path = os.path.join(VOICES_DIR, pt_files[0])
    
    target_device = DEVICE if DEVICE != "cpu" else "cpu"
    all_prefilled_outputs = torch.load(voice_path, map_location=target_device, weights_only=False)
    
    inputs = processor.process_input_with_cached_prompt(
        text=text,
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
                cfg_scale=cfg_scale,
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
                audio_bytes = f.read()
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
    
    saved_filename = None
    if save_to_disk:
        word_count = len(text.split())
        meta = {"word_count": word_count, "speaker_name": speaker_name, "format": format, "language": language}
        if topic:
            meta["topic"] = topic
        saved_filename = save_to_outputs(audio_bytes, prefix="podcast_realtime", metadata=meta)
    
    return audio_bytes, saved_filename


@app.post("/tts/realtime")
async def tts_realtime(req: TTSRealtimeRequest):
    try:
        loop = asyncio.get_event_loop()
        audio_bytes, saved_filename = await loop.run_in_executor(
            _tts_executor, _do_tts_realtime_sync,
            req.text, req.speaker_name, req.cfg_scale, req.save_to_disk, req.topic, req.format, req.language
        )
        headers = {"X-Saved-Filename": saved_filename} if saved_filename else {}
        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav", headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

def _do_tts_longform_sync(req: TTSLongformRequest, max_words: int, req_id: str) -> tuple:
    """Synchronous helper that performs the actual longform TTS generation.
    Runs inside a thread pool so the asyncio event loop stays responsive."""
    t0 = time.time()
    audio_bytes = b""
    chunks_used = 0
    
    log_audio_event("info", "LONGFORM_LOADING_MODEL", req_id=req_id)
    processor, model = load_longform_tts()
    load_time = round(time.time() - t0, 2)
    log_audio_event("info", "LONGFORM_MODEL_READY", extra={"load_time_sec": load_time}, req_id=req_id)
    
    # Build voice samples list (same for all chunks)
    voice_names = []
    for i, item in enumerate(req.script):
        voice_names.append(item.get("role", f"Speaker {i+1}"))
    
    seen = set()
    unique_voices = []
    for name in voice_names:
        if name not in seen:
            seen.add(name)
            unique_voices.append(name)
    
    voice_samples = []
    for name in unique_voices:
        voice_path = None
        for f in os.listdir(LONGFORM_VOICES_DIR):
            if f.lower().endswith('.wav') and name.lower() in f.lower():
                voice_path = os.path.join(LONGFORM_VOICES_DIR, f)
                break
        if not voice_path:
            wavs = [f for f in os.listdir(LONGFORM_VOICES_DIR) if f.lower().endswith('.wav')]
            voice_path = os.path.join(LONGFORM_VOICES_DIR, wavs[0])
        voice_samples.append(voice_path)
    
    target_device = DEVICE if DEVICE != "cpu" else "cpu"
    chunks_used = 1
    
    # Start periodic MPS cache clear for long generations
    start_mps_cache_clear()
    try:
        # Decide: single pass or chunked
        if sum(len(item.get("content", "").split()) for item in req.script) <= max_words:
            # Single-pass generation
            total_words = sum(len(item.get("content", "").split()) for item in req.script)
            log_audio_event("info", "LONGFORM_SINGLE_PASS",
                extra={"words": total_words, "unique_voices": len(unique_voices)}, req_id=req_id)
            
            lines = []
            for i, item in enumerate(req.script):
                role = item.get("role", f"Speaker {i+1}")
                content = item.get("content", "")
                lines.append(f"Speaker {i+1}: {content}")
            full_script = '\n'.join(lines).replace("’", "'")
            
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
            
            estimated_tokens = min(int(len(full_script) * 2.5) + 512, 8192)
            gen_t0 = time.time()
            log_audio_event("info", "LONGFORM_GENERATION_START", req_id=req_id)
            try:
                with _tts_generation_lock, torch.inference_mode():
                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=estimated_tokens,
                        cfg_scale=req.cfg_scale,
                        tokenizer=processor.tokenizer,
                        generation_config={'do_sample': False},
                        verbose=False,
                    )
                gen_time = round(time.time() - gen_t0, 2)
                log_audio_event("info", "LONGFORM_GENERATION_COMPLETE",
                    extra={"gen_time_sec": gen_time}, req_id=req_id)
                
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
            finally:
                try:
                    del inputs
                except NameError:
                    pass
                try:
                    del outputs
                except NameError:
                    pass
            chunks_used = 1
        else:
            # Chunked generation to avoid OOM
            total_words = sum(len(item.get("content", "").split()) for item in req.script)
            chunks = _chunk_script_by_words(req.script, max_words)
            chunks_used = len(chunks)
            log_audio_event("info", "LONGFORM_CHUNKED_MODE",
                extra={"total_words": total_words, "chunks": chunks_used, "max_words_per_chunk": max_words}, req_id=req_id)
            
            chunk_audios = []
            for idx, chunk_script in enumerate(chunks):
                chunk_words = sum(len(item.get("content", "").split()) for item in chunk_script)
                chunk_t0 = time.time()
                log_audio_event("info", f"LONGFORM_CHUNK_{idx+1}_START",
                    extra={"chunk_words": chunk_words, "chunk_idx": idx + 1, "total_chunks": chunks_used}, req_id=req_id)
                
                chunk_bytes = _generate_longform_chunk(
                    processor, model, chunk_script, voice_samples,
                    req.cfg_scale, target_device
                )
                chunk_time = round(time.time() - chunk_t0, 2)
                log_audio_event("info", f"LONGFORM_CHUNK_{idx+1}_COMPLETE",
                    extra={"chunk_time_sec": chunk_time, "chunk_bytes": len(chunk_bytes)}, req_id=req_id)
                chunk_audios.append(chunk_bytes)
            
            # Stitch all chunks together
            stitch_t0 = time.time()
            audio_bytes = _stitch_wav_bytes(chunk_audios, silence_ms=400)
            stitch_time = round(time.time() - stitch_t0, 2)
            log_audio_event("info", "LONGFORM_STITCH_COMPLETE",
                extra={"stitch_time_sec": stitch_time, "total_bytes": len(audio_bytes)}, req_id=req_id)
    finally:
        stop_mps_cache_clear()
        _mps_cleanup()
    
    total_time = round(time.time() - t0, 2)
    return audio_bytes, chunks_used, total_time


@app.post("/tts/longform")
async def tts_longform(req: TTSLongformRequest):
    req_id = get_request_id()
    total_words = sum(len(item.get("content", "").split()) for item in req.script)
    total_chars = sum(len(item.get("content", "")) for item in req.script)
    max_words = get_max_longform_words()
    
    log_audio_event("info", "LONGFORM_REQUEST_START",
        extra={"words": total_words, "chars": total_chars, "speakers": len(req.script),
               "device": DEVICE, "max_allowed": max_words, "format": req.format, "language": req.language})
    
    t0 = time.time()
    try:
        # Run the blocking generation in a thread pool so FastAPI stays responsive.
        # This prevents "socket hang up" errors on the frontend.
        # We use our custom executor (max 2 workers) to limit concurrent TTS jobs.
        loop = asyncio.get_event_loop()
        audio_bytes, chunks_used, gen_time = await loop.run_in_executor(
            _tts_executor, _do_tts_longform_sync, req, max_words, req_id
        )
        
        saved_filename = None
        if req.save_to_disk:
            meta = {
                "word_count": total_words,
                "voice_names": req.voice_names or [],
                "format": req.format or "interview",
                "language": req.language,
                "chunks": chunks_used,
                "device": DEVICE,
            }
            if req.topic:
                meta["topic"] = req.topic
            saved_filename = save_to_outputs(audio_bytes, prefix="podcast_longform", metadata=meta)
        
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
    except Exception as e:
        total_time = round(time.time() - t0, 2)
        log_audio_event("error", "LONGFORM_REQUEST_FAILED",
            extra={"total_time_sec": total_time, "error": str(e), "error_type": type(e).__name__})
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

def chunk_text_by_sentences(text: str, max_chars: int = 2400) -> List[str]:
    """Split text into chunks at sentence boundaries, respecting max_chars."""
    # Split on sentence terminators for multiple languages (., ।, ৷, etc.)
    sentences = re.split(r'(?<=[.।।|!?।])\s+', text)
    chunks = []
    current = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(current) + len(s) + 1 <= max_chars:
            current = current + " " + s if current else s
        else:
            if current:
                chunks.append(current)
            current = s
    if current:
        chunks.append(current)
    return chunks


def _do_tts_local_fallback_sync(text: str, speaker: str, save_to_disk: bool = False, topic: Optional[str] = None) -> tuple:
    """Synchronous helper for Sarvam fallback. Returns (audio_bytes, saved_filename)."""
    processor, model = load_longform_tts()
    
    full_script = f"Speaker 1: {text}".replace("’", "'")
    
    voice_samples = []
    voice_path = None
    for f in os.listdir(LONGFORM_VOICES_DIR):
        if f.lower().endswith('.wav') and speaker.lower() in f.lower():
            voice_path = os.path.join(LONGFORM_VOICES_DIR, f)
            break
    if not voice_path:
        wavs = [f for f in os.listdir(LONGFORM_VOICES_DIR) if f.lower().endswith('.wav')]
        if not wavs:
            raise HTTPException(status_code=500, detail="No voice presets found")
        voice_path = os.path.join(LONGFORM_VOICES_DIR, wavs[0])
    voice_samples.append(voice_path)
    
    inputs = processor(
        text=[full_script],
        voice_samples=[voice_samples],
        padding=True,
        return_tensors="pt",
        return_attention_mask=True,
    )
    
    target_device = DEVICE if DEVICE != "cpu" else "cpu"
    for k, v in inputs.items():
        if torch.is_tensor(v):
            inputs[k] = v.to(target_device)
    
    estimated_tokens = min(int(len(full_script) * 2.5) + 512, 8192)
    try:
        with _tts_generation_lock, torch.inference_mode():
            outputs = model.generate(
                **inputs,
                max_new_tokens=estimated_tokens,
                cfg_scale=1.5,
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
    
    saved_filename = None
    if save_to_disk:
        meta = {"word_count": len(text.split()), "speaker": speaker, "provider": "vibevoice_fallback", "format": "monologue", "language": "en"}
        if topic:
            meta["topic"] = topic
        saved_filename = save_to_outputs(audio_bytes, prefix="podcast_fallback", metadata=meta)
    
    return audio_bytes, saved_filename


async def _tts_local_fallback(text: str, speaker: str, save_to_disk: bool = False, topic: Optional[str] = None):
    """Fallback to local VibeVoice longform TTS when Sarvam is unavailable.
    Runs in thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    audio_bytes, saved_filename = await loop.run_in_executor(
        _tts_executor, _do_tts_local_fallback_sync, text, speaker, save_to_disk, topic
    )
    headers = {"X-Saved-Filename": saved_filename} if saved_filename else {}
    return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav", headers=headers)

@app.post("/tts/sarvam")
async def tts_sarvam(req: SarvamTTSRequest):
    """Proxy to Sarvam AI Bulbul TTS API for Indian language support.
    Automatically chunks long text and stitches audio segments together.
    Falls back to local VibeVoice TTS if SARVAM_API_KEY is not configured."""
    api_key = get_api_key("SARVAM_API_KEY")
    if not api_key:
        print("[tts/sarvam] SARVAM_API_KEY missing — falling back to local VibeVoice TTS.")
        try:
            return await _tts_local_fallback(req.text, req.speaker, save_to_disk=req.save_to_disk, topic=req.topic)
        except HTTPException:
            raise
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))
    
    fallback_triggered = False
    try:
        chunks = chunk_text_by_sentences(req.text, max_chars=2400)
        if len(chunks) > 1:
            print(f"Sarvam TTS: text too long ({len(req.text)} chars), splitting into {len(chunks)} chunks")
        
        segments = []
        for idx, chunk in enumerate(chunks):
            payload = {
                "text": chunk,
                "target_language_code": req.target_language_code,
                "speaker": req.speaker,
                "pace": req.pace,
                "model": req.model,
                "output_audio_codec": req.output_audio_codec,
            }
            if req.model == "bulbul:v3":
                payload["temperature"] = req.temperature
            
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
                return await _tts_local_fallback(req.text, req.speaker, save_to_disk=req.save_to_disk, topic=req.topic)
            
            data = resp.json()
            audio_bytes = base64.b64decode(data["audios"][0])
            
            # Load into pydub AudioSegment for concatenation
            fmt = req.output_audio_codec.replace("mulaw", "wav").replace("alaw", "wav")
            seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format=fmt)
            segments.append(seg)
        
        # Concatenate all segments with brief silence between chunks
        final_audio = segments[0]
        for seg in segments[1:]:
            final_audio = final_audio + AudioSegment.silent(duration=300) + seg
        
        buf = io.BytesIO()
        export_format = "wav" if req.output_audio_codec in ("pcm", "mulaw", "alaw") else req.output_audio_codec
        final_audio.export(buf, format=export_format)
        buf.seek(0)
        audio_bytes = buf.read()
        
        saved_filename = None
        if req.save_to_disk:
            meta = {"word_count": len(req.text.split()), "speaker": req.speaker, "language": req.language or req.target_language_code, "provider": "sarvam", "chunks": len(chunks), "format": req.format or "monologue"}
            if req.topic:
                meta["topic"] = req.topic
            saved_filename = save_to_outputs(audio_bytes, prefix="podcast_sarvam", metadata=meta)
        
        codec_to_mime = {
            "wav": "audio/wav", "mp3": "audio/mpeg", "aac": "audio/aac",
            "opus": "audio/opus", "flac": "audio/flac", "pcm": "audio/pcm",
            "mulaw": "audio/mulaw", "alaw": "audio/alaw"
        }
        mime = codec_to_mime.get(req.output_audio_codec, "audio/wav")
        headers = {"X-Saved-Filename": saved_filename} if saved_filename else {}
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
            return await _tts_local_fallback(req.text, req.speaker, save_to_disk=req.save_to_disk, topic=req.topic)
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
            """Fallback expansion if script is significantly shorter than target."""
            # Skip expansion when using slow local fallback to avoid timeouts
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
        if req.format == "monologue":
            system_prompt = f"""You are a podcast scriptwriter. Write a single-host monologue that:
- Is approximately {target_words} words (about {req.duration_minutes} minutes when spoken)
- Sounds conversational and natural
- Presents multiple perspectives fairly
- Avoids hype, clickbait, or fear-mongering
- Ends with a brief sign-off
- Do not use markdown, bullet points, or sound effect cues. Just plain spoken text.{lang_instruction}{length_instruction}"""
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
- Do not use markdown, bullet points, or sound effect cues.{lang_instruction}{length_instruction}"""
            
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
        
        gen_time = round(time.time() - start_time, 2)
        
        return {
            "topic": req.topic,
            "duration_minutes": req.duration_minutes,
            "format": req.format,
            "script": script,
            "word_count": word_count,
            "generation_time_seconds": gen_time,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

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

        # Rename metadata if present
        old_meta = old_path.replace(".wav", ".json")
        new_meta = new_path.replace(".wav", ".json")
        if os.path.exists(old_meta):
            os.rename(old_meta, new_meta)

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
        meta_path = wav_path.replace(".wav", ".json")

        if not os.path.exists(wav_path):
            raise HTTPException(status_code=404, detail="File not found")

        os.unlink(wav_path)
        if os.path.exists(meta_path):
            os.unlink(meta_path)

        return {"deleted": name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/feed/podcast.rss")
async def podcast_feed():
    """Return a valid RSS 2.0 podcast feed for all saved episodes."""
    try:
        rss_xml = generate_podcast_rss(OUTPUT_DIR, base_url="http://localhost:9876")
        return Response(content=rss_xml, media_type="application/rss+xml; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _do_asr_sync(tmp_path: str, language: str) -> dict:
    """Synchronous helper for ASR transcription. Runs inside a thread pool."""
    processor, model = models["asr"]
    
    inputs = processor(audio=tmp_path, sampling_rate=None, return_tensors="pt", padding=True, add_generation_prompt=True)
    inputs = {k: v.to(DEVICE) if isinstance(v, torch.Tensor) else v for k, v in inputs.items()}
    
    generation_config = {
        "max_new_tokens": 512,
        "pad_token_id": processor.pad_id,
        "eos_token_id": processor.tokenizer.eos_token_id,
        "do_sample": True,
        "temperature": 0.0,
        "top_p": 1.0,
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
        raise HTTPException(
            status_code=503,
            detail="ASR model is still loading. Please retry shortly.",
            headers={"Retry-After": "30"},
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
