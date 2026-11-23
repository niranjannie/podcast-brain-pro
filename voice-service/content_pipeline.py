"""Generate podcast metadata and source-grounded social clip selections.

The model chooses metadata and turn ranges only. ``spoken_text`` is rebuilt from
normalized source turns so a model cannot inject unsourced speech or delivery
markers into text intended for rendering.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from script_pipeline import normalize_turns, strip_directives

__all__ = [
    "generate_content_extras",
    "generate_content_extras_with_retry",
    "with_chapter_timing",
]

_REQUIRED_KEYS = (
    "title",
    "summary",
    "description",
    "takeaways",
    "social_captions",
    "chapters",
    "social_clips",
)
_MAX_TOKENS = 6000
_TEMPERATURE = 0.2


class TruncatedJSONError(ValueError):
    """The response was cut short, so it is worth asking for a bigger budget.

    A malformed response is the model's fault and must not be retried; a
    truncated one is a budget problem and gets one more attempt.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# JSON errors that mean "the response stopped early" rather than "the model
# wrote something invalid".
_TRUNCATION_SIGNATURES = (
    "unterminated string",
    "expecting ',' delimiter",
    "expecting property name",
    "unexpected end of",
)


def _is_truncated_json(text: str, error_message: str) -> bool:
    """True when the JSON stopped early, rather than being malformed.

    An error message alone is not enough: "Expecting value" appears both for a
    cut-off response and for genuinely invalid JSON such as ``{title: oops}``.
    Unbalanced braces are the reliable signal that the response was truncated.
    """
    if any(signature in error_message.lower() for signature in _TRUNCATION_SIGNATURES):
        return True
    # Count braces outside string literals, so a brace inside a quoted value
    # does not skew the balance.
    depth = 0
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
    return depth > 0


def _extract_json_object(raw: Any) -> Dict[str, Any]:
    """Extract one JSON object from a plain, fenced, or prose-wrapped response."""
    if not isinstance(raw, str):
        raise ValueError(
            "LLM content extras response must be a string containing a JSON object."
        )

    text = raw.strip()
    if not text:
        raise ValueError(
            "LLM content extras response was empty; return a complete JSON object."
        )

    try:
        value = json.loads(text)
    except json.JSONDecodeError as whole_error:
        # raw_decode understands braces and escaped quotes inside JSON strings,
        # unlike slicing between the first and last braces in the response.
        decoder = json.JSONDecoder()
        start = text.find("{")
        while start >= 0:
            try:
                value, _ = decoder.raw_decode(text[start:])
            except json.JSONDecodeError:
                pass
            else:
                if isinstance(value, dict):
                    return value
            start = text.find("{", start + 1)

        message = (
            "LLM content extras response did not contain a complete valid JSON "
            f"object ({whole_error.msg} at line {whole_error.lineno}, column "
            f"{whole_error.colno}). Return the JSON object only, without Markdown "
            "fences or surrounding prose."
        )
        if _is_truncated_json(text, whole_error.msg):
            # The response stopped early. That is a token-budget problem, so it
            # earns one retry with a bigger budget.
            raise TruncatedJSONError(message) from whole_error
        raise ValueError(message) from whole_error

    if not isinstance(value, dict):
        raise ValueError(
            "LLM content extras JSON must have an object at the top level, not "
            f"{type(value).__name__}."
        )
    return value


def _required_text(item: Dict[str, Any], key: str, path: str) -> str:
    if key not in item:
        raise ValueError(f"{path} is missing required key '{key}'.")
    value = item[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}.{key} must be a nonempty string.")
    return value.strip()


def _string_list(value: Any, expected: int, path: str) -> List[str]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be a JSON array of {expected} strings.")
    if len(value) != expected:
        raise ValueError(
            f"{path} must contain exactly {expected} strings; got {len(value)}."
        )

    result = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{path}[{index}] must be a nonempty string.")
        result.append(item.strip())
    return result


def _turn_index(value: Any, path: str) -> int:
    # bool is an int subclass, but true/false are not meaningful JSON turn indexes.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path} must be an integer zero-based turn index.")
    return value


