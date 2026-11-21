# Fresh assessment — November 2026, second pass

Written by a different model than the first pass, asked to start from the original
request with fresh eyes: the Agensi email, the two named bugs, the six-month-old stack,
"voice modulations, proper pause and expressions", "more advanced features", and the new
constraints the user added in this pass:

> i don't want big models to test, it should be freely available openrouter or groq, any
> free models, local ... voice models are low memory ... voice cloning feature is missing
> ... i read somewhere there is already highest rated voice cloning repo, if we adopt
> that also an enhancement ... just i am overthinking, not sure, u tell
> ... also the complete UI redesign or makeover

---

## 1. The short answer on voice cloning

**Yes, cloning is the right next feature, and no, you are not overthinking it.** It is
the single capability that separates a demo from a product people would pay for: two
hosts that sound like *your* two hosts, in every episode, without recording anything.

But the model you read about is probably **Chatterbox** (Resemble AI, MIT, very highly
rated) — and on this machine it does not currently run. Details and the evidence below.

### What I actually installed and ran on this machine

| Engine | Licence | Download | Memory | Cloning | Verified here |
|---|---|---|---|---|---|
| **Kokoro 82M** | Apache-2.0 | ~300 MB | ~1 GB, CPU is fine | No | **Yes.** Installed, downloaded the weights, generated speech on CPU, then generated it again through the new `/tts/engine` endpoint and the new Voice Lab UI. The rendered clip was 4.6 seconds for the sample sentence. |
| **Chatterbox 0.1.7** | MIT | ~1-2 GB | ~4-7 GB, MPS or CPU | Yes, from 5-10 s of reference audio | **No — broken here.** It installs and imports, but `ChatterboxTTS.from_pretrained()` dies in `perth.PerthImplicitWatermarker()` because perth does `from librosa import resample` and that name is not importable in this Python 3.14 environment. The registry now reports this as "Broken here" instead of letting you hit a 500. |
| **Qwen3-TTS 0.6B / 1.7B** | Apache-2.0 | ~2 GB / ~3 GB | ~4 GB / ~6-8 GB | Yes, from ~3 s of audio | Not installed. Documented in the catalogue as "Documented, not wired". |

### What to install for cloning, in order

1. **Qwen3-TTS 1.7B via `mlx-audio`** (Apache-2.0). This is the best fit for your Mac:
   MLX runs far faster than PyTorch MPS on Apple Silicon, the download is ~3 GB, the
   memory footprint is ~6-8 GB, and it clones from about three seconds of reference
   audio. Use the 1.7B, not the 0.6B — the 0.6B is cheaper but its own model card says
   cloning quality is noticeably worse.
2. **Chatterbox** (MIT) in a **Python 3.10-3.12** virtualenv with the versions
   `chatterbox-tts` pins. Do not try to force it onto Python 3.14; the failure is in its
   watermarking dependency, not in the model.
3. **Kokoro** for everything that does not need cloning. It is the cheapest way to make
   the product feel instant: 82M parameters, ~300 MB, runs on CPU, Apache-2.0, and it is
   already wired and verified here.

### The one thing cloning must ship with

Consent. Cloning a voice that is not yours is the abuse case that gets products pulled.
The clone endpoint refuses to run without an explicit confirmation and writes a consent
record next to the reference audio. That is the same model ElevenLabs uses, and the EU AI
Act's disclosure rules apply from August 2026.

---

## 2. Fresh judgement on the first pass

I kept most of it. Where I changed my mind or tightened it:

| First-pass decision | Fresh verdict |
|---|---|
| Fix the script contract in one shared module | **Keep.** It is why the new engines could be added in one file instead of three. |
| Delivery style = a cfg_scale nudge on VibeVoice | **Keep, but say what it is.** On VibeVoice there is no emotion API, so a "style" is a guidance change. On Chatterbox the same idea maps to `exaggeration`, which is a real expressiveness control, and on Sarvam to pace and temperature. The Voice Lab now exposes engines where delivery is genuinely controllable. |
| Pauses = split synthesis and stitch silence | **Keep.** It is the only way to place silence accurately, and it now works on every engine, including the small ones. |
| Keep the vendored VibeVoice, disclose it | **Keep, with an exit.** Kokoro is now the verified lightweight alternative for English, and Qwen3-TTS is the documented exit for cloning. The vendored VibeVoice is still the only engine here that does multi-host in one pass. |
| Loudness normalisation on by default | **Keep.** It ran on the Kokoro clip in the end-to-end test without breaking anything. |
| `/` is the studio, `/landing` is marketing | **Keep.** |
| The studio as one 1900-line component | **Changed.** It is now a hook plus five views, and the route's JavaScript dropped from 195 kB to 111 kB first load. |

