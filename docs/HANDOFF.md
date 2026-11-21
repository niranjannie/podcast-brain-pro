# Handoff — context for the next session

> **Update, second pass (same day, different model).** A full studio redesign and a Voice
> Lab with small local engines and consent-gated voice cloning landed after this file was
> written. Read `docs/FRESH_ASSESSMENT_2026-11.md` first — it has the verdict on voice
> cloning, what was actually verified (Kokoro produced real audio through the API and the
> UI; Chatterbox is broken on Python 3.14), and what is still pending. Commits:
> `17480eb` on top of `8749286`. The review brief for an outside model is
> `docs/REVIEW_REQUEST.md`; its diff range predates the redesign.

Last updated: 2026-11-21 by the agent that ran the November 2026 audit and modernisation
pass. Read this first, then `docs/PRODUCT_AUDIT_2026-11.md` (what was broken and what
was fixed) and `docs/ROADMAP_NEXT_LEVEL.md` (what to do next).

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

# Backend logic, no models needed
cd voice-service && python3 -m unittest test_script_pipeline -v

# Backend syntax
python3 -m py_compile main.py script_pipeline.py audio_pipeline.py

# Frontend
cd ../frontend && npm install && npm run typecheck && npm run build
```

The backend cannot be imported on a machine with `transformers` 5 installed, and the
models are ~15 GB, so a full end-to-end run needs the real setup in `docs/SETUP.md` on
Apple Silicon.

---

## 6. What the next session should do, in order

1. **Reply to Agensi** with the questions in `questions-for-agensi.md` before creating a
   payout account. Do not upload anything yet.
2. **Fix the remaining UI defects** listed in section 3 of the roadmap: split the
   1900-line component, real progress, real waveform, health banner, focus trap in the
   modal.
3. **Decide path A or B** for the local TTS engine (keep the vendored VibeVoice with a
   disclosure, or move to Qwen3-TTS via `mlx-audio` / AI4Bharat Indic models).
4. **Ship the tier-1 features**: show notes, chapter markers, pronunciation dictionary,
   re-render without a new script, social clips.
5. **Add the disclosure** — an "AI-generated" line at the start of every episode and a
   note in the README — before this is used commercially or listed anywhere.

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
