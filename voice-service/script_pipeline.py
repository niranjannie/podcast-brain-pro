"""Script contract, delivery directives and voice resolution.

Everything that turns a "script" into something the TTS layer understands lives here:
normalising turn keys, deciding who speaks when, splitting delivery directives out of
the text, chunking to fit the memory budget, and mapping speakers onto voice files.

The generator (``/podcast/generate``) emits turns keyed by ``speaker``. The TTS layer
historically read the key ``role``. Both spellings are accepted here and normalised to
``speaker`` exactly once, so the two can never drift apart again.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ============== Delivery directives ==============
# Directives live inline in the spoken text and are stripped before synthesis.
#   [[pause:0.8]]  -> insert 0.8 s of silence at that point
#   [[pause 1.5]]  -> same, space separated
#   [[style:calm]] -> switch delivery style for the rest of that turn
DIRECTIVE_RE = re.compile(
    r"\[\[\s*(pause|style)\s*(?:[:=]\s*([^\]]*?))?\s*\]\]", re.IGNORECASE
)

MAX_PAUSE_SECONDS = 10.0

# style -> how it changes synthesis. cfg_scale drives VibeVoice's guidance (lower is
# looser and more expressive), pace/temperature drive Sarvam.
STYLE_PRESETS: Dict[str, Dict[str, float]] = {
    "neutral": {"cfg_scale": 1.30, "pace": 1.00, "temperature": 0.60},
    "calm": {"cfg_scale": 1.50, "pace": 0.92, "temperature": 0.40},
    "narrative": {"cfg_scale": 1.40, "pace": 1.00, "temperature": 0.50},
    "serious": {"cfg_scale": 1.45, "pace": 0.95, "temperature": 0.35},
    "warm": {"cfg_scale": 1.35, "pace": 0.98, "temperature": 0.60},
    "excited": {"cfg_scale": 1.10, "pace": 1.12, "temperature": 0.85},
}
DEFAULT_STYLE = "neutral"


def style_params(style: Optional[str]) -> Dict[str, float]:
    """Resolve a style name to its synthesis parameters. Unknown styles fall back."""
    if not style:
        return STYLE_PRESETS[DEFAULT_STYLE]
    return STYLE_PRESETS.get(style.strip().lower(), STYLE_PRESETS[DEFAULT_STYLE])


def style_names() -> List[str]:
    return sorted(STYLE_PRESETS)


def style_cfg_multiplier(style: Optional[str]) -> float:
    """How far a style shifts the guidance scale, relative to neutral.

    A style is a nudge on the caller's own cfg_scale, never a replacement for it:
    an explicit cfg_scale in the request must still mean something when a script
    contains a style marker.
    """
    return style_params(style)["cfg_scale"] / STYLE_PRESETS[DEFAULT_STYLE]["cfg_scale"]


# ============== Turn normalisation ==============

def turn_speaker(item: Dict[str, Any], default: str = "Speaker") -> str:
    """Read the speaker name from a turn, accepting either spelling."""
    for key in ("speaker", "role"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def turn_content(item: Dict[str, Any]) -> str:
    """Read the spoken text from a turn, accepting either spelling."""
    for key in ("content", "text"):
        value = item.get(key)
        if isinstance(value, str):
            return value
    return ""


def normalize_turns(script: Any) -> List[Dict[str, str]]:
    """Normalise any accepted script shape into ``[{"speaker", "content"}, ...]``.

    Accepts ``speaker`` or ``role`` keys and ``content`` or ``text`` keys, skips turns
    without usable text, and preserves order. Never raises on malformed input.
    """
    if not isinstance(script, list):
        return []
    turns: List[Dict[str, str]] = []
    for index, item in enumerate(script):
        if not isinstance(item, dict):
            continue
        content = turn_content(item).strip()
        if not content:
            continue
        speaker = turn_speaker(item, default=f"Speaker {index + 1}")
        turns.append({"speaker": speaker, "content": content})
    return turns


def speaker_order(turns: Sequence[Dict[str, str]]) -> List[str]:
    """Unique speaker names in order of first appearance."""
    seen: List[str] = []
    for turn in turns:
        if turn["speaker"] not in seen:
            seen.append(turn["speaker"])
    return seen


# ============== Directives ==============

def strip_directives(text: str) -> str:
    """Remove delivery directives, leaving the spoken text."""
    return DIRECTIVE_RE.sub("", text).strip()


def parse_directives(content: str) -> Tuple[List[Tuple[str, Optional[str]]], str]:
    """Split content into ``(kind, value)`` directives and the remaining plain text."""
    directives: List[Tuple[str, Optional[str]]] = []

    def _collect(match: "re.Match[str]") -> str:
        kind = match.group(1).lower()
        value = (match.group(2) or "").strip()
        directives.append((kind, value or None))
        return " "

    plain = DIRECTIVE_RE.sub(_collect, content)
    return directives, " ".join(plain.split())


def split_units(content: str, default_style: str = DEFAULT_STYLE) -> List[Dict[str, Any]]:
    """Split one turn into synthesis units around pauses.

    A pause directive inserts silence after the text that precedes it, so the unit that
    carries the text before the directive is the one that records the silence. A style
    directive switches the style for the remainder of the turn. Returns a list of
    ``{"text", "style", "pause_after"}`` units; the text of each unit is directive-free.
    """
    directives, plain = parse_directives(content)
    if not directives:
        return [{"text": plain, "style": default_style, "pause_after": 0.0}] if plain else []

    units: List[Dict[str, Any]] = []
    style = default_style
    cursor = 0

    for match in DIRECTIVE_RE.finditer(content):
        text_before = content[cursor: match.start()].strip()
        cursor = match.end()
        kind = match.group(1).lower()
        value = (match.group(2) or "").strip()

        if kind == "pause":
            duration = _parse_pause_seconds(value)
            if text_before:
                units.append({"text": text_before, "style": style, "pause_after": duration})
            elif units:
                # A pause before any text extends the silence after the previous unit.
                units[-1]["pause_after"] = max(units[-1]["pause_after"], duration)
            continue

        # style directive
        if text_before:
            units.append({"text": text_before, "style": style, "pause_after": 0.0})
        style = (value or DEFAULT_STYLE).lower()
        if style not in STYLE_PRESETS:
            style = DEFAULT_STYLE

    tail = content[cursor:].strip()
    if tail:
        units.append({"text": tail, "style": style, "pause_after": 0.0})

    if not units:
        plain_text, _ = parse_directives(content)
        if plain_text:
            units.append({"text": plain_text, "style": default_style, "pause_after": 0.0})
    return units


def _parse_pause_seconds(value: Optional[str]) -> float:
    if not value:
        return 0.5
    match = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*(s|sec|ms)?\s*$", value, re.IGNORECASE)
    if not match:
        return 0.5
    number = float(match.group(1))
    unit = (match.group(2) or "s").lower()
    if unit == "ms":
        number = number / 1000.0
    return max(0.0, min(number, MAX_PAUSE_SECONDS))


# ============== Units and chunking ==============

def build_units(
    turns: Sequence[Dict[str, str]], default_style: str = DEFAULT_STYLE
) -> List[Dict[str, Any]]:
    """Expand turns into synthesis units with a stable speaker number.

    The speaker number is global across the whole script (1, 2, 3 ... in order of first
    appearance). It is what VibeVoice matches voice samples against, so it must not be
    renumbered per chunk.
    """
    order = speaker_order(turns)
    index_of = {name: index + 1 for index, name in enumerate(order)}

    units: List[Dict[str, Any]] = []
    for turn_index, turn in enumerate(turns):
        speaker = turn["speaker"]
        for unit in split_units(turn["content"], default_style=default_style):
            if not unit["text"]:
                continue
            units.append(
                {
                    "speaker": speaker,
                    "speaker_id": index_of[speaker],
                    "turn_index": turn_index,
                    "text": unit["text"],
                    "style": unit["style"],
                    "pause_after": unit["pause_after"],
                }
            )
    return units


def group_units(
    units: Sequence[Dict[str, Any]], break_before_turns: Optional[set] = None
) -> List[Dict[str, Any]]:
    """Merge consecutive units of the same speaker and style into one turn.

    A pause between two units of the same speaker keeps them apart, because the pause
    has to be rendered as silence between two separate synthesis passes.
    """
    grouped: List[Dict[str, Any]] = []
    for unit in units:
        if (
            grouped
            and grouped[-1]["speaker"] == unit["speaker"]
            and grouped[-1]["style"] == unit["style"]
            and not grouped[-1].get("pause_after")
            and (not break_before_turns or unit.get("turn_index") not in break_before_turns)
        ):
            grouped[-1]["text"] = (grouped[-1]["text"] + " " + unit["text"]).strip()
            grouped[-1]["pause_after"] = unit["pause_after"]
        else:
            grouped.append(dict(unit))
    return grouped


def units_to_script_lines(chunk: Sequence[Dict[str, Any]]) -> str:
    """Render a chunk as the ``Speaker N: text`` script the VibeVoice processor parses."""
    return "\n".join(
        f"Speaker {unit['speaker_id']}: {unit['text']}" for unit in chunk
    )


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?।])\s+")


def split_sentences(text: str) -> List[str]:
    """Split text into sentences, including Indic sentence marks."""
    parts = [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def split_monologue_turns(
    text: str, speaker: str = "Host", target_words: int = 70
) -> List[Dict[str, str]]:
    """Split a monologue into paragraph-sized turns without changing its wording."""
    groups: List[str] = []
    current: List[str] = []
    current_words = 0
    for sentence in split_sentences(text):
        words = len(sentence.split())
        if current and current_words + words > target_words:
            groups.append(" ".join(current))
            current = []
            current_words = 0
        current.append(sentence)
        current_words += words
    if current:
        groups.append(" ".join(current))
    return [{"speaker": speaker, "content": group} for group in groups if group.strip()]


def chunk_units_for_engine(
    units: Sequence[Dict[str, Any]], max_words: int
) -> List[Dict[str, Any]]:
    """Bound single-voice engine calls while preserving speaker, style and pauses.

    Sentences are grouped up to ``max_words``. An unusually long sentence is split on
    word boundaries rather than silently exceeding the model's generation limit.
    """
    max_words = max(1, int(max_words))
    bounded: List[Dict[str, Any]] = []
    for unit in units:
        text_pieces: List[str] = []
        current: List[str] = []
        current_words = 0

        def flush() -> None:
            nonlocal current, current_words
            if current:
                text_pieces.append(" ".join(current))
                current = []
                current_words = 0

        for sentence in split_sentences(unit["text"]):
            words = sentence.split()
            if len(words) > max_words:
                flush()
                for start in range(0, len(words), max_words):
                    text_pieces.append(" ".join(words[start:start + max_words]))
            elif current and current_words + len(words) > max_words:
                flush()
                current = words
                current_words = len(words)
            else:
                current.append(sentence)
                current_words += len(words)
        flush()

        for index, text in enumerate(text_pieces):
            bounded.append({
                **unit,
                "text": text,
                "pause_after": unit.get("pause_after", 0.0)
                if index == len(text_pieces) - 1 else 0.0,
            })
    return bounded


def plan_generation(
    grouped: Sequence[Dict[str, Any]],
    max_words: int,
    break_before_turns: Optional[set] = None,
) -> List[List[Dict[str, Any]]]:
    """Plan the synthesis passes for a grouped script.

    Each segment is generated in one model call. A segment has a single delivery style,
    no internal pause, and at most ``max_words`` spoken words. Speaker numbers stay
    global across segments, so a host keeps the same voice in every pass. Segments break
    at sentence boundaries, never mid-sentence.
    """
    max_words = max(1, int(max_words))

    # Expand to sentence granularity so a chunk never cuts a sentence in half.
    expanded: List[Dict[str, Any]] = []
    for unit in grouped:
        sentences = split_sentences(unit["text"])
        for index, sentence in enumerate(sentences):
            expanded.append(
                {
                    **unit,
                    "text": sentence,
                    "pause_after": unit.get("pause_after", 0.0)
                    if index == len(sentences) - 1
                    else 0.0,
                }
            )

    segments: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []

    def flush() -> None:
        nonlocal current
        if current:
            segments.append(current)
            current = []

    for unit in expanded:
        if current and break_before_turns and unit.get("turn_index") in break_before_turns:
            flush()
        unit_words = len(unit["text"].split())
        current_words = sum(len(u["text"].split()) for u in current)
        if current and (
            current[0]["style"] != unit["style"]
            or current[-1].get("pause_after")
            or current_words + unit_words > max_words
        ):
            flush()
        current.append(unit)
        if sum(len(u["text"].split()) for u in current) >= max_words:
            flush()

    flush()
    return segments


def segment_gap_seconds(segment: Sequence[Dict[str, Any]], default_gap: float = 0.4) -> float:
    """Silence to insert after a segment: its explicit pause, else the default gap."""
    if not segment:
        return default_gap
    pause = segment[-1].get("pause_after") or 0.0
    return float(pause) if pause > 0 else default_gap


# ============== Voice resolution ==============

VOICE_FILE_RE = re.compile(
    r"^(?P<lang>[a-z]{2})-(?P<name>.+?)_(?P<gender>man|woman)\.(?P<ext>wav|pt)$",
    re.IGNORECASE,
)


def list_voices(voices_dir: str) -> List[Dict[str, str]]:
    """List the voice presets available on disk.

    Each entry is ``{"id", "path", "language", "gender", "name"}``. The id is the file
    stem, which is what the UI and the API use to select a voice.
    """
    voices: List[Dict[str, str]] = []
    if not voices_dir or not os.path.isdir(voices_dir):
        return voices
    for filename in sorted(os.listdir(voices_dir)):
        match = VOICE_FILE_RE.match(filename)
        if not match:
            continue
        voices.append(
            {
                "id": os.path.splitext(filename)[0],
                "path": os.path.join(voices_dir, filename),
                "language": match.group("lang").lower(),
                "gender": match.group("gender").lower(),
                "name": match.group("name"),
                "ext": match.group("ext").lower(),
            }
        )
    return voices


def _match_voice_file(speaker: str, voices: Sequence[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Find the voice whose file name matches a speaker name, if any."""
    needle = speaker.strip().lower()
    if not needle:
        return None
    for voice in voices:
        if voice["id"].lower() == needle or voice["name"].lower() == needle:
            return voice
    for voice in voices:
        if needle in voice["name"].lower() or needle in voice["id"].lower():
            return voice
    return None


