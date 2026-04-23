# 🎙️ Podcast Brain Pro

> Open-source AI podcast factory. Generate research-backed scripts instantly. Synthesize multi-speaker audio locally on your Apple Silicon Mac or NVIDIA GPU.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)]()
[![Next.js](https://img.shields.io/badge/Next.js-000?logo=next.js&logoColor=white)]()

---

## ✨ What It Does

1. **Enter a topic** — "The future of quantum computing"
2. **Choose format** — Solo monologue, two-person interview, or three-person panel
3. **Pick language** — English or 10 Indian languages (Hindi, Tamil, Telugu, Kannada, Bengali, Marathi, Gujarati, Malayalam, Punjabi, Odia)
4. **Generate script** — AI researches and writes a natural, conversational script (~10–30s)
5. **Generate audio** — Local VibeVoice TTS turns it into studio-quality podcast audio

---

## 🚀 Quick Start (Local Setup)

### Prerequisites
- **macOS** with Apple Silicon (M1/M2/M3/M4) or **Linux/Windows** with NVIDIA GPU
- **Python 3.10+**
- **Node.js 18+**
- **~15 GB free disk space** for model downloads
- **Git**

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/podcast-brain-pro.git
cd podcast-brain-pro
```

### 2. Install backend

```bash
cd voice-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install the vibevoice package (required, not on PyPI)
cd ../vibevoice-src
pip install -e .
cd ../voice-service
```

### 3. Configure API keys

```bash
cp .env.example .env
# Edit .env and add at least one LLM provider key:
# - DIALOGRAM_API_KEY (recommended, free tier)
# - GITHUB_TOKEN (GitHub Models, free GPT-4o)
# - GROQ_API_KEY (optional fallback)
```

### 4. Start the backend

```bash
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8766
```

### 5. Start the frontend (new terminal)

```bash
cd podcast-brain-pro/frontend
npm install
npm run dev
```

Open **http://localhost:3000**

---

## 📦 Model Downloads (Automatic)

On the first audio generation, VibeVoice models download automatically from HuggingFace:

| Model | Size | Time | Use Case |
|-------|------|------|----------|
| VibeVoice Realtime 0.5B | ~2 GB | ~2–5 min | English monologue ≤10 min |
| VibeVoice Longform 1.5B | ~5.4 GB | ~5–10 min | Multi-speaker / >10 min |
| VibeVoice ASR 7B | ~14 GB | ~10–15 min | Speech-to-text (optional) |

**Cache location:** `~/.cache/huggingface/hub/`

---

## 🏗️ Project Structure

```
podcast-brain-pro/
├── frontend/              # Next.js 14 + React + Tailwind CSS
│   ├── app/page.tsx       # Main UI
│   └── components/ui/     # Buttons, cards, modals, badges
├── voice-service/         # FastAPI backend
│   ├── main.py            # API endpoints, TTS, LLM fallbacks
│   ├── rss_generator.py   # RSS feed generator
│   ├── requirements.txt   # Python dependencies
│   ├── start.sh           # Startup script
│   └── .env.example       # API key template
├── vibevoice-src/         # Microsoft VibeVoice package (install with pip -e)
└── docs/                  # Setup, architecture, API keys, contributing
```

---

## 🔑 API Keys

Podcast Brain Pro uses a **fallback chain** of free-tier LLM providers.

**Recommended primary:** [Dialogram](https://dialogram.me/) (`qwen-3.6-plus`) — free tier available

**Free fallbacks:** GitHub Models (`gpt-4o`), Groq, Cerebras, Gemini, Mistral, NVIDIA, Together AI, OpenRouter

**For Indian languages:** [Sarvam AI](https://www.sarvam.ai/) — free tier for TTS

Keys are saved locally in `voice-service/user_config.json`.

---

## ⚡ Audio Engine Speeds

| Engine | Format | Language | Speed on M4 Mac |
|--------|--------|----------|-----------------|
| **Realtime 0.5B** | Monologue ≤10 min | English | ~30–90s |
| **Longform 1.5B** | Interview / Panel / >10 min | English | ~5–15 min |
| **Sarvam Bulbul v3** | Any | Indian languages | ~30–90s |

---

## 🖼️ Screenshots

See `docs/screenshots/` for UI screenshots.

---

## 🤝 Contributing

We welcome contributions! Priority areas:
- CUDA support for NVIDIA GPUs
- Faster multi-speaker TTS stitching
- Additional language support
- UI/UX improvements

---

## 📄 License

[MIT License](./LICENSE)

---

## 🙏 Acknowledgments

- [Microsoft VibeVoice](https://github.com/microsoft/vibevoice) for the TTS models
- [Dialogram](https://dialogram.me/) for the Qwen 3.6 API
- [FastAPI](https://fastapi.tiangolo.com/) and [Next.js](https://nextjs.org/) for the stack