def _validate_chapters(
    value: Any, chapter_count: int, spoken_texts: List[str]
) -> List[Dict[str, Any]]:
    turn_count = len(spoken_texts)
    if not isinstance(value, list):
        raise ValueError("chapters must be a JSON array of chapter objects.")
    if len(value) > chapter_count:
        raise ValueError(
            f"chapters must contain at most chapter_count ({chapter_count}) entries; "
            f"got {len(value)}."
        )
    if value and turn_count == 0:
        raise ValueError("chapters cannot reference turns because the script is empty.")
    if chapter_count > 0 and turn_count > 0 and not value:
        raise ValueError(
            "chapters must include a first chapter at turn 0 when chapter_count "
            "is positive and the script is nonempty."
        )

    chapters: List[Dict[str, Any]] = []
    previous_start = -1
    for index, item in enumerate(value):
        item_path = f"chapters[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{item_path} must be a JSON object.")
        title = _required_text(item, "title", item_path)
        if "start_turn" not in item:
            raise ValueError(f"{item_path} is missing required key 'start_turn'.")
        start_turn = _turn_index(item["start_turn"], f"{item_path}.start_turn")
        if start_turn < 0 or start_turn >= turn_count:
            raise ValueError(
                f"{item_path}.start_turn ({start_turn}) is outside the normalized "
                f"script range 0..{turn_count - 1}."
            )
        if not spoken_texts[start_turn]:
            raise ValueError(
                f"{item_path}.start_turn ({start_turn}) has no spoken text after "
                "delivery directives are stripped. Choose a spoken turn."
            )
        if index == 0 and start_turn != 0:
            raise ValueError("The first chapter (chapter 0) must start at turn 0.")
        if start_turn <= previous_start:
            raise ValueError(
                "chapters start_turn values must be strictly increasing and unique; "
                f"{item_path}.start_turn is {start_turn} after {previous_start}."
            )
        chapters.append({"title": title, "start_turn": start_turn})
        previous_start = start_turn
    return chapters


def _plain_spoken_text(content: str) -> str:
    """Remove delivery controls and normalize whitespace without adding content."""
    return " ".join(strip_directives(content).split())


def _validate_social_clips(
    value: Any, spoken_texts: List[str]
) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("social_clips must be a JSON array of clip objects.")

    eligible_turns = sum(bool(text) for text in spoken_texts)
    expected_clips = min(3, eligible_turns)
    if len(value) != expected_clips:
        raise ValueError(
            f"social_clips must contain exactly {expected_clips} clips for this "
            f"script (three when at least three turns have spoken text); got "
            f"{len(value)}."
        )

    clips: List[Dict[str, Any]] = []
    turn_count = len(spoken_texts)
    for index, item in enumerate(value):
        item_path = f"social_clips[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{item_path} must be a JSON object.")

        title = _required_text(item, "title", item_path)
        caption = _required_text(item, "caption", item_path)
        for key in ("start_turn", "end_turn"):
            if key not in item:
                raise ValueError(f"{item_path} is missing required key '{key}'.")
        start_turn = _turn_index(item["start_turn"], f"{item_path}.start_turn")
        end_turn = _turn_index(item["end_turn"], f"{item_path}.end_turn")

        if start_turn < 0 or start_turn >= turn_count:
            raise ValueError(
                f"{item_path}.start_turn ({start_turn}) is outside the normalized "
                f"script range 0..{turn_count - 1}."
            )
        if end_turn < 0 or end_turn >= turn_count:
            raise ValueError(
                f"{item_path}.end_turn ({end_turn}) is outside the normalized "
                f"script range 0..{turn_count - 1}."
            )
        if start_turn > end_turn:
            raise ValueError(
                f"{item_path}.start_turn ({start_turn}) must be less than or equal "
                f"to end_turn ({end_turn}); turn ranges are zero-based and inclusive."
            )

        selected_texts = spoken_texts[start_turn : end_turn + 1]
        for offset, spoken_text in enumerate(selected_texts):
            if not spoken_text:
                empty_turn = start_turn + offset
                raise ValueError(
                    f"{item_path} includes normalized turn {empty_turn}, which has "
                    "no spoken text after delivery directives are stripped. Choose "
                    "a contiguous range containing only nonempty spoken turns."
                )

        clips.append(
            {
                "title": title,
                "start_turn": start_turn,
                "end_turn": end_turn,
                "caption": caption,
                # Never trust a model-supplied spoken_text field. This is verbatim
                # source speech apart from directive removal and whitespace cleanup.
                "spoken_text": "\n".join(selected_texts),
            }
        )
    return clips