---

## 3. What this pass built

### Backend

- `voice-service/engines.py` — an engine registry. Every engine reports its licence,
  download size, memory, whether it clones, whether it is installed, and **whether it
  actually runs on this machine** (import checks are not enough: Chatterbox imports and
  still fails). Optional engines import lazily, so the app starts without them.
- `GET /engines` — the catalogue the Voice Lab renders.
- `POST /tts/engine` — synthesise with a small engine. Delivery directives work here too:
  pauses become real silence between the rendered parts.
- `POST /tts/clone` — consent-gated cloning. Multipart: text, engine, reference audio,
  consent. Stores the reference and the consent record, renders, normalises loudness.
- Kokoro and Chatterbox adapters. Qwen3-TTS is documented in the catalogue and marked
  not wired, so nothing pretends to work that does not.

### Frontend — a full redesign, not a reskin

- `app/page.tsx` went from 1900 lines to ~60: a shell, a state hook
  (`lib/useStudio.ts`), and five views.
- New layout: sidebar navigation (**Create**, **Library**, **Voice Lab**), live backend
  and model status, a keys modal and a help modal.
- New design system in `globals.css` and `tailwind.config.ts`: deeper neutrals, an
  indigo-to-cyan accent, panel surfaces, one focus treatment everywhere, an indeterminate
  activity bar for jobs with no real progress signal.
- **Create**: brief (topic, format, language, delivery, length with `aria-pressed`),
  cast (one card per host with a voice select), script editor with a pause button per
  line and directive help, audio panel with elapsed time, cancel, real segment/time
  stats from the response headers, WAV / Script JSON / RSS actions.
- **Library**: search, play, download, rename (stem only), two-step delete, load more,
  loudness badges.
- **Voice Lab**: the engine catalogue with install and health state, a "try a small
  engine" panel, and the consent-gated cloning form.
- Accessibility: every input is labelled through a `Field` primitive, the modal now has
  a focus trap, initial focus, focus restore and a body scroll lock, icon-only buttons
  have `aria-label`, the length selector uses `aria-pressed`.
- `Button asChild` no longer puts `type="button"` on anchors.

### Verified in a browser, not just compiled

The dev server was started against a backend running the real engine layer with the
heavy VibeVoice modules stubbed. In the Voice Lab: the catalogue listed Kokoro as
ready, the render button produced a 4.6-second clip, and the result panel played it.
That is the first audio this project has produced in these sessions.

---

## 4. What is still pending

| Item | Why it is not done |
|---|---|
| Qwen3-TTS adapter code | Documented, not wired. It is the recommended cloning engine for Apple Silicon, so this is the next concrete task. |
| Chatterbox runtime on this machine | Blocked by its dependency chain on Python 3.14. Needs a 3.10-3.12 venv. |
| Multi-host episodes on the small engines | They are single-voice per call; a multi-host path would synthesise per turn and stitch, reusing `plan_generation`. Not built yet. |
| Multi-host Indian episodes | The Indic path is still one narrator; the UI now says so instead of implying otherwise. |
| Show notes, chapters, social clips | Still roadmap items. The chapter outline is computed and discarded. |
| VibeVoice longform / realtime paths | Unchanged in this pass and still unverified end to end: the weights are not on this machine. |
| The landing page | Untouched in this pass except the claims fixed earlier. It still ships ~62 MB of sample audio. |

---

## 5. Suggested order from here

1. `pip install mlx-audio`, then write the Qwen3-TTS adapter behind the registry entry
   that already exists. That turns "Clone a voice" into a working feature on your Mac.
2. Use Kokoro for previews: render a five-second preview of the cast before committing to
   a 15-minute VibeVoice render. That one change makes the product feel an order of
   magnitude faster.
3. Multi-host on the small engines by reusing `plan_generation` per turn.
4. Show notes and chapters, then re-render without a new script.
5. Only then revisit the marketplace listing: a skill that can clone a voice with consent
   is a much stronger listing than a scriptwriter alone.
