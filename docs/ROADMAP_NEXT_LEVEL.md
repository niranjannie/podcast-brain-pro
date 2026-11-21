# Roadmap — taking Podcast Brain Pro to the next level

Date: 2026-11-21
Companion documents: `docs/PRODUCT_AUDIT_2026-11.md` (what is broken and what was
fixed), `docs/HANDOFF.md` (context for the next session).

The goal: move this from "a neat local demo" to "a product people pay for and a skill
someone lists on a marketplace".

---

## 1. The one decision that shapes everything

**Microsoft removed the VibeVoice TTS inference code from its repository** (verified:
upstream `vibevoice/modular/modeling_vibevoice_inference.py` is a 404, and the README
says the TTS installation is disabled). Our `vibevoice-src/` copy still contains it, so
the app works today. But:

- the vendored copy is a frozen fork of code nobody upstream maintains any more;
- the model card restricts it to research use, covers **English and Chinese only**, and
  **embeds an audible AI disclaimer plus a watermark** in the output.

That last point is the sharpest edge for a commercial product and for a marketplace
listing: every episode carries a disclaimer the buyer cannot remove.

Two honest paths:

| Path | What it buys | What it costs |
|---|---|---|
| **A. Keep the vendored VibeVoice, disclose it** | Works today, no migration, 15 GB of known-good models | A disclosure line in every episode, no official support, no upstream fixes, no Indic languages from the local engine |
| **B. Move the local engine to a maintained permissive model** | Commercial clarity, real style control, Indic languages, a model that gets fixed | Weeks of work, new downloads, quality re-tuning, and the multi-speaker feature has to be re-implemented on the new engine |

**Recommendation: A now, B as a tracked project.** Ship A with an explicit disclosure
and start B on a branch. Do not pretend A is a permanent answer.

### Candidates for path B (ranked for this app)

| Model | Licence | Commercial | Indic | Multi-speaker | Prosody control | macOS arm64 |
|---|---|---|---|---|---|---|
| **Qwen3-TTS via `mlx-audio`** | Apache-2.0 | Yes | No | One voice per call | Instruction-based tone/style/emotion, 3 s cloning | Best: native MLX, ~400 ms first chunk |
| **AI4Bharat Indic-Parler-TTS + IndicF5** | Apache-2.0 / MIT | Yes | Yes (23 and 11 languages) | One voice per call | Voice described in natural language; reference-clip style | Plain torch, fits a Mac |
| **Kokoro 82M v1.0** | Apache-2.0 | Yes | Hindi only | One voice per call | Speed only | Easiest, CPU-viable (~1 s/sentence) |
| IndexTTS2 / 2.5 | Apache-2.0 | Yes | No | One voice per call | Best emotion + duration control | GPU-oriented |
| Fish Speech | Community licence (unclear) | Unclear | No | Native | Inline tags `[pause] [excited]` | CUDA-heavy |
| Mistral Voxtral-4B-TTS | CC BY-NC | **No** | Hindi | Yes | Strong | Needs 16 GB+ |

Not shippable as-is: XTTS-v2 (non-commercial), F5-TTS upstream (NC), Voxtral (NC).

---

## 2. Ranked roadmap

### Tier 1 — works with the current backend, days of work, direct quality lift

1. **Loudness normalisation** — *done in this pass* (-16 LUFS, -1.5 dBTP).
2. **Transcript in the feed** — *done in this pass* (Podcasting 2.0 `podcast:transcript`).
3. **Delivery control** — *done in this pass* (`[[pause]]`, `[[style]]`, episode style).
4. **A distinct voice per host** — *done in this pass*.
5. **AI show notes and episode summary** — one extra LLM pass over the script that
   already exists: a summary, three bullet takeaways, a title, a description, and five
   social captions. Cheap, and it is what a podcast host expects to paste into Spotify.
6. **Chapter markers** — the backend already computes a 4- or 6-chapter outline for
   15- and 30-minute episodes and then throws it away. Persist it, show it in the UI,
   and emit `<podcast:chapters>` / `ps1` tags in the feed.
7. **Pronunciation dictionary** — Indian proper nouns and technical terms are where
   Indian-language TTS fails most visibly. Sarvam v4 exposes `dict_id`; a user-editable
   map in the UI, applied before synthesis, fixes it.
8. **Social clips** — three to five short segments (a pull quote, the best exchange, the
   takeaway) rendered from the same script with the sentence chunker that already exists.
9. **Re-render an episode with a different cast or style** — the script is on disk, so
   re-synthesis must not pay for a new LLM script. This is the "revision loop" that
   makes the product worth a subscription.
10. **Batch queue** — a list of topics rendered by the existing two-worker executor.

### Tier 2 — needs backend work, these are the differentiators

