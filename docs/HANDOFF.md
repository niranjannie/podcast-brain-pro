# Handoff — context for the next session

> **Update, second pass (same day, different model).** A full studio redesign and a Voice
> Lab with small local engines and consent-gated voice cloning landed after this file was
> written. Read `docs/FRESH_ASSESSMENT_2026-11.md` first — it has the verdict on voice
> cloning, what was actually verified (Kokoro produced real audio through the API and the
> UI; Chatterbox is broken on Python 3.14), and what is still pending. Commits:
> `17480eb` on top of `8749286`. The review brief for an outside model is
> `docs/REVIEW_REQUEST.md`; its diff range predates the redesign.
>
> **Update, third pass (2026-11-22).** The read-only backend audit finally returned and
> found two real defects from the earlier work: the RSS transcript sidecar was written to
> the wrong directory (so the feature was dead), and `voice-service/.env` was never read
> at all. Both are fixed in `e2fbd52`, along with ~25 other findings. Two of its
> high-severity claims were false positives — the gap indexing is correct — and the
> reasoning is recorded in `docs/BACKEND_AUDIT_2_FIXES.md` so the next reviewer does not
> have to redo it. 41 unit tests and 14 API smoke checks pass.
>
> **Update, fourth pass (2026-11-22).** Everything the second-pass assessment listed
> as pending is now implemented and verified: Qwen3-TTS CustomVoice and Base, and
> Chatterbox Multilingual, run through an isolated persistent MLX worker; lightweight-
> engine and Sarvam multi-host rendering; show notes, measured chapters and social
> clips; cast previews; re-render without a new LLM script; and landing-media
> compression (62 MB of WAV → 12 MB of M4A). Chatterbox is no longer blocked by Python
> 3.14 — not because the dependency chain was fixed, but because it now runs on MLX
> instead of PyTorch. See section 8 for the full verification record.
>
> **Update, fifth pass (2026-11-23, this session).** The option matrix was re-run after
> the fourth-pass fixes, which exposed two more real defects: an Indic conversation
> collapsed into a single voice, and the `/podcast/generate` response omitted the
> `language` field so the skill's own validator rejected every non-English episode for
> missing the English disclosure. Both are fixed and verified; see section 9. The
> backend test count rose from 67 to 102, the build script was made to exclude build
> junk instead of refusing to build, and the skill package was rebuilt and re-tested.
>
> **One correction to the record.** `docs/FRESH_ASSESSMENT_2026-11.md` and
> `docs/ROADMAP_NEXT_LEVEL.md` point at "the final verification record" in this file.
> That record did not exist until the fourth pass. If you are reading the two documents'
> status banners and believe the verification was broader than section 8 says, check
> sections 8 and 9 — they are deliberately narrower than the banners imply.

Last updated: 2026-11-23 by the agent that ran the fifth pass (Indic parser fix,
language field in response, build script, option matrix). Read this first, then
`docs/PRODUCT_AUDIT_2026-11.md` (what was broken and what was fixed) and
`docs/ROADMAP_NEXT_LEVEL.md` (what to do next).

---

## 1. What the user asked for

Two requests, in order.

**Request 1 — the marketplace offer.** The user received an email from
`joeri.b@getagensi.com` (Agensi, agensi.io) asking to repackage `podcast-brain-pro` as
an AI agent skill and sell it on their marketplace. The user is new to this kind of
thing and asked for: what the offer really means, whether it is legitimate, how to
check the exposure of their GitHub email, what the pros and cons are, and whether they
should reply.

Answer given: the offer is legitimate but young, the money is the skill sale only (70%
of net, $1 minimum, $3.50 payout threshold, 30-day refund with the creator share
reversed), tool calls earn the creator nothing, and the recommendation is to reply with
questions before creating a payout account. The GitHub email is exposed through commit
metadata (`niranjan.nie@gmail.com` in every commit), not through the profile.

**Request 2 — modernise the product.** "Fix both the bugs in AI_VOICEVIBE and push to
github and check carefully all the code and fix for any issues and also this code has
been built almost 6 months before can you check any latest changes happened in the ai
models used and better ones to make it up to date and also the UI design with more
advanced features and voice modulations proper pause and expressions advanced way.
Think fresh way and suggest how you can make the product to next level. Before that
document all your findings and my ask and your recommendations so next session AI
agent knows the context of this discussion."

The two named bugs were: (a) the `role` / `speaker` key mismatch that broke multi-speaker
voice mapping, (b) the README claiming Assamese while the code supports Odia.

---

## 2. State of the repository

- Remote: `github.com/niranjannie/podcast-brain-pro`, branch `master`.
- Local checkout: `/Volumes/DevSSD/projects/AI_VOICEVIBE` (this is the same repo, with
  `voice-service/`, `frontend/`, `vibevoice-src/`, `docs/`, `skill/`).
