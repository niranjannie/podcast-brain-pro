# Review request — Podcast Brain Pro, November 2026 pass

**What this file is for.** It is a self-contained brief for a reviewer model that has no
memory of the session that produced the work. It states the original ask, exactly what
was changed, what was verified, what was **not** verified, the judgement calls that are
open to challenge, and the questions worth spending a strong model on. Read it end to
end before looking at the code.

**Repo:** `github.com/niranjannie/podcast-brain-pro` (public, MIT)
**Local checkout:** `/Volumes/DevSSD/projects/AI_VOICEVIBE`
**Range to review:** `ec0628f..e9e7fd5` on `master` (two commits: backend, then
frontend + docs). `git show e9e7fd5` and `git show b7981db` are the full diffs.

**Companion documents in the repo:**
- `docs/PRODUCT_AUDIT_2026-11.md` — every finding, with evidence and status
- `docs/ROADMAP_NEXT_LEVEL.md` — the ranked plan for the next level
- `docs/HANDOFF.md` — the context a next session needs

---

## 1. The original ask, verbatim

**Turn 1 (marketplace):**

> i got a mail from user to make my product alraedy publihseidn githum as skil and earn..
> i am new to this kind help me to undersrtand it better.. mail details: [the Agensi.io
> email] .. i searched somehtign in internet based on this: [analysis of the email] ..
> its frm : joeri.b@getagensi.com.. user its already in my public git account why they
> send me mail? just asking

**Turn 2 (the engineering work):**

> yes fix both the bugs in AI_VOICEVIBE and push to github and check carefully all the
> code and fix for any issues and also this code has been buillt almost 6 months before
> can you check any latest changes happnedin the ai models used and better onces to make
> ti up to date andd also the UI design with more advanced featues and voice modulations
> proper paue and expressions adnvaced way.. think fresh way adn suggest how u can make
> the product to enxt level .. before that document all the ur findings nad my ask and
> ur recomendations so next session ai agnet knows the context of htis discussion

**Turn 3 (this one):** the user asked for a file another, stronger model can use to
review the work against the original ask.

### The two named bugs

1. **`role` / `speaker` key mismatch** between the script generator and the TTS layer,
   which broke per-speaker voice mapping.
2. **README claimed Assamese**; the code supports Odia.

---

## 2. What was in scope, and what was deliberately out of scope

| In scope | Out of scope (and why) |
|---|---|
| The two named bugs | Replacing the local TTS engine (decision pending with the user) |
| A full correctness review of `voice-service/` and `frontend/` | Adding new cloud dependencies |
| Provider and model currency as of today | Any paid service enrolment (the user said they will reply to Agensi later) |
| Delivery control: pauses and expression markers | Writing the Agensi reply email (a draft exists outside the repo) |
| Podcast-ready output: loudness, transcripts, a usable RSS feed | Publishing a marketplace listing |
| Documentation a next session can pick up | Marketing copy beyond removing false claims |

---

## 3. What was changed

### 3.1 Backend — `voice-service/`

| File | Change |
|---|---|
| `script_pipeline.py` (new, 470 lines) | The single owner of the script contract: turn-key normalisation, delivery directives, sentence-aware chunking, voice resolution, segment planning |
| `audio_pipeline.py` (new) | ffmpeg loudness normalisation and ebur128 measurement |
| `test_script_pipeline.py` (new) | 23 stdlib-only tests |
| `main.py` | Longform path rewritten (global speaker numbers, per-speaker voices, honoured `voice_names`, per-segment style, pause stitching); realtime path rewritten (directives, voice matching, `Optional` coercion); Sarvam path rewritten (directives, `bulbul:v4-flash` fields, `od-IN`→`or-IN`, WAV storage); new `GET /voices`; delivery instructions added to the scriptwriter prompt; GitHub Models provider removed; every model id now env-overridable; OpenRouter fallback reads the live catalogue; RSS feed configurable; transcript sidecar; loudness normalisation on every export; empty script rejected before the model loads; dead `expand_script_if_needed` made real and opt-in; sentence splitting consolidated into the pipeline |
| `rss_generator.py` | Configurable channel metadata, Podcasting 2.0 `podcast:transcript`, `itunes:episodeType`, `itunes:explicit` |
| `requirements.txt` | `transformers>=4.51.3,<5.0.0` |
| `.env.example` | Retired key removed; model overrides; `PUBLIC_BASE_URL`; podcast channel metadata; `NORMALIZE_LOUDNESS`; `EXPAND_SHORT_SCRIPTS` |