def resolve_voices(
    speakers: Sequence[str],
    voices: Sequence[Dict[str, str]],
    voice_names: Optional[Sequence[str]] = None,
) -> Tuple[Dict[str, str], List[str]]:
    """Map each speaker to a voice file.

    ``voice_names`` is an explicit per-speaker choice, in speaker order, as sent by the
    UI. Otherwise a speaker name is matched against the voice file names. Otherwise
    voices are handed out round robin so two hosts never share a voice while distinct
    voices exist.

    Returns ``(speaker -> voice id, warnings)``.
    """
    warnings: List[str] = []
    assignment: Dict[str, str] = {}
    if not speakers:
        return assignment, warnings

    if voice_names:
        for index, speaker in enumerate(speakers):
            if index >= len(voice_names):
                break
            requested = (voice_names[index] or "").strip()
            if not requested:
                continue
            match = next((v for v in voices if v["id"].lower() == requested.lower()), None)
            if match is None:
                match = _match_voice_file(requested, voices)
            if match is None:
                warnings.append(
                    f"voice '{requested}' for {speaker} was not found, using the default voice"
                )
                continue
            assignment[speaker] = match["id"]

    for speaker in speakers:
        if speaker in assignment:
            continue
        match = _match_voice_file(speaker, voices)
        if match is not None:
            assignment[speaker] = match["id"]

    if not voices:
        warnings.append("no voice files were found in the voices directory")
        return assignment, warnings

    unassigned = [speaker for speaker in speakers if speaker not in assignment]
    if unassigned:
        used = set(assignment.values())
        free = [voice["id"] for voice in voices if voice["id"] not in used]
        if not free:
            warnings.append(
                "not enough distinct voices for every speaker, some hosts share a voice"
            )
            free = [voice["id"] for voice in voices]
        for index, speaker in enumerate(unassigned):
            assignment[speaker] = free[index % len(free)]

    return assignment, warnings


