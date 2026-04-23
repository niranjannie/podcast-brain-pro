# Setup Guide

> Get Podcast Brain Pro running on your local machine in under 10 minutes.

---

## Requirements

- **macOS** with Apple Silicon (M1/M2/M3/M4) — for local VibeVoice TTS
- **Python 3.10+**
- **Node.js 18+** — if you want the React frontend
- **~10–15 GB free disk space** — for VibeVoice model downloads
- **API keys** for script generation (see [API_KEYS.md](./API_KEYS.md))

### ⚠️ Hardware Requirements (Critical)

| Config | RAM | Result |
|--------|-----|--------|
| **Minimum** | 24 GB | Works for 3–5 min scripts with chunking. 10+ min possible but slow (~15–25 min gen time). Close other heavy apps first. |
| **Recommended** | 32+ GB | Reliable 5–10 min generation with fewer chunks. |
| **Ideal** | 48+ GB or CUDA GPU | No chunking needed; fastest generation. |

**Why?** The VibeVoice-TTS-1.5B model uses a diffusion-based generation process. During inference, intermediate activation tensors spike memory to **18–22 GB** regardless of model weight precision. This is a fundamental property of the architecture, not a bug. We mitigated it with:

- `float16` weights (reduces idle memory from ~23 GB → ~7 GB)
- **Auto-chunking**: scripts >350 words (MPS) or >300 words (CPU) are split into memory-safe segments, generated separately, and stitched with 400 ms silence gaps.
- **Reduced diffusion steps**: Default lowered from 10 → 5 steps for longform on Apple Silicon. This roughly halves generation time while keeping quality acceptable.
- **MPS memory flush**: Explicit `torch.mps.empty_cache()` and Python `gc.collect()` run after every chunk and after generation completes.
- **Non-blocking generation**: Longform TTS now runs in a dedicated thread pool so the FastAPI server remains responsive during 10+ minute generations (fixes frontend "socket hang up" errors).
- Per-request logging to `logs/audio_generation.log` for diagnosis.

> **Before generating 5+ minute audio:** Close Chrome, VS Code, and other memory-heavy apps. Activity Monitor should show ≤10 GB "Memory Used" before you start.

---

## What Gets Downloaded?

VibeVoice TTS models are **not bundled in the repo**. They download automatically from HuggingFace on your first audio generation request:

| Model | Size | Typical Download | Cached Location |
|-------|------|------------------|-----------------|
| VibeVoice Realtime 0.5B | ~2 GB | ~2–5 min | `~/.cache/huggingface/hub/` |
| VibeVoice TTS 1.5B | ~5.4 GB | ~5–10 min | `~/.cache/huggingface/hub/` |
| VibeVoice ASR 7B | ~14 GB | ~10–15 min | `~/.cache/huggingface/hub/` |

> **Tip:** You only need internet for the first download. After that, models are cached locally and load instantly.

### Model Preloading at Startup

By default, the backend **preloads the Longform 1.5B model in a background thread** at startup (`LONGFORM_PRELOAD_AT_STARTUP=true`). This prevents HTTP request timeouts during your first multi-speaker audio generation. The model downloads from HuggingFace if not already cached.

| Environment Variable | Default | Effect |
|---|---|---|
| `LONGFORM_PRELOAD_AT_STARTUP` | `true` | Preload 5.4GB longform TTS on startup |
| `ASR_PRELOAD_AT_STARTUP` | `false` | Preload 14GB ASR model on startup (large, opt-in) |
| `LONGFORM_DDPM_STEPS` | `5` | Diffusion steps for longform (lower = faster, 3–10 range) |
| `MAX_LONGFORM_WORDS_MPS` | `350` | Chunk size for Apple Silicon (lower = less RAM) |
| `MAX_LONGFORM_WORDS_CPU` | `300` | Chunk size for CPU-only machines |

> ⚠️ **First startup after install:** If models are not cached, the backend will appear ready immediately, but the first `/health` check will show `"loaded_models": []`. Wait 5–15 minutes for the download to complete before generating multi-speaker audio. Realtime (single-speaker) audio works as soon as the 0.5B model loads (~2 min).

---

## Step-by-Step Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/podcast-brain-pro.git
cd podcast-brain-pro
```

### 2. Create a Python virtual environment

```bash
cd voice-service
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the local `vibevoice` package

This package is **not on PyPI**. You must install it in editable mode from the included source **inside the activated virtual environment**:

```bash
cd ../vibevoice-src
pip install -e .
cd ../voice-service
```

> This installs the patched Microsoft VibeVoice Python package required for TTS and ASR.

### 4. Install backend dependencies

Still inside the activated virtual environment:

```bash
pip install -r requirements.txt
```

### 5. Configure API keys

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add at least one script-generation provider:

```bash
# Recommended primary provider (free tier available)
DIALOGRAM_API_KEY=your_dialogram_key

# Optional fallbacks
GITHUB_PERSONAL_ACCESS_TOKEN=your_github_token
GROQ_API_KEY=your_groq_key
```

You can also configure keys later via the web UI (Settings → API Keys).

### 5. Run the FastAPI backend

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The backend will be available at **http://localhost:8000**.

> 💡 **Tip:** Use the included `start.sh` script to start the backend with one command: `./start.sh`. It auto-activates the virtual environment and uses the `PORT` environment variable (defaults to 8000).

### 6. Run the React frontend (optional but recommended)

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**. The frontend automatically proxies API requests to the backend.



---

## Verify Installation

1. Open the web UI at http://localhost:3000 (or http://localhost:8766 for the HTML version)
2. Enter a topic (e.g., "The future of electric aviation")
3. Select **2 min · Monologue · English**
4. Click **Generate Script** — you should see a script in ~10–30 seconds
5. Click **Generate Audio** — the first time, the Realtime 0.5B model (~2 GB) will download. After that, audio generates in ~30–60 seconds.

If script generation fails, check that at least one LLM API key is configured.

---

## Troubleshooting

### "No module named 'vibevoice'"
You skipped step 2. Run `cd vibevoice-src && pip install -e . && cd ..`

### Download is very slow or hangs
HuggingFace downloads can be slow depending on your region. You can set a mirror:

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### Out of disk space
Models are cached in `~/.cache/huggingface/hub/`. Ensure you have at least 10–15 GB free. You can move the cache by setting:

```bash
export HF_HOME=/path/to/larger/disk
```

### Model not ready / "Internal Server Error" on first audio generation
This happens when you click **Generate Audio** before the model has finished downloading. The backend preloads models in the background at startup.

**Check model status:**
```bash
# See which models are cached and loaded
curl -s http://localhost:8000/models/status | python3 -m json.tool

# Or check disk cache directly
du -sh ~/.cache/huggingface/hub/models--microsoft--VibeVoice-*/
```

Wait for `"loaded": true` before generating audio. The UI shows a green **Ready** badge when the model is loaded.

### "MPS out of memory" on long episodes
Longform 1.5B uses significant memory. Try shorter episodes (≤5 min) or close other apps. ASR 7B is especially large (~14 GB).

If you still hit memory pressure on a 24 GB Mac:
1. Lower chunk size: `MAX_LONGFORM_WORDS_MPS=250`
2. Lower diffusion steps: `LONGFORM_DDPM_STEPS=3` (fastest, slight quality drop)
3. Restart the backend to clear MPS cache: `Ctrl+C` then `uvicorn main:app --host 0.0.0.0 --port 8000`

---

## Next Steps

- Read the [Architecture Overview](./ARCHITECTURE.md)
- Learn about [API Keys & Providers](./API_KEYS.md)
- Check out the [Contributing Guide](./CONTRIBUTING.md)