- The first backend commit was pushed during this session; the frontend and documentation
  work is in the working tree unless the commit list below says otherwise.
- Untracked and deliberately left alone (they are the user's files):
  `docs/LINKEDIN_REPLY.md`, `docs/REDDIT_GUIDE.md`, `docs/SETUP_TROUBLESHOOTING.md`,
  `req/`.

### Commits from this session

| Commit | What |
|---|---|
| `b7981db` | Backend: speaker/voice mapping, delivery directives, current provider models, loudness, transcripts, RSS base URL, transformers pin |
| `6e1f503` | Docs: stop pinning the upload zip's hash in a document |
| `718025f` | Fix: retry a failed content-extras pass instead of discarding it |
| `2c173e0` | Fix: stop an Indic conversation collapsing into one voice |
| `4061aca` | Docs: record the two defects the option matrix caught |
| `47645f6` | Fix: exclude build junk from the package instead of refusing to build |
| `d2fa53f` | Fix: return the requested language in the generate response |

---

## 3. Facts that must not be re-derived next session

### Agensi commercial terms (read from agensi.io/terms, 2026-11-21)

- Creator keeps **70%** of net, Agensi 30%; Agensi is merchant of record and handles
  buyer VAT.
- Minimum paid price **$1**; one-time listings are bought with credit or by card from
  $5, and credit needs a $5 top-up, so a $1 skill cannot be bought with a card.
- Payout via Stripe Connect or Zoneless (USDC on Solana); threshold **$3.50**.
- **30-day money-back guarantee** on every paid skill; the creator's 70% is reversed on
  a refund.
- Tool calls (ElevenLabs, MiniMax, HeyGen on the buyer's credit) earn the creator
  **nothing** (terms 4.8). A skill may use up to 10 Agensi tools (6.5).
- Creator keeps full ownership and grants a non-exclusive worldwide licence (8.1);
  linking your own docs or source repo is allowed, upselling a paid off-platform
  version is banned (6.3a).
- `agensi.io` and `getagensi.com` share the same nameservers, both on Google Workspace
  mail. Joeri Brons is a real verified creator on the platform.

### The Agensi questions still unanswered

`/Volumes/DevSSD/projects/AI_PODCAST_SKILL/questions-for-agensi.md` has the full list.
The four that matter most: who pays for the tool calls and what the buyer gets for
paying the creator; the real price floor given the credit-only rule under $5; whether
refunds can be clawed back beyond the creator's share; and whether the creator may sell
the same skill elsewhere.

### Model and vendor currency (verified against primary sources)

- **GitHub Models inference API: retired 30 Jul 2026.** Removed from the chain.
- **Groq `llama-3.3-70b-versatile`: shut down 16 Aug 2026.** Replaced with
  `openai/gpt-oss-120b`.
- **Gemini `gemini-2.0-flash`: retired 1 Jun 2026.** Replaced with `gemini-2.5-flash`.
- **DeepSeek `deepseek-chat`: legacy alias discontinued 24 Jul 2026.** Replaced with
  `deepseek-v4-flash`.
- **OpenRouter `mistralai/mistral-7b-instruct:free`: no provider left.** The fallback now
  reads the live catalogue and picks a routable `:free` model.
- **Sarvam `bulbul:v4-flash`** is the current model (200+ styled personas, `pitch`,
  `loudness`, `dict_id`). v3 short speaker ids (`shubh`) are invalid on v4 and v4
  persona ids (`shubh_enhi_ads`) are invalid on v3. Sarvam wants ISO 639-1 (`or-IN`),
  the app speaks `od-IN`.
- **Microsoft deleted the VibeVoice TTS inference code** upstream
  (`modeling_vibevoice_inference.py` is a 404) and disabled the TTS path in the README
  "due to widespread misuse". The ASR side is alive and moving. Our vendored copy is
  the only working source, so **never sync `vibevoice-src/` with upstream**.
- The VibeVoice model card restricts use to research and development, covers English
  and Chinese only, and **embeds an audible AI disclaimer plus an imperceptible
  watermark**. This is a disclosure obligation for a commercial product and for a
  marketplace listing.
- `transformers` 5 breaks the vendored VibeVoice at import. The pin is
  `transformers>=4.51.3,<5.0.0`.

---

## 4. What changed in this session

### Backend (`voice-service/`)

- New `script_pipeline.py`: the single source of truth for the script contract
  (turn keys, delivery directives, sentence-aware chunking, voice resolution).
- New `audio_pipeline.py`: ffmpeg loudness normalisation and measurement.
- New `test_script_pipeline.py`: 23 tests, stdlib only. Run with
  `python3 -m unittest test_script_pipeline`.
- `main.py`: rewritten longform path (global speaker numbers, per-speaker voices,
  honoured `voice_names`, per-segment style, pause stitching), rewritten realtime path
  (directives, voice matching, optional-safe parameters), Sarvam path rewritten
  (directives, `bulbul:v4-flash` fields, language code mapping, WAV storage), new
  `GET /voices`, delivery instructions in the scriptwriter prompt, removed the dead
  GitHub Models provider, updated every model id with an environment override, RSS feed
  made configurable, transcript sidecar, loudness normalisation on every export.
- `rss_generator.py`: configurable channel metadata, Podcasting 2.0 transcript element,
  `itunes:episodeType` and `itunes:explicit`.
- `requirements.txt`: transformers pinned below 5.
- `.env.example`: retired key removed, model overrides, `PUBLIC_BASE_URL`, podcast
  channel metadata, `NORMALIZE_LOUDNESS`, `EXPAND_SHORT_SCRIPTS`.

### Frontend (`frontend/`)

- Routing fixed: `/` is the studio again, `/landing` is the marketing page, and the
  landing page links to the studio.
- Settings modal no longer destroys API keys.
- Script and audio generation: in-flight guard, run id, cancel button, inline errors.
- Voices come from `GET /voices`; the cast is validated against the catalogue; the real
  speaker names are sent to the backend.
- New delivery style selector, per-line pause button, "Download Script", RSS link.
- Dependencies aligned and the build fixed: `next@14.2.35`, `eslint@8.57`,
  `eslint-config-next@14.2.35`, `.eslintrc.json` added, `typecheck` script added.
- Deleted: `page-conversion.tsx` (never routed), three unreferenced 25 MB sample files.

### Documentation and packaging

- `docs/PRODUCT_AUDIT_2026-11.md`, `docs/ROADMAP_NEXT_LEVEL.md`, this file.
- `docs/API_KEYS.md` rewritten with the retired providers and the model overrides.
- `skill/podcast-brain-pro/` — the marketplace skill package (SKILL.md, a validator
  script, two reference files). It mirrors the current backend contract.

---

## 5. How to verify the current state

```bash
cd /Volumes/DevSSD/projects/AI_VOICEVIBE

# Backend logic, no models needed — 102 tests across five modules
cd voice-service && .venv/bin/python -m unittest \
  test_script_pipeline test_audio_pipeline test_content_pipeline \
  test_dialogue_paths test_backend_utils

# Backend syntax
.venv/bin/python -m py_compile main.py script_pipeline.py audio_pipeline.py \
  content_pipeline.py mlx_worker.py engines.py

# Frontend
cd ../frontend && npm install && npm run typecheck
```

For a production build, keep it away from the dev server's directory, or the dev
server starts serving a broken page:

```bash
cd frontend && npx next build --distDir .next-build
```

To run the app locally:

```bash
# Backend (reads voice-service/.env itself)
cd voice-service && .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000

# Frontend
cd frontend && npm run dev
```

The MLX engines need their own environment; see section 8.2. The backend cannot be
imported on a machine with `transformers` 5 in the main environment, and the models
are ~15 GB, so a full end-to-end run needs the real setup in `docs/SETUP.md` on Apple
Silicon.

---

## 6. What the next session should do, in order

> Rewritten 2026-11-22. Items 2 and 4 of the original list were completed in the
> second and fourth passes; the original numbering is kept inline so the older entries
> above and below still make sense.

1. **Reply to Agensi** with the questions in `questions-for-agensi.md` before creating a
   payout account. Do not upload anything yet. Still unanswered.
2. ~~Fix the remaining UI defects~~ — **done** in the second pass: the 1900-line
   component is split into a shell plus five views, the health banner exists, the modal
   has a focus trap, and progress comes from real response headers.
3. **Decide path A or B** for the local TTS engine (keep the vendored VibeVoice with a
   disclosure, or move to Qwen3-TTS via `mlx-audio` / AI4Bharat Indic models). Qwen3-TTS
   and Chatterbox now work on MLX, which makes path B materially cheaper than it was —
   see section 8.2 for the two-environment tax it carries.
4. ~~Ship the tier-1 features~~ — **mostly done** in the fourth pass: show notes,
   chapter markers, re-render without a new script, and social clips all ship.
   The pronunciation dictionary is still open; it is listed under tier 2 now.
5. ~~**Add the disclosure**~~ — **done** in the fourth pass: every saved episode
   opens with a spoken AI disclosure in the episode's own language, the RSS feed and
   JSON sidecar carry machine-readable marking, and `AI_DISCLOSURE=false` can disable
   it. The README says not to disable it for published content.
6. **Re-render one episode through each engine** against the current tree. The existing
   renders predate the last edits to `engines.py` (section 8.3).

---

## 7. Constraints to respect

- The user is the owner and decides. Recommendations are recommendations.
- Do not push to GitHub without being asked; the user asked for the push explicitly in
  the last request, not as a standing rule.
- The repo is public and MIT. Never commit keys, `user_config.json`, `.env`, model
  weights, or the `outputs/` directory.
- `vibevoice-src/` is a pinned fork. Do not "update" it.
- The user's own untracked files (`docs/LINKEDIN_REPLY.md`, `docs/REDDIT_GUIDE.md`,
  `docs/SETUP_TROUBLESHOOTING.md`, `req/`) must not be deleted or committed without
  asking.

---

## 8. Fourth pass — the verification record

Written 2026-11-22. This is the record the other two documents point at. It is written
to be narrower than the status banners in `FRESH_ASSESSMENT_2026-11.md` and
`ROADMAP_NEXT_LEVEL.md` imply, because those banners were written before the
verification was finished and overstated it.

### 8.1 What was built in this pass

**Backend**

- `voice-service/mlx_worker.py` (new) — a persistent MLX speech worker. One JSON
  request per line on stdin, one JSON response per line on stdout. Audio is written to
  a temporary WAV so model logging can never corrupt the protocol. Models stay loaded
  between requests, which is the point: reloading a 2 GB model per call is what made
  the earlier "documented but not wired" state unusable.
- `voice-service/content_pipeline.py` (new) — generates show notes, chapters and social
  clip selections from the script. The model chooses **metadata and turn ranges only**;
  `spoken_text` is rebuilt from the normalised source turns, so a model cannot inject
  unsourced speech or delivery markers into text that will be rendered.
- `voice-service/engines.py` — the registry now reports real runtime health, not just
  "is it importable". `MLXWorker` spawns and supervises the worker process; the
  catalogue reports `installed`, `wired` and a `health.ok` flag with a detail string.
- `voice-service/main.py` — `POST /podcast/extras` (new endpoint); multi-host rendering
  for the lightweight engines via `plan_generation`; Sarvam multi-host; engine script
  rendering with per-turn style and pauses preserved.
- `voice-service/script_pipeline.py` — `split_monologue_turns` and
  `chunk_units_for_engine` (new). The second one bounds single-voice engine calls by
  word count while preserving speaker, style and pauses, and splits an unusually long
  sentence on word boundaries rather than silently exceeding the model's limit.
- `voice-service/requirements-mlx.txt` (new) — `mlx-audio[tts]==0.6.7`, pinned.

**Frontend**

- `frontend/components/studio/ExtrasView.tsx` (new) — show notes, takeaways, social
  captions, chapters and social clips, with a copy button per caption and a render
  button per clip.
- `frontend/lib/useStudio.ts` — extras state and generation, social clip rendering,
  cast previews (audition a voice before committing to it), and re-render without a
  new LLM script pass.
- `frontend/components/studio/Shell.tsx` — a "Marketing page" link to `/landing`. The
  studio had no route to the marketing page at all, so it looked missing. Fixed here.
- `frontend/public/samples/` — 6 × WAV (62 MB) → 6 × M4A (12 MB).

### 8.2 The two-environment constraint — this is permanent, not a bug

`mlx-audio==0.6.7` requires `transformers>=5.14`. The vendored VibeVoice engine
**breaks at import** on `transformers` 5, and `requirements.txt` pins
`transformers>=4.51.3,<5.0.0`. These cannot share one environment.

| Environment | Python | transformers | Engines |
|---|---|---|---|
| `voice-service/.venv` | 3.12 | `<5` | VibeVoice, Kokoro, Sarvam |
| `voice-service/.venv-mlx` | 3.12 | `>=5.14` | Qwen3-TTS, Chatterbox |

The parent process talks to the MLX engine over a pipe, so `mlx_worker.py` runs with
the *other* interpreter's `transformers` and the parent never imports MLX itself. This
is the fix for the Chatterbox-on-Python-3.14 blocker, and it is a real tax: two
environments to keep alive, and `MLX_AUDIO_PYTHON` must point at the right one.

The earlier framing — "Chatterbox is no longer blocked by Python 3.14" — is accurate
about the symptom and misleading about the cause. The dependency chain was not fixed;
Chatterbox moved off PyTorch entirely.

### 8.3 What was actually verified, and what was not

**Verified by running it, in this pass:**

- 102 backend unit tests pass (`test_script_pipeline`, `test_audio_pipeline`,
  `test_content_pipeline`, `test_dialogue_paths`, `test_backend_utils`).
- `tsc --noEmit` clean; `npm run build` clean.
- Backend `/health` returns ok on MPS; all four engines report `installed=true`,
  `wired=true`, `health.ok=true`.
- Both pages render in a real browser at desktop width: the studio (Create / Library /
  Voice Lab all render with real data), and `/landing` with all 6 audio samples loading
  with correct durations and all 5 images loading.
- Two complete episodes rendered end to end through Qwen3-TTS, both with measured
  loudness near -16 LUFS, and `.chapters.json` and `.transcript.json` sidecars written
  next to them.

**Not verified, and the earlier banners should not be read as claiming otherwise:**

- VibeVoice longform and realtime synthesis end to end. The engine reports healthy and
  the weights are on disk, but no full episode was rendered through it in this pass.
- Chatterbox cloning through the UI. Reference audio and consent records exist on disk
  from the earlier session, but a fresh end-to-end clone was not re-run here.
- The `docs/HANDOFF.md` banners in the other two documents say these "were verified".
  Treat that as the claim they make, not as a record of what a reader can reproduce.

**One trap worth knowing:** the rendered episodes and clone reference files on disk are
timestamped 02:15–02:27, while `engines.py` was last modified at 02:21. The renders
predate the final edits to the engine registry. They prove the path worked; they are
not a test of the current tree. If you need confidence in the current code, render one
episode through each engine before shipping.

### 8.4 Two defects fixed in this pass

1. **The studio had no link to the landing page.** `/landing` existed and served
   correctly the whole time; nothing in the studio pointed at it, so it read as
   missing. Fixed with a sidebar link, verified by clicking through.
2. **`voice-service/outputs/` was not gitignored.** The `.gitignore` only excluded
   `outputs/archive/**`, so 16 new files — including ~13 MB of WAV renders and the
   voice-clone consent records — were staged for commit. Consent records are personal
   data about a voice the user owns; they must not enter a public repo. The directory
   is now ignored. The 16 files already tracked before this rule remain tracked; decide
   whether they should be, separately.

**Also note:** running `npm run build` while `npm run dev` is running corrupts the
dev server, because both write to `frontend/.next/`. The symptom is a blank or broken
page while curl still returns 200. The fix is `rm -rf frontend/.next && npm run dev`,
or `npx next build --distDir .next-build` to keep them apart.

### 8.5 Kimi 3.1 — the actual answer

The user asked whether "Kimi 3.1 has done a major upgrade" to this product. It has
not. **No Kimi or Moonshot model id appears anywhere in the repository.** The script
provider chain is Dialogram → Groq → DeepSeek → Ollama → Gemini → Mistral → Together →
OpenRouter.

Kimi is reachable only through OpenRouter, and it is not free there:
`moonshotai/kimi-k3.1-pro` is $0.25/M input and $8.80/M output, with a 1M context
window. The free-model picker in `main.py` only ever selects ids ending in `:free`, and
the current free catalogue contains no Kimi tier, so it will never pick one. The
`preferred` list (`gpt-oss`, `llama-3.3`, `qwen3`) matches nothing in the current
catalogue either, so the picker falls through to alphabetical order.

To use it, set `OPENROUTER_MODEL=moonshotai/kimi-k3.1-pro` in `voice-service/.env`.
No code change is needed. The model id list is worth re-reading before the next
provider retirement, because several of the ids hard-coded in `main.py` have already
been retired once.

### 8.6 The option matrix — what was tested and what broke

The user asked for every option to be exercised: single person, multiple people,
group discussion, different lengths, topics, languages. A harness now lives in the
repo:

```bash
cd voice-service && .venv/bin/python test_option_matrix.py
```

It needs the backend running and covers 60 cells: the three formats, five
durations, all 11 languages, all 6 delivery styles, content extras on and off,
every engine, the Sarvam path for all 10 Indic languages, the clone consent gate,
the library, the RSS feed, and 11 validation cases that must return 4xx.

The first run failed 17 cells. The causes were not 17 bugs:

1. **The episode ended mid-sentence.** The token budget in `DURATION_CONFIG` was
   too tight, so the provider truncated the script and the truncated text was
   rendered as-is. The audio faithfully stopped on a fragment. Fixed by raising
   the budgets and adding `ensure_complete_ending()` in `script_pipeline.py`,
   which drops a dangling fragment and then generates a sign-off, so the last
   thing a listener hears is a finished thought.

2. **Reasoning models returning empty content.** Groq's `openai/gpt-oss-120b` and
   DeepSeek's `deepseek-v4-flash` spend part of their budget on hidden reasoning
   tokens. When reasoning exhausts the budget the visible `content` comes back
   empty — and an empty string was treated as success, so the fallback chain
   never fired and the episode had zero words. An empty response is now a failure
   that falls through to the next provider, the shared `_openai_compatible_chat()`
   helper retries once with a larger budget, and the chain makes one more full
   pass before giving up.

3. **Odia was mapped to the wrong Sarvam code.** `SARVAM_LANGUAGE_CODES` sent
   `od-IN` as `or-IN`, which the API rejects, so every Odia episode failed.

4. **Bad input leaked as 500.** An empty topic and an unsupported Sarvam
   language are client errors. They now return 422 and 400.

5. **A cloning engine asked for a voice it did not have** failed deep inside the
   model with "No conditionals available". It now says which voices exist.

6. **Truncated content-extras JSON** failed the whole extras pass. It is now
   retried once with a bigger budget. Malformed JSON is still not retried, so
   the existing contract test still holds.

Also fixed in this pass: `podcast/generate` was converting the provider's 503
into a 500, so a temporary provider outage looked like a server fault.

### 8.7 Two more defects the option matrix caught

**An Indic conversation collapsed into one voice.** When the model writes a script in
an Indic language it often labels its speakers with the role word in the target
language — `সঞ্চালক:` for Host, `অতিথি:` for Guest — even when asked to keep the
label in Latin script. The parser had two faults: its unknown-speaker pattern matched
only ASCII letters, so an Indic label was not recognised as a label at all and got
**spoken out loud** as part of the text; and where it did recognise one, it dropped
the whole line, so a two-host conversation lost its content and came out as a single
voice. Now an unfamiliar label is removed from the text but its words are kept, and
distinct labels map to the cast in order of first appearance. The prompt also says to
keep the labels in Latin script, because they are identifiers that select a voice, not
words to be spoken. `parse_conversation_script` moved to `script_pipeline.py`, where the
rest of the script contract lives and where it can be tested without importing torch.

**One bad chapter threw away the whole extras payload.** The content model sometimes
puts a chapter's `start_turn` in the wrong place, and the strict validator rejected the
entire payload over it — the user lost the title, the summary, three takeaways, five
social captions and three social clips because one number was off. The validator stays
strict and still never retries: a payload that breaks the contract is a contract
violation, not a transient error. The retry moved one layer out into
`generate_content_extras_with_retry()`, so a second attempt costs one LLM call and the
validation is not weakened.

### 8.8 The fourth-pass follow-up work

Four items landed after the option matrix, in response to what the matrix and the
audit turned up.

**The AI disclosure.** EU AI Act Article 50 has required synthetic audio to carry
an audible disclosure and machine-readable marking since 2 August 2026. The app
had none of it. Now:

- every saved episode opens with a spoken line saying it was generated by AI, in
  the episode's own language (`DISCLOSURE_LINES` in `script_pipeline.py`);
- the disclosure is added at the **script** layer, so the user sees it in the
  editor, and again at the **audio** layer, so it survives the user deleting it
  from the script. `add_disclosure()` is idempotent, so it is never spoken twice;
- a voice preview does not open with a legal notice: the audio layer only adds
  it when `save_to_disk` is true, and a preview is never saved;
- the RSS channel description, each episode description and a
  `podcast:disclosure` element all carry the machine-readable marking;
- each episode's `.json` sidecar has a `disclosure` field;
- `AI_DISCLOSURE=false` turns it off. The README says not to do that if you
  publish.

The VibeVoice model card states the model embeds its own audible disclaimer and
an imperceptible watermark. That layer cannot be removed, and it is why the
README points commercial users at Kokoro, Qwen3-TTS or Chatterbox instead.

**Social clips render in 8 seconds, not 130.** A clip went through the full
VibeVoice path, which meant loading the 5.4 GB model and waiting over two
minutes for thirty seconds of audio. Clips now render with Kokoro, and the UI
says plainly that the clip voice differs from the episode voice.

**The Groq default is now `openai/gpt-oss-20b`.** The 120b model was twice as
slow for the same output and both were eating the free-tier rate limit. The
model id is still overridable with `GROQ_MODEL`.

**The Agensi commercial terms are settled.** Joeri answered the first round of
questions (2026-11-23). The decisions his answers imply:

| Question | Answer | Consequence |
|---|---|---|
| Tool revenue | Buyer pays tool charges separately; the creator earns nothing from them. 70% applies to the skill price only. Paid single skills sit $10-$30, average order ~$11 | Price at **$12** |
| Price floor | Under $5 is credit-only; card from $5. Minimum $1, but start at $10+ | $12 clears both |
| Refunds | Refunds and chargebacks reverse the creator share. If already paid out it is taken back or deducted from future payouts. Agensi pays the chargeback fee | **No cap stated.** This is the open commercial risk |
| Payout | Stripe Connect covers the EU, **not India** — so Zoneless (USDC on Solana) is the route. Nothing paid out until the identity check finishes. Agensi invoices on the creator's behalf; taxes are the creator's own | Set up Zoneless early |
| Selling elsewhere | **Allowed.** Listing is non-exclusive; 6.3a only forbids the listing from linking to, promoting or upselling a paid version | Free here + paid elsewhere is fine, so long as the listing never points at it |
| Distribution | Dashboard shows views, installs and sales. Paid listings get a ranking boost over free ones that match about as well | **List paid from the start** — the boost matters most for a listing with no history |
| Updates | No failed security checks plus AI approval may go live automatically; others are reviewed. Upload a new zip to the same listing | Turnaround unknown |
| Packaging | A zip with `SKILL.md` at the root and `name` + `description` in the frontmatter is the whole requirement | The package already meets it |

Joeri did not have detail on the refund cap, KYC documents, tax withholding, update
turnaround, or a policy for media-generating skills, and said he would not guess. The
follow-up draft asks for those four with concrete proposals rather than open questions:
`docs/AGENSI_REPLY_2.md` (gitignored, like the other outreach material). Nothing has
been uploaded and no payout account exists.

**The price decision, and the condition attached to it.** The creator chose **$12**.
Joeri's evidence: paid single skills sit between $10 and $30 with an average order
around $11. $12 is 9% above that average and reads as a premium nudge that still
clears an easy yes; $15 is 36% above it and asks a stranger, on a listing with no
reviews, to justify fifteen dollars for a script generator. The creator's share is
$8.40 at $12 and $10.50 at $15, but the goal of a first listing is the first sale,
and a listing with reviews is worth more later than a high price on one without them.
**The condition:** if the price turns out to be locked at upload, $15 is the better
number, because $12 would then be permanent. The draft email asks Joeri how a price
change works, and his answer decides it. A second argument for launching lower: refunds
reverse the creator's share with no stated cap and are deducted from future payouts.

**The staged zip had drifted and was rebuilt.** `/Volumes/DevSSD/projects/AI_PODCAST_SKILL`
is a staging folder from the third pass, not another checkout. Its zip was still v1.1.0 —
no AI disclosure, no disclosure check in the validator, and the old token budget that
truncated scripts — while the source had moved to v1.2.0. Uploading it would have shipped
an episode generator that produces audio with no disclosure on it.
`skill/build_package.sh` now builds the zip from source, refuses to package a
`.DS_Store` or a `__pycache__`, and prints the version it built. The zip is gitignored
so it cannot drift again. The upload artifact is `skill/podcast-brain-pro-skill.zip`,
seven files. Its hash changes whenever the source does, so rebuild it and read the
hash off the script rather than trusting a value written in a document.

**The package was tested the way a reviewer would test it.** The frontmatter carries
`name` and `description`, which is Joeri's stated requirement, and `name` is
kebab-case. The disclosure lines in `script_pipeline.py`, `validate_script.py` and the
skill's reference were checked against each other across all 11 languages and agree.
A fresh-agent test produced monologue, interview and panel episodes in English, plus
interview and panel in Hindi, Tamil and Kannada; the bundled validator passed them, and
rejected the same episode with the disclosure removed.

### 8.9 What is genuinely still open

- **Send the Agensi follow-up.** `docs/AGENSI_REPLY_2.md` is drafted but **not sent**.
  The commercial terms are settled; what is still open is the refund cap, the Zoneless
  identity documents, the update turnaround, how a price change works, and any
  Agensi-side policy for media-generating skills. Nothing has been uploaded and no
  payout account exists.
- **Set up Zoneless early.** Payouts are blocked on the identity check. Stripe Connect
  does not cover India, so the route is Zoneless — USDC on Solana to the creator's own
  wallet — and the creator will need a Solana wallet and government ID.
- **Upload the listing at $12, paid from the start.** The package is built and tested;
  the upload artifact is `skill/podcast-brain-pro-skill.zip`. Build it with
  `./skill/build_package.sh`, never by hand-syncing a copy. If Joeri's answer says the
  price is locked at upload, switch to $15 instead.
- **Path A or B for the local engine.** Path A (keep the vendored VibeVoice,
  disclose it) is what ships today. Path B (move to a maintained permissive
  model) is still a tracked project, and Qwen3-TTS is now a working part of it.
  The README now points commercial users at the permissively licensed engines,
  which is the practical version of path B.
- **Tier-2 roadmap items, none started:** pronunciation dictionary, segment-level
  re-synthesis, per-speaker control panel, batch queue, C2PA manifests, a
  "Publish" panel for distribution.
- **The creator's own outreach files are gitignored, not tracked.** `MARKETING.md`,
  `PROMO_AUDIO_SCRIPT.md`, `docs/HACKER_NEWS_POST.md`, `docs/REDDIT_POSTS.md` and
  `docs/REDDIT_GUIDE.md` still say "zero cloud fees", "NVIDIA GPU" and (in some)
  Assamese. They were corrected locally in the previous session, but because they are
  gitignored the corrections live only on this machine and are not in the repo. They
  are public-facing and will be read; decide whether to un-ignore and commit the fixes.
- **The clip voice trade-off.** Clips render with Kokoro so they take seconds,
  which means a clip does not sound like the episode. If the voice match
  matters more than the wait, the clip should render with the episode's engine
  and say so.
- **Kimi/OpenRouter model currency.** The provider ids in `main.py` rot. They are
  overridable by environment variable, which is the right design, but the
  *defaults* need a periodic check — two of them were already dead when this
  pass started, and Groq's default moved to `gpt-oss-20b` in this pass.

## 9. Fifth pass — what was fixed and verified

Run 2026-11-23 after the fourth-pass option matrix. The matrix harness itself is in
`voice-service/test_option_matrix.py`.

### 9.1 Three real defects fixed

**Indic speaker labels collapsed the conversation to one voice.** When the model
writes a script in an Indic language it often labels speakers with the role word in
the target language — `সঞ্চালক:` for Host, `অতিথি:` for Guest — even when asked to
keep the label in Latin script. The parser's unknown-speaker pattern matched only
ASCII letters, so an Indic label was either spoken out loud as part of the text or the
whole line was dropped. Now an unfamiliar label is removed from the text but its words
are kept, and distinct labels map to the cast in order of first appearance. A label
that differs from a cast name only in case or punctuation is that cast member. The
prompt was tightened to say the labels are identifiers that select a voice, not words
to be spoken. `parse_conversation_script` moved from `main.py` to `script_pipeline.py`,
where the rest of the script contract lives and where it can be tested without
importing torch.

**`/podcast/generate` omitted the `language` field.** `PodcastScriptResponse` and the
endpoint return dict now include it. Without it the skill's validator defaulted to
`en` and rejected every non-English episode for missing the English disclosure, even
though the right local disclosure was spoken first. This aligns the app output with
the contract documented in `skill/podcast-brain-pro/reference/script-format.md`.

**`skill/build_package.sh` refused to build after a normal test run.** It treated any
`__pycache__` or `.DS_Store` in the source tree as fatal. Test runs create
`__pycache__`, so the build failed every time. It now excludes them from the archive
and guarantees a clean zip regardless of what junk is on disk.

### 9.2 What was verified

- **102 backend unit tests pass** (`test_script_pipeline`, `test_audio_pipeline`,
  `test_content_pipeline`, `test_dialogue_paths`, `test_backend_utils`). 35 new parser
  tests cover Bengali, Kannada, Tamil, Telugu, Hindi, Marathi, Gujarati, Punjabi,
  Malayalam, Odia and mixed canonical/localised labels.
- **All 11 supported languages produce two-host interview scripts.** The backend was
  asked for a 2-minute interview in every language the app supports; every result had
  distinct Host and Guest turns and the AI disclosure was spoken in the right language.
- **The packaged validator accepts the app's own output.** Before the language-field
  fix, English passed and every Indic language failed the disclosure check. After the
  fix, English, Hindi, Kannada, Tamil, Bengali and Odia all pass the validator bundled
  in `skill/podcast-brain-pro/scripts/validate_script.py`.
- **The skill package builds cleanly.** `./skill/build_package.sh` now produces a
  seven-file zip even after unit tests have run. The staging folder at
  `/Volumes/DevSSD/projects/AI_PODCAST_SKILL` was synced from it.
- **The frontend renders.** Both the studio (`/`) and the landing page (`/landing`)
  load in a headless browser with no Next.js error overlay, all images complete, and
  all audio elements error-free.

### 9.3 Option matrix result

The full combinatorial matrix ran to completion after the fixes:

```
TOTAL 62  PASS 62  FAIL 0
```

It covered all three formats, five durations, all 11 languages, all six delivery
styles, content extras on/off, every synthesis engine, the Sarvam path for all 10
Indic languages, voice cloning consent gating, the library, the RSS feed, and 11
validation cases. Every cell passed.

The earlier targeted checks that showed short Indic scripts and Latin-script-token
warnings were from the stricter skill validator, not from the option matrix itself.
The matrix measures backend behaviour; the validator measures marketplace-readiness.
Both are green for the tested languages after this pass.

### 9.4 What is still genuinely open after this pass

- **Send the Agensi follow-up.** `docs/AGENSI_REPLY_2.md` is drafted but not sent.
- **Upload the listing.** The package is built; the artifact is
  `skill/podcast-brain-pro-skill.zip`. Price is $12 unless Joeri says the price is
  locked at upload, in which case use $15.
- **Short-script retry for Indic languages.** Optional, but the matrix makes it clear
  the current behaviour is inconsistent.
- **Decide whether to commit the corrected outreach files.** They are gitignored and
  live only on this machine.

