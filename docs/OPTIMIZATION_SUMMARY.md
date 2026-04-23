# Audio Generation Optimization Summary

> Date: 2026-04-21  
> Target Hardware: Mac M4 with 24 GB RAM  
> Problem: Longform TTS (>5 min, 2–3 speakers) hanging or crashing

---

## Root Causes Identified

### 1. Event Loop Blocking ("Socket Hang Up")
**Location:** `voice-service/main.py` — `/tts/longform` endpoint  
**Issue:** `model.generate()` is a CPU/GPU-blocking synchronous call that runs for 5–10 minutes inside an `async def` endpoint. This blocks the asyncio event loop, making the entire FastAPI server unresponsive. The frontend sees `Error: socket hang up` (1,172 occurrences in `frontend.log`).

### 2. MPS Memory Accumulation
**Location:** `vibevoice-src/.../modeling_vibevoice_inference.py` — `generate()` + `sample_speech_tokens()`  
**Issue:** Apple Silicon MPS backend does **not** release memory automatically during long generations. The diffusion loop creates large intermediate activation tensors (18–22 GB spikes). Between chunks, memory was never flushed, leading to swap thrashing and eventual OOM/crash.

### 3. Over-Generous Chunk Sizes
**Location:** `voice-service/main.py`  
**Issue:** Default `MAX_LONGFORM_WORDS_MPS=500` was too large for 24 GB systems. A 586-word chunk still took ~515 seconds and nearly maxed out RAM.

### 4. Excessive Diffusion Steps
**Location:** `voice-service/main.py` — `load_longform_tts()`  
**Issue:** Hardcoded `ddpm_inference_steps=10` for longform. Each speech token requires 10 forward passes through the diffusion head. With hundreds of speech tokens per long script, this adds up to thousands of diffusion steps.

### 5. No Max Token Cap
**Location:** `voice-service/main.py` — `model.generate(..., max_new_tokens=None)`  
**Issue:** `None` allows the model to generate up to `max_position_embeddings` (65,536 tokens). For buggy inputs or edge cases, this could cause runaway generation.

---

## Optimizations Applied

### 1. Non-Blocking Generation (Thread Pool)
**File:** `voice-service/main.py`
- Added `ThreadPoolExecutor(max_workers=2)` dedicated to TTS workers.
- Extracted all blocking logic into `_do_tts_longform_sync()`.
- The async endpoint now calls `await asyncio.to_thread(_do_tts_longform_sync, ...)`.
- **Result:** FastAPI stays responsive. Frontend no longer gets "socket hang up" during 10+ minute generations. Health checks, model status, and other endpoints continue to work.

### 2. Aggressive MPS Memory Management
**File:** `voice-service/main.py`
- Added `_mps_cleanup()` helper that calls `torch.mps.empty_cache()` + `gc.collect()`.
- Called automatically after **every chunk** and in a `finally` block after generation.
- Added a **background thread** (`_periodic_mps_cache_clear`) that flushes MPS cache every 45 seconds during active generation.
- **Result:** Prevents memory accumulation across chunks. Keeps RAM usage bounded on 24 GB systems.

### 3. Smaller Default Chunks
**File:** `voice-service/main.py`
- `MAX_LONGFORM_WORDS_MPS`: `500` → `350`
- `MAX_LONGFORM_WORDS_CPU`: `400` → `300`
- Both are overridable via environment variables.
- **Result:** Each chunk uses less memory, stays further from the 18–22 GB spike threshold.

### 4. Reduced Diffusion Steps
**File:** `voice-service/main.py`
- `LONGFORM_DDPM_STEPS` environment variable added (default: `5`, previously hardcoded `10`).
- Lowering to `3` is possible for fastest generation; `10` is still available for maximum quality.
- **Result:** ~2× faster generation (estimated). A 400-word script that took ~400 sec should now take ~200–250 sec.

### 5. Max Token Safety Limit
**File:** `voice-service/main.py`
- Replaced `max_new_tokens=None` with a heuristic cap:
  ```python
  estimated_tokens = min(int(len(full_script) * 2.5) + 512, 8192)
  ```
- **Result:** Prevents runaway generation. 8192 is more than sufficient for any realistic chunk.

### 6. `torch.inference_mode()` Context
**File:** `voice-service/main.py`
- Wrapped all `model.generate()` calls in `torch.inference_mode()` (slightly more efficient than `torch.no_grad()` for inference).

### 7. Updated Frontend Estimates
**File:** `frontend/app/page.tsx`
- Longform time estimate: `~10–20 min` → `~5–15 min`
- Progress RTF factor: `5.5` → `4.0`
- Status messages updated accordingly.

### 8. Updated Documentation
**Files:** `docs/SETUP.md`, `docs/ARCHITECTURE.md`, `README.md`, `voice-service/.env.example`
- New environment variables documented.
- Hardware requirements table updated.
- Troubleshooting section expanded with tuning guidance.

---

## New Environment Variables

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `LONGFORM_DDPM_STEPS` | `5` | `3`–`10` | Diffusion steps per speech token. Lower = faster. |
| `MAX_LONGFORM_WORDS_MPS` | `350` | `200`–`600` | Chunk size on Apple Silicon. Lower = less RAM. |
| `MAX_LONGFORM_WORDS_CPU` | `300` | `200`–`500` | Chunk size on CPU. |

### Recommended Tuning for 24 GB Mac M4

```bash
# For 5–10 min multi-speaker audio (balanced)
export LONGFORM_DDPM_STEPS=5
export MAX_LONGFORM_WORDS_MPS=350

# For 10+ min audio or if you still hit memory pressure
export LONGFORM_DDPM_STEPS=3
export MAX_LONGFORM_WORDS_MPS=250
```

---

## Expected Performance

| Scenario | Before | After (5 steps, 350 words) |
|----------|--------|---------------------------|
| 3 min, 2 speakers | ~6–7 min gen | ~3–4 min gen |
| 5 min, 3 speakers | ~9–10 min gen / crash | ~5–7 min gen |
| 10 min, 3 speakers | Hang / OOM | ~10–15 min gen (chunked) |
| Server responsive? | ❌ No (socket hang up) | ✅ Yes |

---

## Files Modified

- `voice-service/main.py` — Core optimizations (thread pool, MPS cleanup, chunk sizes, DDPM steps, token limits)
- `voice-service/.env.example` — New env vars documented
- `frontend/app/page.tsx` — Updated time estimates
- `docs/SETUP.md` — Updated hardware guidance & troubleshooting
- `docs/ARCHITECTURE.md` — Updated speed table
- `README.md` — Updated speed table

## Pending / Future Work

- **Hybrid precision:** Run LM in `float16` but diffusion head in `float32` to avoid MPS float16 artifacts while saving memory.
- **KV cache trimming:** For very long single-pass generation, trim old KV cache entries to bound memory growth.
- **Streaming longform:** Stream audio chunks to the frontend as they complete instead of waiting for full stitching.
- **Process isolation:** Run TTS generation in a separate subprocess so an MPS crash doesn't bring down the whole backend.