### 3.2 Frontend — `frontend/`

| Change | Detail |
|---|---|
| Routing | `next.config.mjs` redirected `/` → `/landing`, which shadowed the studio route. `/` is the studio again; the landing page links to it |
| Settings modal | Seeded inputs with the **masked** key and posted them back, destroying every configured key. Now: empty form, mask as placeholder, explicit "Remove this key" sends `null` |
| Script generation | In-flight guard plus a run id, so a cancelled run cannot clobber a newer one |
| Audio generation | `AbortController` in a ref, a Cancel button, timer cleaned up on unmount, distinct timeout status |
| Voice cast | Populated from `GET /voices`; selections re-validated when the engine changes; duplicates avoided; the real speaker names are now sent and `voice_names` is ordered by first appearance |
| New UI | Delivery style selector, per-line pause button, "Download Script", RSS link, inline error banners instead of `alert()`, two-step delete confirmation, empty state, real progress bar width |
| Dependencies | `next@14.2.5` (security advisory) → `14.2.35`; `eslint@9` + `eslint-config-next@16` → `eslint@8.57` + `eslint-config-next@14.2.35`; `.eslintrc.json` added; `typecheck` script added |
| Deleted | `app/landing/page-conversion.tsx` (never routed, 825 lines), three unreferenced sample WAVs (25 MB) |
| Claims | "100% Free" and "AI voice clone" were false; both corrected |

### 3.3 Docs and packaging

`docs/PRODUCT_AUDIT_2026-11.md`, `docs/ROADMAP_NEXT_LEVEL.md`, `docs/HANDOFF.md`,
this file, `docs/API_KEYS.md` rewritten, `docs/ARCHITECTURE.md` updated, and
`skill/podcast-brain-pro/` (the marketplace skill package with a packaging README).

---

## 4. Verification that was actually run

| Check | Command | Result |
|---|---|---|
| Backend unit tests | `cd voice-service && python3 -m unittest test_script_pipeline -v` | 23 passed |
| Backend syntax | `python3 -m py_compile main.py script_pipeline.py audio_pipeline.py` | clean |
| Backend API smoke | Stubbed VibeVoice imports, `fastapi.testclient.TestClient` against `/health`, `/voices`, `/config`, `/feed/podcast.rss`, and two invalid `/tts/longform` payloads | 10/10 checks passed (the empty-script case returns 400 in 6 s instead of downloading 5.4 GB of weights) |
| Frontend types | `cd frontend && npx tsc --noEmit` | clean |
| Frontend build | `npm run build` | compiled, no warnings, no lint errors |
| Skill validator | `python3 skill/podcast-brain-pro/scripts/validate_script.py` on a fixture with directives | directives accepted, word-budget error reported correctly |
| External research | Provider deprecation notes, the VibeVoice repository and model card, Sarvam and podcast-host documentation | cited in `docs/PRODUCT_AUDIT_2026-11.md` |

**The smoke test script is not committed** (it stubs the model modules and is not
useful to end users). It is described in section 7 if the reviewer wants to rebuild it.

---

## 5. What was NOT verified — read this before trusting the backend

This is the most important section of this file.

1. **No episode was ever generated end to end.** The TTS models are ~15 GB and are not
   present on the review machine; the installed `transformers` is 5.x, which makes the
   vendored VibeVoice fail at import. Every TTS code path changed in this pass —
   segment planning, voice assignment, pause stitching, style-driven cfg_scale, the
   Sarvam rewrite, loudness normalisation — is **verified by unit tests and by reading
   the code, not by running audio**. This is the largest risk in the work.
2. **No human has heard the new voice assignment.** The claim "every host now gets its
   own voice" is derived from `resolve_voices()` and the VibeVoice processor's
   documented voice-sample ordering, not from listening to an episode.
3. **The backend review was a single-agent review.** A second reviewer agent was
   started for the backend and never produced a report before the session ended; the
   frontend review came from a separate agent and is in
   `docs/PRODUCT_AUDIT_2026-11.md`. **The backend has not had a second opinion.**
4. **The ASR path (`/asr/transcribe`, 14 GB model) was not audited at all.**
5. **The Sarvam cloud path was not executed** (no key, no credit). The rewrite is
   reasoned from the Sarvam v4 documentation.
