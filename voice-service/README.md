# AI_VOICEVIBE Voice Service

> FastAPI wrapper for Microsoft VibeVoice running locally on M4 Mac (24GB)

## Quick Start

```bash
# 1. Start the server
cd voice-service
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8766
```

Server runs at `http://localhost:8766`

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Root endpoint (health check fallback) |
| `GET /health` | Service status + device info |
| `POST /tts/realtime` | VibeVoice-Realtime-0.5B (~300ms latency) |
| `POST /tts/longform` | VibeVoice-TTS-1.5B (multi-speaker, 90min) |
| `POST /asr/transcribe` | VibeVoice-ASR (60min transcription) |

## Frontend

The primary interface is a Next.js 14 app in `../frontend/`:

```bash
cd ../frontend
npm install
npm run dev
```

Open **http://localhost:3000**. The frontend proxies API calls to the backend.

## Models

Models download automatically from HuggingFace on first request:
- **Realtime 0.5B**: ~2GB download
- **TTS 1.5B**: ~5.4GB download  
- **ASR 7B**: ~14-16GB download

On a 24GB M4 Mac, all three can run (though ASR is large).

### Model Status Endpoint

Check which models are cached on disk and loaded in memory:
```bash
curl -s http://localhost:8766/models/status | python3 -m json.tool
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

By default, the backend preloads the Longform 1.5B model at startup in a background thread (`LONGFORM_PRELOAD_AT_STARTUP=true`). This prevents HTTP timeouts during your first multi-speaker audio generation.

| Variable | Default | Effect |
|---|---|---|
| `LONGFORM_PRELOAD_AT_STARTUP` | `true` | Preload 5.4GB longform TTS on startup |
| `ASR_PRELOAD_AT_STARTUP` | `false` | Preload 14GB ASR on startup (large, opt-in) |

If models are not cached, the first startup will trigger a download. The backend is immediately responsive, but audio generation will wait until the download completes. Check `/models/status` or watch the UI **Ready** badge.
