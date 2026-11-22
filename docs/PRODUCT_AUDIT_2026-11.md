# Podcast Brain Pro — Product Audit (November 2026)

> **Status update:** this is the original audit. Its open items were subsequently addressed;
> including the large-component split, real response stats, backend health, accessible modal,
> library search/load-more, stem rename, multi-host Indic rendering, and smaller landing media.
> See `docs/HANDOFF.md` for the final implementation and verification record.
Date: 2026-11-21
Scope: `voice-service/` (FastAPI backend), `frontend/` (Next.js studio + landing),
`vibevoice-src/` (vendored Microsoft VibeVoice), provider chain, and the external
stack (LLM providers, TTS providers, podcast-host requirements).

Everything marked **Verified** was reproduced in this repository or read from a primary
source during the audit. Everything marked **[INFERENCE]** is a judgement call.

---

## 1. The headline problems

| # | Problem | Impact | Status |
|---|---|---|---|
| 1 | Multi-speaker episodes gave every host the same voice | The core promise (interview / panel) did not work | **Fixed** |
| 2 | The script contract used two different key names | Turns lost their speaker on the way to TTS | **Fixed** |
| 3 | The studio UI could not be opened at all | The whole app was unreachable behind a redirect | **Fixed** |
| 4 | Saving the settings modal wiped every API key | Silent, total loss of the user's provider keys | **Fixed** |
| 5 | Two of the nine LLM providers were dead services | The fallback chain was two links shorter than it looked | **Fixed** |
| 6 | `transformers` was unpinned, so a fresh install breaks | New installs failed at import time | **Fixed** |
| 7 | Upstream deleted the VibeVoice TTS inference code | The vendored copy is now the only source | **Risk, documented** |
| 8 | The RSS feed pointed at `localhost` | The feed could never be submitted to a podcast host | **Fixed** |
| 9 | Exports had no loudness normalisation | Episodes were rejected or sound inconsistent | **Fixed** |
| 10 | The README promised Assamese; the code supports Odia | A false claim in the listing | **Fixed** |

---

## 2. Backend findings

### 2.1 The speaker / voice bug (the important one)

**Verified.** `voice-service/main.py` read the speaker name from `item.get("role")`
in four places (the chunker, the longform voice resolver, the single-pass renderer and
the realtime fallback), while `POST /podcast/generate` returns turns keyed by
`speaker`. The frontend papered over this by rewriting each turn's speaker into the
*voice name* before sending it (`role: voiceMap[line.speaker]`), so the host names were
lost from the transcript and the voice mapping depended on the script introducing
speakers in the same order as the form.

Two more consequences, both **verified**:

- With the default cast (`Host`, `Guest`), no voice file matches those names, so every
  speaker fell back to the first `.wav` in the voices directory: **both hosts spoke with
  the same voice**.
- `voice_names` was accepted by `POST /tts/longform` and then ignored entirely.
- Speaker numbers were re-assigned per chunk (`f"Speaker {i+1}"` inside the chunk
  renderer), so a chunk that started with the second host got the first host's voice.

**Fix.** One shared module, `voice-service/script_pipeline.py`:

- `normalize_turns()` accepts `speaker` or `role` and normalises once.
- `build_units()` assigns **global** speaker numbers (1, 2, 3 … in order of first
  appearance) that never change between chunks.
- `resolve_voices()` picks, in order: an explicit `voice_names` entry, a name match
  against the voice file names, then a round robin over the remaining voices, so two
  hosts never share a voice while distinct voices exist.

Regression tests: `voice-service/test_script_pipeline.py` (23 tests, no heavy deps).

### 2.2 Dead and retired providers

**Verified** against the providers' own deprecation notes and documentation.