def voice_paths_by_id(
    assignment: Dict[str, str], voices: Sequence[Dict[str, str]]
) -> List[str]:
    """Turn a speaker -> voice id assignment into the ordered path list VibeVoice wants."""
    by_id = {voice["id"]: voice["path"] for voice in voices}
    return [by_id[voice_id] for voice_id in assignment.values()]


# ============== Ending integrity ==============
# A script cut off by the provider's token budget used to be rendered as-is, so
# the episode stopped mid-sentence and the audio ended abruptly. These helpers
# detect that and repair it.

# Phrases that mean the episode already closed itself.
SIGNOFF_MARKERS = (
    "until next time", "see you next time", "that's all", "thats all",
    "thanks for listening", "thank you for listening", "goodbye",
    "stay safe", "see you soon", "tune in next", "subscribe",
)

# Words that cannot end a sentence: the text is dangling after them.
DANGLING_ENDINGS = (
    "and", "or", "but", "of", "in", "on", "at", "to", "for", "with",
    "from", "by", "as", "the", "a", "an", "is", "are", "was", "were",
    "that", "which", "who", "because", "about", "into", "over", "after",
    "before", "between", "through", "however", "meanwhile", "actually",
    "really", "very", "so", "then", "than", "when", "while", "health",
    "economy", "economics", "future", "history", "science", "policy",
)