11. **Real distribution** — the feed now takes a `PUBLIC_BASE_URL`, but a submission to
    Spotify for Creators or Buzzsprout also needs a public host, `itunes:*` metadata
    that matches, and an enclosure that a podcast host can fetch. Add a "Publish" panel
    that shows the feed URL, the episode count and a copy button.
12. **Provenance and consent** — an "AI-generated" disclosure at the start of each
    episode (EU AI Act Article 50 requires machine-readable marking and an audible
    disclosure from 2 Aug 2026), a C2PA manifest per episode, and a consent record for
    any cloned voice. For a marketplace listing this is what separates a hobby from a
    product.
13. **Per-speaker control panel** — show the resolved speaker → voice mapping the
    backend computes, warn about duplicates, allow a re-pick, and expose pace and
    temperature for the Sarvam path.
14. **Segment-level re-synthesis** — edit one turn, re-render only that turn, splice it
    back with the offsets already available. This is the Descript model.
15. **Transcribe-and-edit** — `/asr/transcribe` exists; wire it so an episode can be
    turned back into text, edited and re-rendered.

### Tier 3 — needs a model or vendor change

16. Move the local engine (section 1).
17. **Sarvam `bulbul:v4-flash`** — 200+ styled personas, `pitch`, `loudness`,
    `dict_id`. The backend already accepts the model and the new fields; the migration
    trap is that v4 persona ids (`shubh_enhi_ads`) are invalid on v3 and the v3 short
    ids are invalid on v4.
18. **Interruption realism** — overlapping speech, as NotebookLM does. No open local
    model does this today; VibeVoice explicitly does not.
19. **Per-language dubbing** with a cloned voice per language.

---

## 3. UI work that is still open

The audit of `frontend/app/page.tsx` found the following, in priority order.

### Correctness and safety

- Split the 1900-line `Home` component into `EpisodeConfigCard`, `ScriptEditor`,
  `AudioPanel`, `HistoryPanel`, `SystemStatus` and the modals. ~40 `useState` hooks in
  one component means every keystroke in the script editor re-renders the history list
  and the waveform.
- Replace the client-side progress estimate with the real `X-Chunks-Used` and
  `X-Gen-Time-Sec` headers, and label the estimate as an estimate.
- Replace the decorative waveform with real peak data decoded from the WAV blob.
- Poll `/health` and show a "backend unreachable" banner. Today a stopped backend looks
  exactly like "the model is downloading".
- Poll `/models/status` only while the page is visible, and with an abort controller.
- `Modal` has no focus trap, no initial focus and no focus restore.
- Inputs have no `id`/`htmlFor` pairing; icon-only buttons have no `aria-label`.
- The landing page mounts six audio elements with `preload="metadata"`; the samples
  total 62 MB after the dead files were removed. Consider serving them from a CDN with
  range requests, or trimming them to 30 s clips.
- The studio is one file. Extract the subcomponents before adding more features.

### Product features the backend already supports

- The backend exposes `/voices`; the UI now uses it, but there is no audition button
  (synthesise one line with `/tts/realtime` to hear a voice before committing).
- The episode library supports `limit` up to 100 and writes a metadata sidecar per
  episode; the UI should offer search, a load-more, and a per-episode metadata export.
- The Indic path flattens the script into one blob with one voice. Either synthesise
  per turn, or label the voice picker as a single narrator so the UI stops implying
  multi-host Indian episodes.
- The export format is hard coded to WAV. Sarvam supports mp3, aac, opus and flac, and
  exposes pace and temperature; both are one selector away.

---

## 4. What to do about the marketplace offer

The Agensi email (2026-11-21) asks to repackage this as an agent skill and list it.
See `docs/HANDOFF.md` for the commercial terms and the questions to send them. The
relevant engineering points:

- The skill package lives in `skill/podcast-brain-pro/` (SKILL.md, a stdlib-only
  validator, and two reference files). It is ready to zip and submit.
- A marketplace skill can only carry the **scriptwriting** workflow. The 15 GB of
  VibeVoice weights cannot ride along, so the skill must either drive the user's own
  local install or fall back to a hosted TTS tool the user already has.
- Agensi's terms (4.8) say a tool charge earns the creator nothing: the revenue is the
  skill sale, not the per-call usage. Price and positioning should follow from that.
- The VibeVoice disclosure obligation applies to anything the skill produces too.

---

## 5. Explicitly not recommended

- **Do not sync `vibevoice-src/` with upstream.** The TTS inference file no longer
  exists upstream; a sync breaks the app.
- **Do not add a paid tier to the UI before the free path works.** The free path is
  what gets usage.
- **Do not chase multi-host interruption realism on the current engine.** VibeVoice
  cannot do it, and faking it with overlap tricks produces artefacts that a listener
  notices immediately.
- **Do not market the local engine as "no cloud".** Script generation is a cloud LLM
  call; only the synthesis is local.