| Provider | Model in the code | Status | Now |
|---|---|---|---|
| GitHub Models | `gpt-4o` @ `models.inference.ai.azure.com` | Inference API retired 30 Jul 2026 | **Removed** |
| Groq | `llama-3.3-70b-versatile` | Model shut down 16 Aug 2026 | `openai/gpt-oss-120b` |
| Gemini | `gemini-2.0-flash` | Model retired 1 Jun 2026 | `gemini-2.5-flash` |
| DeepSeek | `deepseek-chat` | Legacy alias discontinued 24 Jul 2026 | `deepseek-v4-flash` |
| Together | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | Listed as deprecated | `together_ai/deepseek-ai/DeepSeek-V4.1-Flash-1017` |
| OpenRouter | `mistralai/mistral-7b-instruct:free` | No provider left for that id | picked live from the catalogue |

Every id is now an environment override (`GROQ_MODEL`, `GEMINI_MODEL`, …), so a
retirement is a config change, not a code change. The OpenRouter fallback reads
`GET /api/v1/models` at runtime and picks a `:free` model that is actually routable.

### 2.3 The `transformers` pin

**Verified, reproduced.** `requirements.txt` said `transformers>=4.51.3` with no upper
bound, so a fresh install pulls transformers 5.x. Under transformers 5 the vendored
VibeVoice fails at import:

```
ValueError: '<class 'vibevoice.modular.configuration_vibevoice.VibeVoiceAcousticTokenizerConfig'>'
is already used by a Transformers model.
```

VibeVoice's own `pyproject.toml` pins `transformers>=4.51.3,<5.0.0`. Fixed by pinning
the same range in `voice-service/requirements.txt`.

### 2.4 Output problems

- **Loudness.** Speech from a local model lands wherever it lands. Podcast hosts ask
  for -16 LUFS with a true peak of at most -1 dBTP. Now every export goes through
  `_finalize_audio()` → `audio_pipeline.normalize_loudness()` (ffmpeg `loudnorm`), and
  the measurement is stored in the episode metadata. Turn it off with
  `NORMALIZE_LOUDNESS=false`.
- **File extension.** The Sarvam path wrote the requested codec (mp3, aac, opus…) into
  a file named `.wav`. The episode library now always stores WAV, whatever codec the
  caller asked for.
- **RSS feed.** `base_url` was hard coded to `http://localhost:9876`, so every
  enclosure URL in the feed pointed at a dead port. Now `PUBLIC_BASE_URL` plus
  `PODCAST_TITLE`, `PODCAST_DESCRIPTION`, `PODCAST_AUTHOR`, `PODCAST_LANGUAGE`,
  `PODCAST_CATEGORY`.
- **Transcripts.** The backend wrote metadata JSON but never the words of the episode.
  Each longform episode now gets a `<episode>.transcript.json` sidecar and the feed
  emits a Podcasting 2.0 `<podcast:transcript>` element.

### 2.5 Smaller backend issues

- `Optional` request fields were passed straight into helpers typed as `str`/`float`:
  `cfg_scale=None` went into `model.generate()`, `speaker_name=None` hit
  `None.lower()`. Coerced at the edge now.
- `expand_script_if_needed()` returned before doing anything, leaving ~40 unreachable
  lines. It is now a real, opt-in second pass (`EXPAND_SHORT_SCRIPTS=true`).
- `vibevoice/scripts/convert_nnscaler_checkpoint_to_transformers.py` used an unsafe
  `torch.load`; upstream deleted the file for exactly that reason (CWE-502). Removed
  from the vendored copy.
- Sarvam speaks ISO 639-1 (`or-IN`); the app uses ISO 639-3 (`od-IN`). Mapped.

---

## 3. Frontend findings

The studio is a single 1900-line component (`frontend/app/page.tsx`).