def _chapter_limit(value: Optional[int]) -> int:
    # DURATION_CONFIG uses None for episode lengths that do not need chapters.
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("chapter_count must be a nonnegative integer or None.")
    return value


def _build_messages(
    topic: str,
    duration_minutes: int,
    language: str,
    chapter_count: int,
    turns: List[Dict[str, str]],
    spoken_texts: List[str],
) -> List[Dict[str, str]]:
    indexed_turns = [
        {
            "turn": index,
            "speaker": turn["speaker"],
            "spoken_text": spoken_texts[index],
        }
        for index, turn in enumerate(turns)
    ]
    eligible_turns = sum(bool(text) for text in spoken_texts)
    expected_clips = min(3, eligible_turns)

    system_prompt = """You create accurate content extras for an existing podcast script.
Use only claims, examples, quotations, and numbers already present in the supplied
script. Do not invent facts, quotations, statistics, guests, or episode details.
Write every human-readable string in the requested language. Return plain JSON only:
no Markdown fences, explanatory prose, comments, or trailing commas."""

    user_prompt = f"""Create content extras for this podcast.
Topic: {json.dumps(topic, ensure_ascii=False)}
Requested language: {json.dumps(language, ensure_ascii=False)}
Duration in minutes: {json.dumps(duration_minutes)}
Maximum chapter count: {chapter_count}
Required social clip count: {expected_clips}

Normalized script turns (indexes are zero-based; spoken_text already has delivery
directives removed; an empty spoken_text turn cannot be part of a social clip):
{json.dumps(indexed_turns, ensure_ascii=False, indent=2)}

Return one JSON object with exactly these fields:
{{
  "title": "nonempty episode title",
  "summary": "nonempty concise summary grounded in the script",
  "description": "nonempty episode description grounded in the script",
  "takeaways": ["three", "distinct", "takeaways"],
  "social_captions": ["five", "source-grounded", "social", "post", "captions"],
  "chapters": [{{"title": "chapter title", "start_turn": 0}}],
  "social_clips": [
    {{"title": "clip title", "start_turn": 0, "end_turn": 0,
      "caption": "caption for this clip"}}
  ]
}}

Validation rules:
- takeaways has exactly 3 strings and social_captions has exactly 5 strings.
- chapters has at most {chapter_count} entries. If chapters are enabled and the
  script is nonempty, include at least one chapter. Chapter 0 starts at turn 0;
  subsequent start_turn values are strictly increasing, unique, and in range.
  Every chapter must start on a turn whose spoken_text is nonempty.
  If the maximum chapter count is zero or the script is empty, chapters is [].
- social_clips has exactly {expected_clips} entries: three when at least three
  normalized turns contain spoken text, otherwise one per available spoken turn
  up to three. Each start_turn/end_turn pair is an in-range, zero-based,
  inclusive range with start_turn <= end_turn. Every turn in each range must
  contain nonempty spoken text. Select interesting, self-contained, contiguous
  moments rather than adding or paraphrasing speech.
- Do not output spoken_text. It will be reconstructed verbatim from the selected
  normalized source turns, without delivery directives.
"""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def generate_content_extras(
    topic: str,
    script: Any,
    duration_minutes: int,
    language: str,
    chapter_count: Optional[int],
    llm_chat: Callable[..., str],
) -> Dict[str, Any]:
    """Call ``llm_chat`` once and return validated, JSON-ready content extras.

    Result schema::

        {
            "title": str,
            "summary": str,
            "description": str,
            "takeaways": [str, str, str],
            "social_captions": [str, str, str, str, str],
            "chapters": [{"title": str, "start_turn": int}, ...],
            "social_clips": [
                {
                    "title": str,
                    "start_turn": int,
                    "end_turn": int,
                    "caption": str,
                    "spoken_text": str,
                },
                ...
            ],
        }

    Turn indexes refer to ``normalize_turns(script)`` and clip ends are inclusive.
    ``spoken_text`` joins selected source turns with newlines after stripping
    delivery directives. The model's own ``spoken_text`` field, if any, is ignored.

    Raises:
        ValueError: if inputs needed for indexing are invalid, or if the single
            model response is not valid JSON matching the contract. No fallback
            metadata is invented and malformed responses are not retried.
    """
    normalized_turns = normalize_turns(script)
    spoken_texts = [
        _plain_spoken_text(turn["content"]) for turn in normalized_turns
    ]
    chapter_limit = _chapter_limit(chapter_count)
    messages = _build_messages(
        topic,
        duration_minutes,
        language,
        chapter_limit,
        normalized_turns,
        spoken_texts,
    )

    # A truncated JSON response is a budget problem, not a contract problem, so it
    # gets one retry with a larger budget. A malformed response is the model's
    # fault and is not retried: a second provider call would make validation and
    # provider usage nondeterministic for callers and tests.
    raw_response = llm_chat(
        messages, max_tokens=_MAX_TOKENS, temperature=_TEMPERATURE
    )
    try:
        payload = _extract_json_object(raw_response)
    except TruncatedJSONError:
        raw_response = llm_chat(
            messages, max_tokens=_MAX_TOKENS * 2, temperature=_TEMPERATURE
        )
        payload = _extract_json_object(raw_response)

    missing = [key for key in _REQUIRED_KEYS if key not in payload]
    if missing:
        raise ValueError(
            "LLM content extras JSON is missing required keys: "
            + ", ".join(missing)
            + "."
        )

    return {
        "title": _required_text(payload, "title", "content extras"),
        "summary": _required_text(payload, "summary", "content extras"),
        "description": _required_text(payload, "description", "content extras"),
        "takeaways": _string_list(payload["takeaways"], 3, "takeaways"),
        "social_captions": _string_list(
            payload["social_captions"], 5, "social_captions"
        ),
        "chapters": _validate_chapters(
            payload["chapters"], chapter_limit, spoken_texts
        ),
        "social_clips": _validate_social_clips(
            payload["social_clips"], spoken_texts
        ),
    }


