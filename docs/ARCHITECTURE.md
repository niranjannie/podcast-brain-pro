# Architecture Overview

Podcast Brain Pro is a **FastAPI backend** with a **React/Next.js frontend**. It separates **script generation** (cloud LLMs) from **audio synthesis** (local TTS models).

```
┌─────────────────────────┐      HTTP/WebSocket      ┌─────────────────────┐
│   React/Next.js UI      │  ◄──────────────────►   │   FastAPI Server    │
│   (localhost:3000)      │                         │     (main.py)       │
└─────────────────────────┘                         └─────────────────────┘
                                                            │
                           ┌────────────────────────────────┼────────────────────────────────┐
                           │                                │                                │
                           ▼                                ▼                                ▼
                  ┌───────────────┐              ┌─────────────────┐              ┌─────────────────┐
                  │   Dialogram   │              │  VibeVoice TTS  │              │   Sarvam AI     │
                  │  (Qwen 3.6)   │              │  (Local GPU)    │              │  (Cloud TTS)    │
                  │  Script Gen   │              │  English Audio  │              │  Indian Lang    │
                  └───────────────┘              └─────────────────┘              └─────────────────┘
                                                         ▲
                                                         │
                                              Auto-download from HuggingFace
                                              on first audio generation
```

## Design Philosophy

- **Instant gratification:** Script generation is fast and cloud-based. Anyone can try it immediately.
- **Local audio power:** High-quality English TTS requires Apple Silicon MPS or NVIDIA CUDA. This runs locally.
- **Modular providers:** LLM keys are swappable via a fallback chain.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.10+, FastAPI, Uvicorn |
| TTS | Microsoft VibeVoice (Realtime 0.5B, Longform 1.5B) |
| LLM Routing | Requests + custom fallback chain |
| Frontend (Primary) | Next.js 14, React, Tailwind CSS, Framer Motion, GSAP |
| Frontend (Fallback) | Single-file HTML/CSS/JS (zero build) |
| Audio Processing | pydub, scipy.io.wavfile |
| Model Hub | HuggingFace Hub (auto-download on first use) |

## File Structure

```
podcast-brain-pro/
├── README.md
├── LICENSE
├── docs/
│   ├── SETUP.md
│   ├── API_KEYS.md
│   ├── ARCHITECTURE.md
│   └── CONTRIBUTING.md
├── voice-service/
│   ├── main.py                      # FastAPI app + endpoints
│   ├── rss_generator.py             # RSS feed generator
│   ├── requirements.txt             # Python dependencies
│   ├── start.sh                     # Startup script
│   └── .env.example                 # Example environment config
├── frontend/                        # React/Next.js app
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── package.json
└── vibevoice-src/                   # Local VibeVoice package (pip install -e .)
    └── ...
```

## Model Downloads

VibeVoice models are **not shipped in the repository**. They are downloaded automatically from HuggingFace on first request:

| Model | Parameters | Download Size | Cache Location |
|-------|------------|---------------|----------------|
| VibeVoice Realtime | 0.5B | ~2 GB | `~/.cache/huggingface/hub/` |
| VibeVoice TTS | 1.5B | ~5.4 GB | `~/.cache/huggingface/hub/` |
| VibeVoice ASR | 7B | ~14 GB | `~/.cache/huggingface/hub/` |

This keeps the git repository lightweight (~1 MB) while providing state-of-the-art local TTS. Users need internet only for the first download.

## Audio Engine Selection

The frontend automatically picks the right TTS engine:

| Format | Duration | Language | Engine | Speed on M4 |
|--------|----------|----------|--------|-------------|
| Monologue | ≤10 min | English | Realtime 0.5B | ~30–90s |
| Monologue | >10 min | English | Longform 1.5B | ~5–15 min |
| Interview/Panel | Any | English | Longform 1.5B | ~5–15 min |
| Any | Any | Indian | Sarvam Bulbul v3 | ~30–90s |

## LLM Fallback Chain

`llm_chat()` in `main.py` tries providers in order until one succeeds:

1. Dialogram (`qwen-3.6-plus`)
2. GitHub Models (`gpt-4o`)
3. Groq (`llama-3.3-70b`)
4. DeepSeek
5. Ollama (local)
6. Gemini
7. Mistral
8. Together AI
9. OpenRouter

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI (HTML fallback) |
| `/health` | GET | Device status & loaded models |
| `/config` | GET/POST | API key management |
| `/podcast/generate` | POST | Research + script generation |
| `/podcast/history` | GET | List generated episodes |
| `/tts/realtime` | POST | Single-speaker fast TTS |
| `/tts/longform` | POST | Multi-speaker high-quality TTS |
| `/tts/sarvam` | POST | Indian-language cloud TTS |
| `/asr` | POST | Speech-to-text transcription |

## Concurrency & Safety

The backend uses several mechanisms to ensure stable operation under load:

| Mechanism | Purpose |
|-----------|---------|
| `_tts_generation_lock` | Serializes all `model.generate()` calls to prevent DPMSolver scheduler race conditions |
| `_tts_executor` (ThreadPoolExecutor, max_workers=2) | Offloads sync inference from the async event loop — prevents frontend timeouts |
| Per-model load locks (`_realtime_load_lock`, `_asr_load_lock`, `_longform_load_lock`) | Prevents concurrent model initialization races |
| `_mps_cleanup()` | Flushes MPS memory cache after every inference to prevent GPU memory leaks |
| `gc.collect()` (conditional on MPS) | Runs garbage collection only on Apple Silicon where it helps |

## Security Notes

- API keys are read from environment variables or a local `user_config.json` file.
- Keys are **masked** in the `/config` endpoint (only first/last 4 chars shown).
- Empty/None speaker names are filtered out before regex processing.
- Path traversal is prevented in metadata file operations (`os.path.splitext` instead of string replacement).
- No telemetry or tracking is implemented.
