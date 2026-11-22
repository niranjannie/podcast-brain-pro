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
| Backend | Python 3.12 recommended, FastAPI, Uvicorn |
| TTS | VibeVoice, Kokoro, Qwen3-TTS/Chatterbox via isolated MLX worker, Sarvam |
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
│   ├── script_pipeline.py           # Turns, directives, chapter-aware planning, voices
│   ├── content_pipeline.py          # Show notes, chapters, captions, social clip plans
│   ├── engines.py                   # Engine catalogue + persistent MLX worker client
│   ├── mlx_worker.py                # Qwen3-TTS/Chatterbox in isolated .venv-mlx
│   ├── audio_pipeline.py            # Loudness, PCM stitching, WAV duration
│   ├── requirements.txt             # Main/VibeVoice Python dependencies
│   ├── requirements-mlx.txt         # Isolated current MLX Audio dependencies
│   ├── rss_generator.py             # RSS + transcript/chapter links
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

The Create view exposes the installed, healthy engines. VibeVoice remains the original
English workflow; Kokoro/Qwen/Chatterbox render per turn through `/tts/longform`, while
Sarvam renders Indian-language turns with per-speaker voices.

| Selection | Language | Path |
|-----------|----------|------|
| VibeVoice Realtime 0.5B | English monologue ≤10 min | `/tts/realtime` |
| VibeVoice Longform 1.5B | English multi-host or >10 min | `/tts/longform` |
| Kokoro / Qwen3-TTS / Chatterbox | Supported local languages, mono or multi-host | `/tts/engine` preview or `/tts/longform` dialogue |
| Sarvam Bulbul | Indian languages, mono or multi-host | `/tts/sarvam` |

Qwen/Chatterbox use a persistent subprocess in `.venv-mlx`; the main process retains
VibeVoice's incompatible `transformers<5` dependency. Models stay loaded between calls.

## LLM Fallback Chain

`llm_chat()` in `main.py` tries providers in order until one succeeds. Every model id can
be overridden with an environment variable (`GROQ_MODEL`, `GEMINI_MODEL`, ...), so a
retired id is a config change, not a code change:

1. Dialogram (`qwen-3.6-plus`)
2. Groq (`openai/gpt-oss-120b`)
3. DeepSeek (`deepseek-v4-flash`)
4. Ollama (local, `qwen3:8b` by default)
5. Gemini (`gemini-2.5-flash`)
6. Mistral (`mistral-small-latest`)
7. Together AI (`together_ai/deepseek-ai/DeepSeek-V4.1-Flash-1017`)
8. OpenRouter (a free model picked from the live catalogue)

GitHub Models was removed from the chain: its inference API was retired on 30 Jul 2026.

## Script Contract

`script_pipeline.py` owns everything that turns a script into something the TTS layer
understands:

- `normalize_turns()` accepts a turn keyed `speaker` or `role` and normalises it once.
- `build_units()` assigns global speaker numbers and source turn indexes that never change between chunks.
- Delivery directives: `[[pause:0.8]]` (real silence) and `[[style:calm]]` (delivery
  settings), applied on VibeVoice, optional local engines, and Sarvam.
- Chapter start turns force generation-segment boundaries, so measured segment durations
  produce real chapter timestamps.

`content_pipeline.py` validates one LLM-generated metadata pass into show notes, chapters,
five captions, and source-grounded clip turn ranges. `/podcast/extras` refreshes that data
without rewriting the script.

`audio_pipeline.py` normalises exports to -16 LUFS with a -1.5 dBTP ceiling, stitches valid
PCM WAVs, and measures actual frame durations.

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI (HTML fallback) |
| `/health` | GET | Device status & loaded models |
| `/voices` | GET | VibeVoice presets, consented cloned voices, delivery styles |
| `/engines` | GET | Engine licences, install state, runtime health, preset voices |
| `/config` | GET/POST | API key management |
| `/podcast/generate` | POST | Research + script + optional content extras |
| `/podcast/extras` | POST | Refresh extras without rewriting the script |
| `/podcast/history` | GET | List generated episodes |
| `/tts/realtime` | POST | Single-speaker VibeVoice TTS |
| `/tts/engine` | POST | Kokoro/Qwen/Chatterbox single-voice preview |
| `/tts/clone` | POST | Consent-gated Qwen/Chatterbox cloning |
| `/tts/longform` | POST | Multi-speaker VibeVoice/Kokoro/Qwen/Chatterbox TTS |
| `/tts/sarvam` | POST | Single- or multi-speaker Indian-language cloud TTS |
| `/asr` | POST | Speech-to-text transcription |

## Concurrency & Safety

The backend uses several mechanisms to ensure stable operation under load:

| Mechanism | Purpose |
|-----------|---------|
| `_tts_generation_lock` | Serializes all `model.generate()` calls to prevent DPMSolver scheduler race conditions |
| Persistent `MLXWorker` | Serializes Qwen/Chatterbox requests over a clean JSON channel, caches models, and terminates/restarts failed workers |
| `_tts_executor` (ThreadPoolExecutor, max_workers=2) | Offloads sync inference from the async event loop — prevents frontend timeouts |
| Per-model load locks (`_realtime_load_lock`, `_asr_load_lock`, `_longform_load_lock`) | Prevents concurrent model initialization races |
| `_mps_cleanup()` | Flushes MPS memory cache after every inference to prevent GPU memory leaks |
| `gc.collect()` (conditional on MPS) | Runs garbage collection only on Apple Silicon where it helps |

## Security Notes

- API keys are read from environment variables or a local `user_config.json` file.
- Keys are **masked** in the `/config` endpoint (only first/last 4 chars shown).
- Empty/None speaker names are filtered out before regex processing.
- Path traversal is prevented in metadata file operations (`os.path.splitext` instead of string replacement).
- Voice cloning requires explicit consent and stores a consent record; reference IDs resolve only to existing consented records, with basename path containment.
- No telemetry or tracking is implemented.