def generate_content_extras_with_retry(
    topic: str,
    script: List[Dict[str, Any]],
    duration_minutes: int,
    lang_name: str,
    chapter_count: int,
    llm_chat: Callable[[List[Dict[str, str]], int, float], str],
) -> Dict[str, Any]:
    """Generate content extras, retrying once if the model's output fails validation.

    :func:`generate_content_extras` is deliberately strict and never retries: a
    payload that breaks the contract is a contract violation, not a transient
    error, and retrying inside the validator would make the contract tests
    nondeterministic.

    But the model sometimes places a chapter's ``start_turn`` wrongly, and
    losing the title, summary, takeaways, captions and social clips over one
    number is a bad outcome for a metadata pass that is optional anyway. So the
    retry lives here, one layer out, where a second attempt costs one LLM call
    and does not weaken the validation.
    """
    try:
        return generate_content_extras(
            topic, script, duration_minutes, lang_name, chapter_count, llm_chat
        )
    except ValueError as first_error:
        try:
            return generate_content_extras(
                topic, script, duration_minutes, lang_name, chapter_count, llm_chat
            )
        except ValueError as second_error:
            raise second_error from first_error


def with_chapter_timing(extras: Dict[str, Any], starts: Dict[int, float]) -> Dict[str, Any]:
    """Attach measured start times to every planned chapter, or fail clearly."""
    timed = dict(extras)
    chapters = []
    for chapter in extras.get("chapters", []):
        start_turn = chapter["start_turn"]
        if start_turn not in starts:
            raise ValueError(f"No rendered audio start time for chapter turn {start_turn}")
        chapters.append({**chapter, "startTime": round(float(starts[start_turn]), 3)})
    timed["chapters"] = chapters
    return timed