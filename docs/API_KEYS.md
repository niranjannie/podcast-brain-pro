# API Keys & Providers

Podcast Brain Pro uses a **fallback chain** for script generation. If the primary provider fails, it automatically tries the next one.

## Current Fallback Order

1. **Dialogram** (`qwen-3.6-plus`) — recommended primary
2. **GitHub Models** (`gpt-4o`) — free, reliable
3. **Groq** (`llama-3.3-70b`) — very fast, rate-limited
4. **DeepSeek** → **Gemini** → **Mistral** → **Together** → **OpenRouter**

## Free-Tier Providers

### Dialogram (Primary — Recommended)
- **Model:** `qwen-3.6-plus` (Alibaba)
- **Why:** Huge context, excellent creative writing, generous free tier
- **Get key:** https://dialogram.me/

### GitHub Models
- **Model:** `gpt-4o`
- **Why:** Completely free GPT-4o via Azure
- **Get key:** https://github.com/settings/tokens (classic token with no scopes)

### Groq
- **Model:** `llama-3.3-70b-versatile`
- **Why:** Blazing fast inference
- **Caveat:** Daily rate limits can be exhausted quickly
- **Get key:** https://console.groq.com/keys

### Cerebras
- **Why:** Good Groq backup, claims fastest inference
- **URL:** https://cloud.cerebras.ai/

### Google AI Studio
- **Model:** `gemini-2.0-flash`
- **Get key:** https://aistudio.google.com/api-keys

### NVIDIA Build
- **Why:** Free API keys for NVIDIA-hosted models
- **URL:** https://build.nvidia.com/

### Together AI
- **URL:** https://api.together.ai/settings/api-keys

### Mistral AI
- **URL:** https://console.mistral.ai/home

### Moonshot AI
- **Why:** 200K+ context window
- **URL:** https://platform.moonshot.ai

### OpenRouter
- **Why:** Universal fallback with dozens of models
- **URL:** https://openrouter.ai/settings/keys

### DeepSeek
- **URL:** https://platform.deepseek.com/api_keys

## Optional: Indian-Language TTS

### Sarvam AI
- **What:** TTS for Hindi, Tamil, Telugu, Kannada, Bengali, Marathi, Gujarati, Malayalam, Punjabi, Odia
- **Requires:** Valid `SARVAM_API_KEY`
- **Get key:** https://dashboard.sarvam.ai/

## Optional: Research

### Tavily
- **What:** Live web research before script generation
- **Get key:** https://app.tavily.com/home

---

## Configuring Keys

You have two options:

### Option A: Environment variables (recommended for servers)
Create a `.env` file in `voice-service/`:

```bash
DIALOGRAM_API_KEY=your_key
GITHUB_PERSONAL_ACCESS_TOKEN=your_token
SARVAM_API_KEY=your_key
```

### Option B: Web UI (recommended for local testing)
1. Open http://localhost:8000
2. Click **⚙️ Settings**
3. Paste keys into the relevant fields
4. Click **Save Changes**

Keys saved via the UI are stored locally in `user_config.json` and are **never sent to any external server** except the provider itself.