6. **The landing page was not checked in a browser.** Only the build was verified.
7. **The Agensi side was not advanced.** The reply email and the question list live
   outside the repo, in `/Volumes/DevSSD/projects/AI_PODCAST_SKILL/`.

---

## 6. Open issues — everything the audits found that is still not fixed

Ordered by how much it should worry the reviewer.

### Backend

| Issue | Where | Why it matters |
|---|---|---|
| No end-to-end audio verification | `voice-service/main.py` | Section 5 item 1 |
| Vendored VibeVoice TTS code is upstream-deleted and unsupported | `vibevoice-src/` | A future "update dependencies" action would break the app. The model card also restricts use to research and embeds an audible AI disclaimer plus a watermark |
| `_tts_local_fallback_sync` (the Sarvam → local fallback) was not touched | `main.py` | It still takes a plain string, so it does not honour delivery directives, and it was never exercised |
| The 15/30-minute chapter outline is computed and then discarded | `main.py` (`chapters` in `DURATION_CONFIG`) | A ready-made feature that throws its result away |
| `save_to_outputs` still derives the filename from the topic only | `main.py` | Two episodes on the same topic in the same second collide |
| Loudness normalisation is single-pass `loudnorm` | `audio_pipeline.py` | Single-pass is approximate; a two-pass pass would be more accurate |

### Frontend

| Issue | Where | Why it matters |
|---|---|---|
| The studio is still one 1900-line component with ~40 state hooks | `frontend/app/page.tsx` | Every keystroke re-renders the history list and the waveform |
| The progress estimate is still a client-side guess | `app/page.tsx` (`generateAudio`) | The backend returns `X-Chunks-Used` and `X-Gen-Time-Sec`; the UI ignores them and animates a fabricated countdown |
| The waveform is decorative | `app/page.tsx` | 24 randomly animated bars next to a real audio element |
| No backend liveness check | `app/page.tsx` | A stopped backend looks exactly like "the model is downloading" |
| Accessibility gaps | `app/page.tsx`, `components/ui/modal.tsx` | No `id`/`htmlFor` pairing on most inputs, no focus trap or focus restore in the modal, no `aria-pressed` on the segmented duration control, icon-only buttons with only `title` |
| The Indic path collapses the script into one blob with one voice | `app/page.tsx` (`isIndic` branch) | The Voice Cast UI implies multi-host Indian episodes that do not happen |
| The Indic path is disabled without a Sarvam key | `app/page.tsx` | The backend can fall back to local VibeVoice, but the UI blocks the attempt |
| 62 MB of sample audio still ships | `frontend/public/samples` | Six `<audio preload="metadata">` elements mount at once; each play pulls 7-14 MB |
| History is capped at 20 with no search | `app/page.tsx` | The backend allows `limit` up to 100 |
| Rename pre-fills the full filename including `.wav` | `app/page.tsx` | The backend appends `.wav` again |
| `Button asChild` spreads `type="button"` onto anchors | `components/ui/button.tsx` | Invalid attribute on every link-styled button |
| Dead code | `components/ui/progress.tsx`, `tailwind.config.ts` (`pulse-slow`, `gradient-x`), `globals.css` (`.focus-ring`), `lib/gsap.ts` registers `useGSAP` as a GSAP plugin | Small, but it misleads the next reader |
| `AudioPlayer` and `MiniPlayer` are ~230 duplicated lines | `app/landing/page.tsx` | |
| The landing page still hardcodes the GitHub URL and `localhost:3000` | `app/landing/page.tsx` | Should be `NEXT_PUBLIC_*` |
| The panel labels say "Guest 1 / Guest 2" while the values are "Guest / Expert" | `app/page.tsx` (`getSpeakers`) | |
| `formatDuration` returns an empty string for unknown durations | `lib/utils.ts` | The badge silently disappears |
| Three different word-count formulas | `app/page.tsx` | Two were unified in this pass; one remains |

### Repo hygiene

- `docs/REDDIT_POSTS.md` and `docs/SETUP_TROUBLESHOOTING.md` are untracked (gitignored)
  and still mention GitHub Models and Assamese. They were left alone because they are
  the user's files.
- `docs/REDDIT_GUIDE.md`, `docs/LINKEDIN_REPLY.md` and `req/` are untracked user files.
- `frontend/frontend.log` was mentioned in an audit as committed; it is not tracked in
  the current tree.

