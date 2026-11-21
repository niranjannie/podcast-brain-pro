# Local TTS with VibeVoice (private, on the user's own machine)

This is the path that keeps audio generation local: no cloud TTS, no per-minute billing,
nothing leaves the machine. It is also the heaviest path - roughly 15 GB of models and a
GPU-class machine - so check the prerequisites before you start.

## Prerequisites

- macOS on Apple Silicon (M1-M4), or Linux/Windows with an NVIDIA GPU
- Python 3.10+
- ~15 GB free disk for model weights
- Source: https://github.com/niranjannie/podcast-brain-pro (MIT)

## Setup

```bash
git clone https://github.com/niranjannie/podcast-brain-pro.git
cd podcast-brain-pro

cd voice-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ../vibevoice-src && pip install -e . && cd ../voice-service

cp .env.example .env     # add at least one LLM provider key for script generation

source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

Then:

```bash
curl http://localhost:8000/health
```

## Voices

Longform voices live in `vibevoice-src/demo/voices` (`.wav` reference clips).
Streaming voices live in `vibevoice-src/demo/voices/streaming_model` (`.pt` files).

Longform reference clips currently shipped:

| file | voice |
|---|---|
| `en-Alice_woman.wav` | Alice (en, woman) |
| `en-Carter_man.wav` | Carter (en, man) |
| `en-Frank_man.wav` | Frank (en, man) |

Streaming model voices include `en-Carter_man`, `en-Davis_man`, `en-Emma_woman`,
`en-Frank_man`, `en-Grace_woman`, `en-Mike_man`, plus `de`, `fr`, `in-Samuel_man`,
`it`, `jp`, `kr`, `nl`, `pl`, `pt`, `sp` variants.

Override the directories with `VOICES_DIR` and `LONGFORM_VOICES_DIR` if you keep the
models elsewhere.

## Longform TTS request

```
POST /tts/longform
Content-Type: application/json
```

```json
{
  "script": [
    { "role": "Host", "content": "Welcome back to the show..." },
    { "role": "Guest", "content": "Thanks for having me..." }
  ],
  "voice_names": ["en-Carter_man", "en-Alice_woman"],
  "cfg_scale": 1.3,
  "save_to_disk": true,
  "topic": "my episode",
  "format": "interview",
  "language": "en"
}
```

The response is `audio/wav` streamed back, with headers `X-Saved-Filename`,
`X-Chunks-Used`, and `X-Gen-Time-Sec`.

Important: the TTS endpoints read the speaker name from the **`role`** key of each turn
(`item.get("role", ...)`). The script generator returns the same data under **`speaker`**.
If you pipe generator output straight into `/tts/longform`, every turn falls back to
`Speaker 1`, `Speaker 2`, ... and the voice mapping is wrong. Rename the key before
calling:

```python
turns = [{"role": t["speaker"], "content": t["content"]} for t in script]
```

`voice_names` must be in the same order as the turns' speakers, one voice per speaker.

## Single turn

```
POST /tts/realtime
```

```json
{ "text": "One sentence to speak.", "speaker_name": "Carter", "cfg_scale": 1.5, "save_to_disk": false }
```

## Chunking limits

Longform synthesis splits text into chunks at sentence boundaries, so long episodes are
stitched from multiple passes. Defaults: 350 words per chunk on MPS, 300 on CPU
(`MAX_LONGFORM_WORDS_MPS`, `MAX_LONGFORM_WORDS_CPU`). Lower values reduce RAM but
increase stitch gaps. Lower `LONGFORM_DDPM_STEPS` (default 5) to go faster at some
quality cost.

## Optional cloud TTS for Indian languages

`POST /tts/sarvam` with `SARVAM_API_KEY` set gives Sarvam voices for Hindi, Tamil,
Telugu, Kannada, Bengali, Marathi, Gujarati, Malayalam, Punjabi and Odia. It falls back
to local VibeVoice when the call fails. Use this when the user needs an Indian language
and does not want to wait for a local model.

## RSS feed

`GET /feed/podcast.rss` returns the RSS feed built from the episodes saved under the
output directory. It carries the title, description, publication date, duration and an
enclosure per episode, so the same feed can be pointed at any podcast host.
