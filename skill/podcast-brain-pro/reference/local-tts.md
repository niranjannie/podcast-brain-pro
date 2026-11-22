# Local TTS with Podcast Brain Pro

The service separates script generation from audio synthesis. VibeVoice, Kokoro,
Qwen3-TTS, and Chatterbox can run locally; Sarvam is the hosted Indic-language path.
Models are downloaded only when selected. Current MLX Audio needs dependencies that
conflict with VibeVoice, so Qwen/Chatterbox use an isolated, persistent worker.

## Prerequisites

- macOS Apple Silicon for Qwen3-TTS/Chatterbox MLX; VibeVoice also supports CUDA
- Python 3.12 and Node.js 18+
- ffmpeg for loudness normalization and compressed Sarvam codecs
- espeak-ng for Kokoro (`brew install espeak-ng` on macOS)

## Main application setup

```bash
git clone https://github.com/niranjannie/podcast-brain-pro.git
cd podcast-brain-pro/voice-service
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e ../vibevoice-src
.venv/bin/pip install kokoro
cp .env.example .env  # configure a script provider and optional Sarvam key
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

VibeVoice loads lazily on first use. Set `LONGFORM_PRELOAD_AT_STARTUP=true` only if you
intentionally want to preload its 1.5B model at startup.

## Qwen3-TTS and Chatterbox MLX setup

Keep this environment separate from the main environment:

```bash
cd voice-service
python3.12 -m venv .venv-mlx
.venv-mlx/bin/pip install -r requirements-mlx.txt
```

The app finds `.venv-mlx/bin/python` automatically. Override with `MLX_AUDIO_PYTHON`.
The worker starts on first use and keeps models loaded between requests.

Defaults:

- Qwen presets/style: `mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit`
- Qwen cloning: `mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit`
- Chatterbox cloning: `mlx-community/chatterbox-multilingual-v3`

Override them with `QWEN3_TTS_MODEL`, `QWEN3_TTS_BASE_MODEL`, and
`CHATTERBOX_MLX_MODEL`. Qwen supports English, Chinese, Japanese, Korean, German,
French, Russian, Portuguese, Spanish, and Italian—not Indian languages.

## Voices and multi-host episodes

`GET /voices` returns VibeVoice presets and consented cloned voices. `GET /engines`
returns install/runtime health, model cost, licences, voices, and cloning support.

`POST /tts/longform` accepts the generated script directly. Both `speaker` and the
legacy `role` key are accepted; no manual key conversion is needed.

```json
{
  "script": [
    {"speaker": "Host", "content": "Welcome to the show."},
    {"speaker": "Guest", "content": "[[style:warm]] Thanks for having me."}
  ],
  "engine": "qwen3-tts",
  "voice_names": ["Ryan", "Aiden"],
  "style": "neutral",
  "language": "en",
  "save_to_disk": true,
  "topic": "my episode"
}
```

Use `engine: "vibevoice"` (the default), `"kokoro"`, `"qwen3-tts"`, or
`"chatterbox"`. Kokoro and Qwen have preset voices. Chatterbox requires consented
reference voices created through Voice Lab; Qwen can mix presets and consented clones.
The backend renders per turn and stitches real silence for `[[pause:0.8]]`.

For a single voice preview, `POST /tts/engine` accepts `{text, engine, voice,
language, style, save_to_disk}`. For VibeVoice monologues, use `/tts/realtime` with
`{text, speaker_name, style, save_to_disk}`.

## Consent-gated voice cloning

`POST /tts/clone` is multipart form data:

- `text`: new words to speak
- `engine`: `qwen3-tts` or `chatterbox`
- `reference`: 5–10 seconds of clean, single-speaker audio
- `reference_text`: exact reference transcript; **required for Qwen** so no Whisper
  model is downloaded
- `language`: for example `en`
- `consent`: must be `true`

Only clone your own voice or one for which you have written permission. The service
stores the reference and a consent record. Those voices then appear in `/voices` and
can be reused in previews and multi-host episodes.

## Indian-language conversations

`POST /tts/sarvam` requires `SARVAM_API_KEY`. In addition to the original single-text
fields, provide `script` and `voice_names` for per-turn voices:

```json
{
  "text": "Fallback plain-text form of the script",
  "script": [
    {"speaker": "Host", "content": "स्वागत है।"},
    {"speaker": "Guest", "content": "धन्यवाद।"}
  ],
  "voice_names": ["shubh", "shreya"],
  "target_language_code": "hi-IN",
  "language": "hi-IN",
  "output_audio_codec": "wav",
  "save_to_disk": true
}
```

Sarvam uses ISO 639-1 codes; the app maps Odia `od-IN` to `or-IN`. English requests can
fall back to the full VibeVoice longform pipeline with transcript/extras preserved. Indic
requests return 503 when Sarvam is unavailable instead of saving unsupported local output.

## Show notes, chapters, and social clips

- `POST /podcast/generate` with `include_extras: true` returns validated show notes,
  chapters, five captions, and up to three source-grounded social clip selections.
- `POST /podcast/extras` refreshes those extras for an existing/edited script without
  rewriting it.
- Chapter starts are measured from rendered audio and saved as
  `<episode>.chapters.json`. RSS emits `<podcast:chapters>` only when timings exist.
- Render social clips from the selected original turns; do not synthesize an LLM-written
  paraphrase as though it were part of the episode.

## Output and RSS

Saved episodes include WAV audio, metadata JSON, transcript JSON, and chapter JSON when
available. Rename and delete operations keep all sidecars together. Exports are
normalized to -16 LUFS with a -1.5 dBTP ceiling when ffmpeg is available.

`GET /feed/podcast.rss` emits transcript and chapter links. Set `PUBLIC_BASE_URL`,
channel metadata, artwork, and owner email before submitting the feed to a host.