def has_signoff(text: str) -> bool:
    """True when the text already contains a closing phrase."""
    lowered = (text or "").lower()
    return any(marker in lowered for marker in SIGNOFF_MARKERS)


def looks_truncated(text: str) -> bool:
    """True when the text stops mid-sentence, so the ending is not a real ending."""
    stripped = (text or "").strip()
    if not stripped:
        return True
    if has_signoff(stripped):
        return False
    words = re.split(r"[^A-Za-z']+", stripped.lower())
    words = [w for w in words if w]
    if not words:
        # No Latin characters at all: an Indic script. Judge it by punctuation.
        return not stripped.endswith((".", "!", "?", "।", '"', "”", "’", "'", "…"))
    if words[-1] in DANGLING_ENDINGS:
        return True
    return not stripped.endswith((".", "!", "?", "।", '"', "”", "’", "'", "…"))


def trim_to_last_complete_sentence(text: str) -> str:
    """Drop a trailing fragment so the audio never ends mid-word."""
    stripped = (text or "").strip()
    if not stripped:
        return ""
    ends = [m.end() for m in re.finditer(r"[.!?…।]([\"”'])?(?=\s|$)", stripped)]
    if not ends:
        return ""
    cut = ends[-1]
    tail = stripped[cut:]
    if tail.startswith('"') or tail.startswith("”"):
        cut += 1
    return stripped[:cut].strip()


