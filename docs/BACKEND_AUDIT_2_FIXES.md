# Second backend audit — findings, verdicts and fixes

Date: 2026-11-22
Source: a read-only review agent that audited `voice-service/main.py`,
`rss_generator.py` and `start.sh` after the redesign pass (it ran for ~2 hours and
returned 2 critical, 8 high, 15 medium and 24 low findings).

This document records which findings were correct, which were **wrong**, and what
changed as a result. It exists so the next reviewer can check the reasoning instead of
repeating the audit.

---

## 1. Two findings were false positives

### "H1 — `_stitch_wav_bytes()` drops the last gap and mis-indexes the rest" — **incorrect**

The audit claimed the gap list is off by one. The code:

```python
final = segments[0]
for index, seg in enumerate(segments[1:]):
    gap = gaps_ms[index] if gaps_ms and index < len(gaps_ms) else silence_ms
```

`gaps_ms[i]` is defined as the silence **after** segment `i`. On the first iteration
`index` is 0 and `seg` is `segments[1]`, so `gaps_ms[0]` — the pause after segment 0 —
is inserted between segment 0 and segment 1. That is exactly where the author put it.
"Before segment 1" and "between 0 and 1" are the same position; the audit treated them
as different.

The last entry being unused is also correct: a pause after the final segment would be
trailing silence at the end of the file, which is not a defect.

### "H2 — the Sarvam path double-counts silence" — **incorrect**

```python
gaps_ms.append(pause_ms if last_piece else 300)
```

Every unit contributes its real pause on its **last** piece, and 300 ms between the
interior pieces of the same unit. The audit read this as the pause being "replaced by
300 ms whenever the unit had to be split"; in fact the last piece always carries the
unit's full pause.

**No change was made for either finding.** They are recorded here because a future
reviewer will find the same code and may reach the same conclusion.

---

## 2. Critical findings that were correct, and are fixed

### The transcript sidecar was written to the wrong directory — **fixed**

`save_to_outputs()` returns a **bare filename**, and `_save_transcript_sidecar()` built
a relative path from it, so transcripts were written into the process working directory
(`voice-service/`) instead of next to the audio. The RSS generator looks for the
sidecar beside the `.wav`, so **the Podcasting 2.0 `<podcast:transcript>` element was
never emitted** — the feature added in the previous pass was dead.

Fixed by anchoring the sidecar in `OUTPUT_DIR`. The smoke test now asserts both the
file location and that the feed advertises it.

### `.env` was never read — **fixed**

The setup guide tells users to `cp .env.example .env` and paste their key. Nothing in
the application loaded that file: no `python-dotenv` dependency and no loader anywhere.
This was the single most likely cause of "all providers failed" for a new user.

Fixed with `voice-service/env_loader.py`, a stdlib-only parser loaded at startup before
any environment-derived constant. Real environment variables still win. 11 unit tests.

### The frontend sent `style` to `/tts/realtime`, which had no such field — **fixed**

Pydantic silently dropped it, so the delivery selector did nothing on the realtime path.
`TTSRealtimeRequest.style` now exists and is threaded through to `split_units()`.

---

## 3. High and medium findings fixed in this pass