---

## 7. Judgement calls the reviewer should challenge

These are the decisions where a stronger reviewer might disagree with the agent that
made them. Each is stated with its reasoning so it can be argued with, not just read.

1. **`normalize_turns()` accepts both `speaker` and `role` instead of migrating to one
   key.** Reasoning: the frontend and the marketplace skill both send turns, and a
   hard cut would break external callers of `/tts/longform`. The cost is that two
   spellings remain legal forever. If the reviewer prefers a single key, the change is
   small: normalise in the request model and drop the fallback.
2. **Delivery style maps to `cfg_scale` on the local engine.** VibeVoice exposes no
   emotion or prosody API, so a "style" is a guidance-scale nudge plus, on the Sarvam
   path, a pace and temperature change. The UI presents it as a tone control. If that is
   overselling, rename the control to something honest such as "Guidance".
3. **Pauses are rendered by splitting the synthesis into segments and stitching real
   silence between them.** This costs one model call per pause. The alternative
   (post-hoc silence insertion) cannot know where in the audio the marker landed.
4. **Loudness normalisation is on by default.** It changes the bytes of every export,
   which may surprise anyone comparing old and new episodes. `NORMALIZE_LOUDNESS=false`
   turns it off.
5. **The OpenRouter fallback now makes a network call to read the model catalogue.**
   That is one extra request the first time it is needed, cached afterwards, and it
   replaces a hard coded id that was already dead.
6. **The frontend now sends real speaker names instead of pre-mapping to voice names.**
   This changes the wire format of `/tts/longform` for anyone calling it directly: a
   caller that used to send `role: "en-Carter_man"` still works, because the backend
   still matches names, but a caller that sent `role: "Host"` now gets a name match
   against the voice files, which is the intended behaviour.
7. **The redirect removal changes the meaning of `/`.** The marketing page was
   previously the default route and the README says the app runs at `localhost:3000`.
   The reviewer may prefer `/studio` with `/` staying the landing page; that is a
   one-line change plus updating the README.
8. **The frontend now depends on the backend being reachable for `/voices`.** If the
   backend is down the hard coded voice lists are used as a fallback, so the UI still
   renders.

---

## 8. Questions worth a strong model

Answering these is worth more than re-reading the diff.

1. **Is the voice-to-speaker mapping in `script_pipeline.resolve_voices()` actually
   correct for the VibeVoice processor?** Read
   `vibevoice-src/vibevoice/processor/vibevoice_processor.py` around `_process_single`
   and `_create_voice_prompt`, and confirm that the order of `voice_samples` maps to
   `Speaker 1`, `Speaker 2`, ... as the code assumes, including the `list(set(...))`
   ordering of `all_speakers`. If that assumption is wrong, every multi-speaker episode
   has swapped voices.
2. **Does the global speaker numbering survive chunking?** The chunks are generated in
   separate model calls, and each call re-parses `Speaker N:` labels. Check that a
   segment that contains only `Speaker 2` still receives the second voice sample, and
   that `voice_samples[:len(all_speakers)]` in the processor does not truncate to the
   wrong slice when a segment contains only one speaker.
3. **Are the delivery directives safe inside the prompt?** The script content is fed
   back into an LLM prompt and into the TTS text. Can a directive survive into the
   spoken audio as literal text, or break the `Speaker N:` parsing?
4. **Is the loudness pass safe for every input?** `normalize_loudness()` pipes bytes
   through ffmpeg and returns the original bytes on any failure. Check the WAV parsing
   and the `-ar 24000 -ac 1` resampling for the sample rate and channel layout the
   local model actually produces.
5. **Does the Sarvam v4 payload match the current API?** The model accepts `pitch`,
   `loudness` and `dict_id` for v4 only, and the v3/v4 speaker id formats are
   incompatible. Verify against the Sarvam documentation that the field names, the
   `model` value and the persona ids are right, and that `or-IN` is the code Sarvam
   wants for Odia.
6. **Can the new `voice_names` contract be satisfied by the frontend in every case?**
   The frontend computes the voice list from the order the speakers first appear in the
   script, while the backend resolves voices from the order the speakers appear in the
   normalised turns. Confirm these are always the same order, including after the user
   edits a speaker name in the script editor.
7. **Is there any remaining path where a turn's speaker is lost?** Search for every
   place that reads `speaker` or `role` in `voice-service/` and confirm each one goes
   through `normalize_turns()` or `turn_speaker()`.
