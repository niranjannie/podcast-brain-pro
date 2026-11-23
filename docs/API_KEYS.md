# API Keys & Providers

Podcast Brain Pro uses a **fallback chain** for script generation. If the primary provider fails, it automatically tries the next one.

## Current Fallback Order

1. **Dialogram** (`qwen-3.6-plus`) — third-party router, no public API docs
2. **Groq** (`openai/gpt-oss-20b`) — very fast, generous free-tier rate limit
3. **DeepSeek** (`deepseek-v4-flash`) — verified, free tier
4. **Ollama** (local, no key needed)
5. **Gemini** (`gemini-2.5-flash`)
6. **Mistral** (`mistral-small-latest`)
7. **Together AI**
8. **OpenRouter** (a free model is picked from the live catalogue)

Providers retire model ids. Every id below can be overridden with an environment
variable, so a retirement is a one line change:

```bash
GROQ_MODEL=openai/gpt-oss-20b
DEEPSEEK_MODEL=deepseek-v4-flash
GEMINI_MODEL=gemini-2.5-flash
MISTRAL_MODEL=mistral-small-latest
TOGETHER_MODEL=together_ai/deepseek-ai/DeepSeek-V4.1-Flash-1017
DIALOGRAM_MODEL=qwen-3.6-plus
OPENROUTER_MODEL=some/model:free
```

## Retired Providers

| Provider | Status | What to use instead |
|---|---|---|
| GitHub Models (`models.inference.ai.azure.com`) | Inference API retired, 30 Jul 2026 | Any remaining provider in the chain |
| Groq `llama-3.3-70b-versatile` | Model shut down, 16 Aug 2026 | `openai/gpt-oss-20b` (default) or `openai/gpt-oss-120b` |
| Gemini `gemini-2.0-flash` | Model retired, 1 Jun 2026 | `gemini-2.5-flash` or `gemini-3-flash` |
| DeepSeek `deepseek-chat` | Legacy alias discontinued, 24 Jul 2026 | `deepseek-v4-flash` |
| OpenRouter `mistralai/mistral-7b-instruct:free` | No provider left for that id | Any `:free` id, or set `OPENROUTER_MODEL` |

## Free-Tier Providers

### Dialogram (First in the Chain)
- **Model:** `qwen-3.6-plus` (Alibaba)
- **Why:** Huge context, excellent creative writing, generous free tier
- **Get key:** https://dialogram.me/
- **Note:** This is a third party router with no public API docs. Treat it as a
  convenience, not a guarantee, and keep a second provider key configured.

### Groq (Recommended — Verified)
- **Model:** `openai/gpt-oss-20b`
- **Why:** Blazing fast inference, 131k context, and the 20b model is small enough
  to stay well inside the free-tier rate limit
- **Caveat:** `openai/gpt-oss-120b` also works and writes slightly better, but it is
  slower and burns the rate limit faster. Daily rate limits can still be exhausted
  on a heavy run.
- **Get key:** https://console.groq.com/keys

### Google AI Studio
- **Model:** `gemini-2.5-flash`
- **Get key:** https://aistudio.google.com/api-keys

### Together AI
- **URL:** https://api.together.ai/settings/api-keys

### Mistral AI
- **URL:** https://console.mistral.ai/home

### OpenRouter
- **Why:** Universal fallback. The app reads the live model catalogue and picks a free
  model that is actually routable, instead of hard coding an id that silently dies.
- **URL:** https://openrouter.ai/settings/keys

### DeepSeek
- **URL:** https://platform.deepseek.com/api_keys

### Ollama (fully local)
- **Why:** No key, no cost, no data leaving the machine. Good for private topics.
- **Default model:** `qwen3:8b` (set `OLLAMA_MODEL` to change)
- **URL:** https://ollama.com/

## Optional: Indian-Language TTS

### Sarvam AI
- **What:** TTS for Hindi, Tamil, Telugu, Kannada, Bengali, Marathi, Gujarati, Malayalam, Punjabi, Odia
- **Requires:** Valid `SARVAM_API_KEY`
- **Get key:** https://dashboard.sarvam.ai/
- **Models:**
  - `bulbul:v3` — the default, speaker names like `shubh`
  - `bulbul:v4-flash` — newer, 200+ styled voices, adds `pitch`, `loudness` and
    pronunciation dictionaries (`dict_id`). Persona ids on v4 look like
    `shubh_enhi_ads`; the short v3 ids are rejected by v4 and vice versa.
- **Language codes:** Sarvam uses ISO 639-1, so Odia is `or-IN`. The app accepts
  `od-IN` and maps it for you.

## Optional: Research

### Tavily
- **What:** Live web research before script generation
- **Get key:** https://app.tavily.com/home
- **Note:** An `advanced` search costs 2 credits, the free tier is 1,000 credits a month.

---

## Local voice engines (no API key)

Kokoro, Qwen3-TTS, and Chatterbox run locally. Install Kokoro in the main environment;
for Qwen/Chatterbox on Apple Silicon use `.venv-mlx` and `requirements-mlx.txt` as shown in
`docs/SETUP.md`. Qwen cloning requires a reference transcript; every clone requires consent.
VibeVoice loads only when selected unless `LONGFORM_PRELOAD_AT_STARTUP=true`.

## Configuring Keys

You have two options:

### Option A: Environment variables (recommended for servers)
Create a `.env` file in `voice-service/`:

```bash
DIALOGRAM_API_KEY=your_key
GROQ_API_KEY=your_key
SARVAM_API_KEY=your_key
```

### Option B: Web UI (recommended for local testing)
1. Open http://localhost:8000
2. Click **⚙️ Settings**
3. Paste keys into the relevant fields
4. Click **Save Changes**

Keys saved via the UI are stored locally in `user_config.json` and are **never sent to any external server** except the provider itself.