| Area | Fix |
|---|---|
| `OUTPUT_DIR` vs `OUTPUTS_DIR` | Setting `OUTPUT_DIR` used to make saved episodes unreachable. The static mount now uses the same constant as the writers |
| Config writes | Atomic (`tmp` + `os.replace`), file mode `0600`, mtime-cached reads, parse failures logged instead of silently returning no keys |
| Config validation | Non-string values now return 422 with the offending key names; the response echoes `saved` and `removed` |
| Rename/delete sidecars | `os.path.splitext` instead of `str.replace(".wav", ".json")`; the transcript sidecar is renamed and deleted with the episode |
| RSS dates | `pubDate` is real UTC instead of local time labelled `+0000` |
| RSS durations | Estimated at 48 000 B/s (24 kHz mono) instead of 176 400 B/s (44.1 kHz stereo) — a 3.7x error for episodes without metadata |
| RSS identity | A stable `episode_id` (UUID) is stored per episode and emitted as `<guid isPermaLink="false">`, so renames and host moves no longer make clients re-download everything |
| RSS channel metadata | `itunes:image`, `itunes:owner`/`email`, `itunes:summary`, channel `itunes:explicit`, `lastBuildDate`, `atom:link rel="self"` — the elements Apple requires |
| Feed base URL | Default was `localhost:9876`, a port nothing listens on. Now `localhost:8000`, and enclosure filenames are URL-quoted |
| Language fallback | A Sarvam failure that falls back to a local English voice now returns `X-TTS-Provider: vibevoice-local-fallback` and `X-Language-Fallback: true`, so a client cannot mistake it for Indic audio |
| Style vs `cfg_scale` | A style is now a **multiplier** on the caller's `cfg_scale` (`style_cfg_multiplier`), so an explicit `cfg_scale` is never silently discarded |
| ASR | Loads lazily on first request instead of returning 503 forever; `do_sample=False` (the old `do_sample=True, temperature=0.0` is rejected by transformers and is wrong for transcription); `models.get("asr")` with an explicit 503 |
| Engine/clone previews | Saved under `outputs/previews/` so they no longer appear in the episode library or the podcast feed |
| Unknown speakers | `parse_conversation_script` matches longer names first and drops lines whose prefix is not in the cast, logging the count, instead of attributing them to the previous host |
| Provider failures | `llm_chat` raises 503 with a configuration hint instead of 429, and only catches provider-shaped exceptions — a `TypeError` in our own code is now a 500, not eight "provider failures" |
| Groq status | A 5xx after retries reports 503, not "rate-limited" |
| MPS cache thread | It waited on the wrong event and exited on its first iteration, so the cache was never cleared on a timer. A separate stop event fixes it, and `stop_mps_cache_clear()` now signals it |
| Full GC pressure | `gc.collect()` runs every fourth cleanup instead of after every segment |
| Loudness parsing | Regex with an explicit unit group instead of `rstrip()` character stripping; `loudness_normalised` is recorded in the episode metadata so a missing ffmpeg is visible |
| Dead code | Removed `chunk_units`, `cloning_engines`, the unused `numpy` and `strip_directives` imports; `voice_paths_by_id` is now used instead of a hand-built dict |
| Bind address | `start.sh` binds `127.0.0.1` by default with a `HOST` override, `set -e`, and a missing-venv message |
| Setup guide | GitHub token instructions removed, current providers listed, `.env` behaviour documented, localhost binding and `PUBLIC_BASE_URL`/`PODCAST_IMAGE_URL`/`PODCAST_EMAIL` documented |
| Short scripts | `/podcast/generate` now returns `target_words` and `under_target`; the studio shows "shorter than requested" |

---

## 4. Verification

```
python3 -m unittest test_backend_utils test_script_pipeline
# 41 tests, all passing

# API smoke test (VibeVoice modules stubbed, everything else real)
# 14 checks: health, /engines with health, feed + atom link + lastBuildDate,
# empty-script rejection, config 422 on non-string, config save echo, key file 0600,
# transcript sidecar location, feed advertises the transcript, stable episode_id.
# All passing.

cd frontend && npx tsc --noEmit && npm run build
# clean
```

---

## 5. Findings deliberately not acted on, with the reason

| Finding | Why not |
|---|---|
| H1 / H2 gap indexing | False positives, see section 1 |
| Token authentication in front of `/config`, `/podcast/*`, `/outputs` | Real issue, but the minimal correct fix is the localhost bind, which is done. A token layer is a product decision (it changes every client, including the skill) and belongs on the roadmap, not in a bug-fix pass |
| `mask_key` reveals 8 characters of each key | Accepted for now: the service binds localhost. Revisit if a token layer is added |
| ASR `dtype=` / `device_map` / `trust_remote_code` | Not changed: these paths cannot be executed here, and the loading code is delicate. The memory concern (fp32 on a 7B model) is real and is on the roadmap |
| ASR model eviction from `models` | An LRU/eviction policy is a design change; the memory pressure is documented |
| OpenRouter model choice cached forever, arbitrary sort | Improvement, not a defect: the fallback works and is overridable with `OPENROUTER_MODEL`. Left as a roadmap item |
| `get_cache_size` walks the HF cache three times per status call | Performance nit; the status poll is now 15 s and visibility-gated on the frontend |
| `is_model_cached` file variants | Only affects exotic weight layouts |
| `_finalize_audio` mutates the caller's metadata dict | Documented behaviour; the duration is now computed in one place |
| `chunk_text_by_sentences` max chars vs Sarvam's real limit | Needs a live Sarvam key to determine the correct value |
| `groq_max_tokens` variable name | Cosmetic |
| Untracked user notes mentioning GitHub Models | Those files belong to the user and were left alone |

---

## 6. Still unverified

Nothing in this pass executed a VibeVoice or Sarvam model. The audio paths are covered
by unit tests and the stubbed API smoke test only. The Kokoro engine remains the only
engine that has produced real audio in these sessions.