8. **Does the settings modal now behave correctly in every case?** The form starts
   empty, sends only non-empty values, and sends `null` for keys the user explicitly
   removed. Confirm that the backend's `POST /config` semantics match that intent and
   that no key can be deleted by accident.
9. **Does the frontend build genuinely pass lint, or was a rule disabled to get there?**
   `frontend/.eslintrc.json` turns off `@next/next/no-img-element`. Check whether that
   rule was the only reason a build was failing, and whether the remaining lint output
   is clean or merely quiet.
10. **Is anything in `docs/PRODUCT_AUDIT_2026-11.md` wrong or overstated?** Every claim
    in it was checked against a primary source or reproduced locally, but a reviewer
    should re-check the external facts: the retirement dates, the Sarvam model names,
    the podcast loudness target and the Podcasting 2.0 tag.
11. **What is the smallest set of changes that would make the product safe to sell?**
    The VibeVoice disclosure obligation, a public `PUBLIC_BASE_URL` for the feed, and a
    loudness-verified export are the candidates.

---

## 9. Facts the reviewer should not have to re-derive

These were established from primary sources during the session; re-checking them costs
time and network.

- **Agensi marketplace terms** (read from `agensi.io/terms`): creator keeps 70% of net,
  $1 minimum price, one-time listings are credit-only under $5 and credit needs a $5
  top-up, payout threshold $3.50 via Stripe Connect or Zoneless (USDC on Solana), 30-day
  money-back guarantee with the creator share reversed, tool calls earn the creator
  nothing (4.8), max 10 Agensi tools per skill (6.5), creator keeps full ownership and
  grants a non-exclusive licence (8.1), linking your own repo is allowed but upselling a
  paid off-platform version is banned (6.3a).
- **Provider retirements**: GitHub Models inference API retired 30 Jul 2026; Groq
  `llama-3.3-70b-versatile` shut down 16 Aug 2026; Gemini `gemini-2.0-flash` retired
  1 Jun 2026; DeepSeek `deepseek-chat` alias discontinued 24 Jul 2026; the OpenRouter free
  id `mistralai/mistral-7b-instruct:free` has no provider left.
- **VibeVoice upstream**: the TTS inference module is gone (HTTP 404 upstream) and the
  upstream README disables the TTS path "due to widespread misuse"; the ASR side is
  active. The weights remain MIT but the model card says research use only, English and
  Chinese only, and the output carries an audible AI disclaimer plus an imperceptible
  watermark.
- **transformers 5 breaks the vendored VibeVoice at import** with
  `ValueError: ... is already used by a Transformers model`. Reproduced locally.

---

## 10. How to verify this work locally

```bash
cd /Volumes/DevSSD/projects/AI_VOICEVIBE

# Backend logic, no models required
cd voice-service && python3 -m unittest test_script_pipeline -v

# Backend syntax
python3 -m py_compile main.py script_pipeline.py audio_pipeline.py

# Frontend
cd ../frontend && npm install && npm run typecheck && npm run build

# The backend cannot be imported with transformers 5 installed, and the models are
# ~15 GB, so a full run needs the setup in docs/SETUP.md on Apple Silicon.
```

To rebuild the API smoke test from section 4: create fake modules for
`vibevoice.modular.modeling_vibevoice_inference`,
`vibevoice.modular.modeling_vibevoice_streaming_inference`,
`vibevoice.modular.modeling_vibevoice_asr` and the three processor modules, put them in
`sys.modules` before importing `main`, then drive `fastapi.testclient.TestClient`
against `/health`, `/voices`, `/config`, `/feed/podcast.rss` and two invalid
`/tts/longform` payloads. Run it with `HF_HUB_OFFLINE=1` so no model download is
attempted.

---

## 11. Constraints the reviewer should respect

- The repository is public and MIT. Never commit keys, `user_config.json`, `.env`,
  model weights or `outputs/`.
- `vibevoice-src/` is a pinned fork of upstream code that no longer exists upstream. Do
  not "update" it.
- The user's untracked files (`docs/LINKEDIN_REPLY.md`, `docs/REDDIT_GUIDE.md`,
  `docs/SETUP_TROUBLESHOOTING.md`, `req/`) must not be deleted or committed without
  asking.
- The user decides. Where the roadmap proposes a change, it is a proposal, not an
  instruction.