| Finding | Impact | Status |
|---|---|---|
| `next.config.mjs` redirected `/` to `/landing`, which shadows the studio route | **The studio could never be opened** | Fixed: `/` is the studio, `/landing` is marketing, with an "Open the Studio" CTA |
| The settings modal seeded its inputs with the **masked** key and posted them back | Saving destroyed every configured key | Fixed: the form starts empty, the mask is a placeholder, an explicit "Remove this key" sends `null` |
| `generateScript()` had no in-flight guard and no run id | A cancelled run could clobber a newer run | Fixed: guard + monotonically increasing run id |
| Audio generation had no cancel button, and the interval leaked on unmount | A stuck job could not be stopped | Fixed: `AbortController` in a ref, Cancel button, cleanup on unmount |
| The voice list changed with the engine but the stored selection did not | The dropdown showed no valid option while a stale voice was sent | Fixed: selections are re-validated against the catalogue |
| The voice payload was pre-mapped to voice names | Host names lost, order-dependent voice swaps | Fixed: the real speaker names are sent, `voice_names` is ordered by first appearance |
| `eslint@9` + `eslint-config-next@16` with `next@14`, and no ESLint config | `npm run build` and `npm run lint` could not pass | Fixed: `next@14.2.35` (the vulnerable `14.2.5` was flagged), `eslint@8.57`, `eslint-config-next@14.2.35`, `.eslintrc.json` added |
| `next@14.2.5` | Deprecated: security advisory 2025-12-11 | Fixed by the upgrade above |
| Failures surfaced through `alert()` | Unstyled, blocking, lost on dismiss | Fixed for script, audio and settings: inline error banners |
| `confirm()` for delete | Native dialog | Fixed: two-step "Confirm?" on the button |
| `page-conversion.tsx` (825 lines) | Never routed, dead duplicate | Deleted |
| 87 MB of WAV assets under `public/samples`, 25 MB of it unreferenced | Every visitor downloads dead weight | The 25 MB of unreferenced `-alt` files are deleted; the rest are still referenced by the landing page |
| The progress bar width was hard coded to `0%` in the markup | The bar never moved | Fixed to the real progress value |
| `X-Saved-Filename` ignored, the client invented its own filename | The download name did not match the saved episode | Fixed |
| Episode metadata JSON was never surfaced | The file existed but the UI could not reach it | Fixed: "Download Script" and an RSS link |

**Still open** (see the roadmap): the studio is still one large component, the progress
estimate is still a client-side guess, the waveform is still decorative, and the landing
page still mounts six audio elements with `preload="metadata"`.

---

## 4. The upstream problem that needs a decision

**Verified.** Microsoft has removed the VibeVoice **TTS inference code** from the public
repository: `vibevoice/modular/modeling_vibevoice_inference.py` now returns HTTP 404
upstream, and the upstream README says the installation and usage of the TTS path is
"Disabled due to widespread misuse". The ASR side is alive and moving.

Consequences:

1. `voice-service/main.py` imports that file. A naive "sync with upstream" upgrade
   breaks the entire app at import time.
2. The vendored copy in `vibevoice-src/` is a March/April 2026 snapshot of upstream
   `main` and is now the only working source of that code. It must be treated as a
   pinned fork, not as a copy that gets refreshed.
3. The weights are still MIT on Hugging Face, but the model card says the model is for
   research and development, supports English and Chinese only, and **embeds an audible
   "this segment was generated by AI" disclaimer plus an imperceptible watermark**.
   That is a disclosure obligation for a commercial product and for a marketplace
   listing, not a footnote.

**Decision needed** (see `docs/ROADMAP_NEXT_LEVEL.md`): keep the vendored fork and
disclose it, or move the local engine to a maintained model.

---

## 5. What the product is now

- A topic in, a researched script out, with delivery marks the audio engine honours.
- Every host gets its own voice, chosen by the user from the presets on disk.
- Pauses and tonal shifts are written into the script and rendered as real silence and
  different delivery settings.
- Exports are podcast-ready: normalised loudness, transcript sidecar, RSS feed with a
  real base URL.
- The studio is reachable, cancellable, honest about errors, and no longer destroys the
  user's API keys.
