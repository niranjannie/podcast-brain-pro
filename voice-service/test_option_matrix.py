#!/usr/bin/env python3
"""Exercise every user-facing option of Podcast Brain Pro against a running backend.

Run the backend first, then:

    cd voice-service && .venv/bin/python test_option_matrix.py

It covers the option matrix a user can pick in the studio: format (one, two or
three hosts), duration (2 to 30 minutes), all 11 languages, all 6 delivery
styles, content extras on and off, every synthesis engine, the Sarvam path for
every Indic language, voice cloning with its consent gate, the library, the RSS
feed, and the validation of bad input.

Exits non-zero if any cell fails, so it can be run in CI.
"""

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"

TOPIC = "How Indian cities plan for monsoon flooding"

LANGUAGES = [
    ("en", "English"),
    ("hi-IN", "Hindi"),
    ("ta-IN", "Tamil"),
    ("te-IN", "Telugu"),
    ("kn-IN", "Kannada"),
    ("bn-IN", "Bengali"),
    ("mr-IN", "Marathi"),
    ("gu-IN", "Gujarati"),
    ("ml-IN", "Malayalam"),
    ("pa-IN", "Punjabi"),
    ("od-IN", "Odia"),
]

STYLES = ["neutral", "calm", "narrative", "serious", "warm", "excited"]

# The Indic languages Sarvam speaks, with the code Sarvam itself expects.
SARVAM_CODES = [
    ("hi-IN", "Hindi"), ("ta-IN", "Tamil"), ("te-IN", "Telugu"),
    ("kn-IN", "Kannada"), ("bn-IN", "Bengali"), ("mr-IN", "Marathi"),
    ("gu-IN", "Gujarati"), ("ml-IN", "Malayalam"), ("pa-IN", "Punjabi"),
    ("od-IN", "Odia"),
]

RESULTS = []


def call(path, payload=None, timeout=600):
    """Call the backend. Returns (status, parsed_body, seconds, byte_length)."""
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        BASE + path,
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json"},
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            elapsed = time.time() - started
            if "json" in response.headers.get("Content-Type", ""):
                return response.status, json.loads(body), elapsed, len(body)
            return response.status, None, elapsed, len(body)
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace")
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = body[:300]
        return error.code, parsed, time.time() - started, len(body)
    except Exception as error:  # connection refused, timeout, reset
        return 0, f"{type(error).__name__}: {error}", time.time() - started, 0


def record(group, name, ok, detail, seconds):
    RESULTS.append({"group": group, "name": name, "ok": ok,
                    "detail": detail, "seconds": round(seconds, 1)})
    print(f"{'PASS' if ok else 'FAIL'} | {group:12} | {name:34} | {seconds:6.1f}s | {detail}",
          flush=True)


def script_case(group, label, payload, expect_hosts=None, expect_native=None):
    """Generate a script and check it has content, the right shape and the right language."""
    status, body, seconds, _ = call("/podcast/generate", payload)
    if status != 200:
        record(group, label, False, f"HTTP {status}: {str(body)[:170]}", seconds)
        return None
    script = (body or {}).get("script") or []
    words = (body or {}).get("word_count", 0)
    speakers = {turn.get("speaker") for turn in script}
    text = " ".join(turn.get("content", "") for turn in script)

    if expect_hosts is not None and len(speakers) < expect_hosts:
        record(group, label, False,
               f"expected {expect_hosts} hosts, got {sorted(speakers)}", seconds)
        return body

    if expect_native:
        latin = sum(1 for char in text if char.isascii() and char.isalpha())
        letters = sum(1 for char in text if char.isalpha()) or 1
        if latin / letters > 0.4:
            record(group, label, False,
                   f"script is {latin/letters:.0%} Latin characters", seconds)
            return body

    record(group, label, words > 0,
           f"turns={len(script)} hosts={len(speakers)} words={words}", seconds)
    return body