def ensure_complete_ending(
    script: List[Dict[str, str]],
    lang_name: str = "English",
    llm_chat: Optional[Any] = None,
) -> List[Dict[str, str]]:
    """Make sure the last spoken line ends properly.

    A script cut off by the provider's token budget used to be rendered as-is,
    so the episode stopped mid-sentence. The repair has two independent parts:

    1. If the text stops mid-sentence, drop the dangling fragment.
    2. If the episode has no sign-off, ask the model to write one, so the
       listener hears a finished episode rather than a body of text that
       simply stops.

    Part 2 runs even when part 1 succeeded, because trimming a fragment leaves
    complete but sign-off-free text.

    ``llm_chat`` is injected rather than imported, so this stays testable and
    this module stays free of provider dependencies.
    """
    if not script:
        return script

    last = script[-1]
    content = (last.get("content") or "").strip()
    if not content:
        return script

    if looks_truncated(content):
        trimmed = trim_to_last_complete_sentence(content)
        if trimmed and trimmed != content:
            content = trimmed
            last["content"] = content

    if has_signoff(content):
        return script

    closing = ""
    if llm_chat is not None:
        try:
            closing = llm_chat(
                [
                    {"role": "system", "content": "You write the closing lines of a podcast script."},
                    {
                        "role": "user",
                        "content": (
                            "Write ONLY a short closing passage (2 to 4 sentences) that signs "
                            "this podcast episode off. It must not repeat what was already "
                            "said, must not add a speaker name, and must not mention that the "
                            "text was cut off. Write it in "
                            f"{lang_name} only.\n\n"
                            f"THE EPISODE SO FAR ENDS WITH:\n{content[-1500:]}"
                        ),
                    },
                ],
                max_tokens=400,
                temperature=0.5,
            ).strip()
        except Exception:
            closing = ""

    if closing and looks_truncated(closing):
        closing = trim_to_last_complete_sentence(closing)

    if closing:
        last["content"] = (content + " " + closing).strip()
    else:
        # No model available to close it. Say it plainly rather than ending on a
        # fragment, so the listener hears a complete episode.
        last["content"] = (
            content + " That is all for this episode. Thanks for listening."
        ).strip()

    return script

