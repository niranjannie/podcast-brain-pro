# AI_VOICEVIBE Voice Service

> The FastAPI backend for Podcast Brain Pro: script generation, four local speech
> engines, the Sarvam Indic path, and the RSS feed.

## Quick Start

```bash
# 1. Start the server
cd voice-service
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000
```

The server runs at `http://localhost:8000`. There is a startup script too:

```bash
./start.sh
```

> Bind to `127.0.0.1`. The service has no authentication: `/config` returns masked keys
> and lets a client change them, and `/outputs` serves your episodes. Only set
> `HOST=0.0.0.0` on a network you trust.

## Two environments, on purpose

| Environment | Python | `transformers` | Engines |
|---|---|---|---|
| `.venv` | 3.12 | `<5` | VibeVoice, Kokoro, Sarvam |
| `.venv-mlx` | 3.12 | `>=5.14` | Qwen3-TTS, Chatterbox |

`mlx-audio` needs `transformers>=5.14` and the vendored VibeVoice breaks at import on
transformers 5, so they cannot share one environment. The parent process talks to the
MLX engines over a pipe, so `mlx_worker.py` runs under the other interpreter and the
main process never imports MLX itself.

```bash
python3.12 -m venv .venv-mlx
.venv-mlx/bin/pip install -r requirements-mlx.txt
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service page |
| `/health` | GET | Device status and loaded models |
| `/models/status` | GET | Which models are cached or loaded, device and limits |
| `/voices` | GET | VibeVoice presets, consented cloned voices, delivery styles |
| `/engines` | GET | Engine licences, install state, runtime health, preset voices |
| `/config` | GET/POST | API key management |
| `/podcast/generate` | POST | Research + script + optional content extras |
| `/podcast/extras` | POST | Refresh extras without rewriting the script |
| `/podcast/history` | GET | List generated episodes |
| `/podcast/rename` | POST | Rename a saved episode |
| `/podcast/delete` | DELETE | Delete a saved episode |
| `/feed/podcast.rss` | GET | Podcast feed with transcript, chapters and AI disclosure |
| `/tts/realtime` | POST | Single-speaker VibeVoice TTS |
| `/tts/engine` | POST | Kokoro / Qwen3-TTS / Chatterbox single-voice preview |
| `/tts/clone` | POST | Consent-gated Qwen3-TTS / Chatterbox cloning |
| `/tts/longform` | POST | Multi-speaker VibeVoice / Kokoro / Qwen3-TTS / Chatterbox TTS |
| `/tts/sarvam` | POST | Single- or multi-speaker Indian-language cloud TTS |
| `/asr/transcribe` | POST | Speech-to-text transcription |

## Frontend

The primary interface is a Next.js 14 app in `../frontend/`:

```bash
cd ../frontend
npm install
npm run dev
```

Open **http://localhost:3000**. The frontend proxies API calls to the backend.

## Models

Models download automatically from HuggingFace on first use of each engine:

| Engine | Download | Notes |
|---|---|---|
| Kokoro 82M | ~300 MB | CPU is enough |
| Qwen3-TTS 1.7B | ~2 GB per 8-bit model | CustomVoice and Base |
| Chatterbox Multilingual v3 | ~1–2 GB | Clone-only, needs a reference recording |
| VibeVoice Realtime 0.5B | ~2 GB | Single-speaker English |
| VibeVoice Longform 1.5B | ~5.4 GB | Multi-speaker English |
| VibeVoice ASR 7B | ~14 GB | Optional, large |

On a 24 GB M4 Mac all three VibeVoice models can run, though ASR is large.

### Model Status Endpoint

Check which models are cached on disk and loaded in memory:

```bash
curl -s http://localhost:8000/models/status | python3 -m json.tool
```

Response:

```json
{
  "realtime": { "cached": true, "loaded": true, "cache_size_mb": 2048 },
  "longform": { "cached": true, "loaded": true, "cache_size_mb": 5530 },
  "asr": { "cached": false, "loaded": false, "cache_size_mb": 0 }
}
```

### Preloading

Models load lazily on first use, so the backend starts immediately and the first
generation waits for the download. Set these to preload instead:

| Variable | Default | Effect |
|---|---|---|
| `LONGFORM_PRELOAD_AT_STARTUP` | `false` | Preload the 5.4 GB longform TTS at startup |
| `ASR_PRELOAD_AT_STARTUP` | `false` | Preload the 14 GB ASR model at startup (large, opt-in) |

If a model is not cached, the first request triggers the download. The backend stays
responsive while it happens; audio generation waits for it to finish. Check
`/models/status` or watch the **Ready** badge in the studio.

## AI disclosure

Every saved episode opens with a spoken AI disclosure, in the episode's language, and
the feed and episode metadata carry the machine-readable marking. Article 50 of the EU
AI Act requires this for synthetic audio from 2 August 2026. Set `AI_DISCLOSURE=false`
to turn it off — do not do that if you publish the episodes.