def main():
    print("=" * 100)
    print("PODCAST BRAIN PRO — OPTION MATRIX")
    print("=" * 100)

    print("\n--- FORMATS: one, two and three hosts ---")
    for fmt, hosts in [("monologue", 1), ("interview", 2), ("panel", 3)]:
        script_case("format", f"{fmt} ({hosts} host)", {
            "topic": TOPIC, "duration_minutes": 2, "format": fmt,
            "language": "en", "include_extras": False}, expect_hosts=hosts)

    print("\n--- DURATIONS ---")
    for minutes in [2, 5, 10, 15, 30]:
        script_case("duration", f"{minutes} min", {
            "topic": TOPIC, "duration_minutes": minutes, "format": "monologue",
            "language": "en", "include_extras": False})

    print("\n--- LANGUAGES (all 11) ---")
    for code, name in LANGUAGES:
        script_case("language", f"{code} ({name})", {
            "topic": TOPIC, "duration_minutes": 2, "format": "interview",
            "language": code, "include_extras": False},
            expect_hosts=2, expect_native=(code != "en"))

    print("\n--- DELIVERY STYLES (all 6) ---")
    for style in STYLES:
        script_case("style", style, {
            "topic": TOPIC, "duration_minutes": 2, "format": "monologue",
            "language": "en", "style": style, "include_extras": False})

    print("\n--- CONTENT EXTRAS ---")
    body = script_case("extras", "include_extras=true", {
        "topic": TOPIC, "duration_minutes": 5, "format": "interview",
        "language": "en", "include_extras": True})
    if body:
        extras = (body or {}).get("extras") or {}
        needed = ["title", "summary", "description", "takeaways",
                  "social_captions", "chapters", "social_clips"]
        missing = [key for key in needed if not extras.get(key)]
        record("extras", "extras payload complete", not missing,
               f"missing={missing} chapters={len(extras.get('chapters') or [])} "
               f"clips={len(extras.get('social_clips') or [])}", 0)
        error = (body or {}).get("extras_error")
        record("extras", "no extras error", not error, str(error or "clean")[:150], 0)

    body = script_case("extras", "include_extras=false", {
        "topic": TOPIC, "duration_minutes": 5, "format": "interview",
        "language": "en", "include_extras": False})
    if body:
        extras_value = (body or {}).get("extras")
        record("extras", "extras omitted when off", extras_value is None,
               f"extras={type(extras_value).__name__}", 0)

    print("\n--- ENGINES ---")
    line = "The monsoon arrives in June, and with it the work of draining a city."
    # Vibevoice has its own endpoints (/tts/longform, /tts/realtime).
    for engine, voice in [("kokoro", "af_bella"), ("qwen3-tts", "Ryan")]:
        status, body, seconds, size = call("/tts/engine", {
            "text": line, "engine": engine, "voice": voice,
            "style": "neutral", "save_to_disk": False})
        record("engine", f"tts/engine {engine}", status == 200 and size > 1000,
               f"HTTP {status} bytes={size}", seconds)

    status, catalogue, _, _ = call("/voices")
    cloned = []
    if status == 200:
        voices = catalogue.get("voices", catalogue) if isinstance(catalogue, dict) else catalogue
        cloned = [v for v in voices.get("cloned", []) if v.get("engine") == "chatterbox"]
    if cloned:
        status, body, seconds, size = call("/tts/engine", {
            "text": line, "engine": "chatterbox", "voice": cloned[0]["id"],
            "style": "neutral", "save_to_disk": False})
        record("engine", "tts/engine chatterbox", status == 200 and size > 1000,
               f"HTTP {status} bytes={size}", seconds)
    else:
        record("engine", "tts/engine chatterbox", False,
               "no consented chatterbox voice to test with", 0)

    status, body, seconds, _ = call("/tts/engine", {
        "text": line, "engine": "chatterbox", "save_to_disk": False})
    record("engine", "chatterbox without a voice -> 4xx", 400 <= status < 500,
           f"HTTP {status}: {str(body)[:110]}", seconds)

    print("\n--- LONGFORM: two hosts ---")
    script = [
        {"speaker": "Host", "content": "Welcome to the show about monsoon planning."},
        {"speaker": "Guest", "content": "Thanks for having me. Cities face a hard problem."},
        {"speaker": "Host", "content": "What would you change first?"},
        {"speaker": "Guest", "content": "Better drains, and honest data about flooding."},
    ]
    for engine in ["kokoro", "qwen3-tts"]:
        status, body, seconds, size = call("/tts/longform", {
            "script": script, "engine": engine, "language": "en",
            "save_to_disk": False, "format": "interview"})
        record("longform", f"longform {engine}", status == 200 and size > 1000,
               f"HTTP {status} bytes={size}", seconds)

    print("\n--- SARVAM: every Indic language ---")
    for code, name in SARVAM_CODES:
        status, body, seconds, size = call("/tts/sarvam", {
            "text": "A short test of the Sarvam voice.",
            "target_language_code": code, "speaker": "shubh",
            "save_to_disk": False, "language": name})
        record("sarvam", f"{code} ({name})", status == 200 and size > 500,
               f"HTTP {status} bytes={size}", seconds)

    print("\n--- VOICES, PREVIEW, CLONING ---")
    status, body, seconds, _ = call("/voices")
    counts = {}
    if status == 200:
        voices = body.get("voices", body) if isinstance(body, dict) else body
        counts = {key: len(voices.get(key, [])) for key in
                  ("longform", "streaming", "cloned", "styles")}
    record("voices", "GET /voices", status == 200 and counts.get("streaming", 0) > 0,
           f"{counts}", seconds)

    status, body, seconds, size = call("/tts/realtime", {
        "text": "A short line to hear the voice.", "speaker_name": "Carter",
        "save_to_disk": False})
    record("voices", "voice preview", status == 200 and size > 500,
           f"HTTP {status} bytes={size}", seconds)

    # The clone endpoint is multipart: a POST with no consent flag must be refused.
    request = urllib.request.Request(
        BASE + "/tts/clone",
        data=b"",
        method="POST",
        headers={"Content-Type": "multipart/form-data; boundary=x"},
    )
    clone_started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            clone_status = response.status
            clone_body = response.read(200).decode(errors="replace")
    except urllib.error.HTTPError as error:
        clone_status = error.code
        clone_body = error.read(200).decode(errors="replace")
    except Exception as error:
        clone_status = 0
        clone_body = str(error)[:120]
    record("voices", "clone without consent -> 4xx", 400 <= clone_status < 500,
           f"HTTP {clone_status}: {clone_body[:110]}", time.time() - clone_started)

    print("\n--- LIBRARY AND FEED ---")
    status, body, seconds, _ = call("/podcast/history?limit=5")
    record("library", "GET /podcast/history", status == 200, f"HTTP {status}", seconds)
    status, body, seconds, size = call("/feed/podcast.rss")
    record("library", "GET /feed/podcast.rss", status == 200 and size > 200,
           f"HTTP {status} bytes={size}", seconds)

    print("\n--- VALIDATION: bad input must be a 4xx, never a 500 ---")
    bad_cases = [
        ("unknown format", "/podcast/generate", {"topic": "x", "format": "debate"}),
        ("unknown language", "/podcast/generate", {"topic": "x", "language": "xx-YY"}),
        ("duration over 30", "/podcast/generate", {"topic": "x", "duration_minutes": 99}),
        ("duration under 2", "/podcast/generate", {"topic": "x", "duration_minutes": 1}),
        ("unknown style", "/podcast/generate", {"topic": "x", "style": "sarcastic"}),
        ("empty topic", "/podcast/generate", {"topic": "", "duration_minutes": 2}),
        ("unknown engine", "/tts/engine", {"text": "hi", "engine": "not-a-real-engine"}),
        ("unknown sarvam language", "/tts/sarvam", {"text": "x", "target_language_code": "zz-ZZ"}),
        ("unknown sarvam model", "/tts/sarvam", {"text": "x", "model": "bulbul:v9"}),
        ("empty script", "/tts/longform", {"script": []}),
        ("speed out of range", "/tts/engine", {"text": "hi", "engine": "kokoro", "speed": 99}),
    ]
    for label, path, payload in bad_cases:
        status, body, seconds, _ = call(path, payload, timeout=120)
        record("validation", label, 400 <= status < 500,
               f"HTTP {status}: {str(body)[:110]}", seconds)

    print("\n" + "=" * 100)
    passed = sum(1 for row in RESULTS if row["ok"])
    failed = [row for row in RESULTS if not row["ok"]]
    print(f"TOTAL {len(RESULTS)}  PASS {passed}  FAIL {len(failed)}")
    print("=" * 100)
    if failed:
        print("\nFAILURES:")
        for row in failed:
            print(f"  [{row['group']}] {row['name']}\n      {row['detail']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
