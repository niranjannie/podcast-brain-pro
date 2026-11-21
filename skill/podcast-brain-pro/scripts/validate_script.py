#!/usr/bin/env python3
"""Validate a Podcast Brain Pro episode JSON against the script contract.

Usage:
    python3 validate_script.py episode.json
    python3 validate_script.py episode.json --json

Exit codes:
    0  no errors (warnings may be present)
    1  at least one error
    2  the file could not be read or parsed
"""

from __future__ import annotations

import argparse
import json
import re
import sys

FORMATS = ("monologue", "interview", "panel")
LANGUAGES = (
    "en", "hi-IN", "ta-IN", "te-IN", "kn-IN", "bn-IN",
    "mr-IN", "gu-IN", "ml-IN", "pa-IN", "od-IN",
)
WORD_BUDGET = {2: 300, 5: 750, 10: 1500, 15: 2250, 30: 4500}
DEFAULT_SPEAKERS = {
    "monologue": ["Host"],
    "interview": ["Host", "Guest"],
    "panel": ["Host", "Guest A", "Guest B"],
}

# Spoken text must not carry these: they break TTS or were never meant to be spoken.
STAGE_PATTERN = re.compile(
    r"(?m)^\s*(?:[-*+]\s|#{1,6}\s|\[[^\]]*\]|\([^)]*\)|\*{1,2}[^*]+\*{1,2})"
)
BULLET_INLINE = re.compile(r"(?m)^\s*[-*]\s+")

# Delivery markers are part of the contract and must survive validation.
DIRECTIVE_PATTERN = re.compile(r"\[\[\s*(pause|style)\b[^\]]*\]\]", re.IGNORECASE)


def validate(data: object) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return ["top level of the episode file must be a JSON object"], warnings

    topic = data.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        errors.append("missing or empty 'topic'")

    fmt = data.get("format", "monologue")
    if fmt not in FORMATS:
        errors.append(f"format {fmt!r} is not one of {list(FORMATS)}")
        fmt = "monologue"

    duration = data.get("duration_minutes", 2)
    if duration not in WORD_BUDGET:
        errors.append(
            f"duration_minutes {duration!r} is not one of {sorted(WORD_BUDGET)}"
        )
        duration = 2

    language = data.get("language", "en")
    if language not in LANGUAGES:
        errors.append(f"language {language!r} is not one of {list(LANGUAGES)}")

    script = data.get("script")
    if not isinstance(script, list) or not script:
        errors.append("'script' must be a non-empty list of turns")
        return errors, warnings

    expected_speakers = list(data.get("speakers") or DEFAULT_SPEAKERS[fmt])
    seen: list[str] = []
    total_words = 0

    for index, turn in enumerate(script):
        where = f"script[{index}]"
        if not isinstance(turn, dict):
            errors.append(f"{where} is not an object")
            continue

        speaker = turn.get("speaker", turn.get("role"))
        content = turn.get("content")

        if not isinstance(speaker, str) or not speaker.strip():
            errors.append(f"{where} has no speaker name")
        elif speaker not in seen:
            seen.append(speaker)

        if not isinstance(content, str) or not content.strip():
            errors.append(f"{where} has empty content")
            continue

        total_words += len(content.split())

        spoken = DIRECTIVE_PATTERN.sub(" ", content)
        if STAGE_PATTERN.search(spoken) or BULLET_INLINE.search(spoken):
            errors.append(
                f"{where} contains markdown, bullets or a stage direction - "
                "remove it, TTS reads it out loud"
            )

        if re.search(r"\bTODO\b|\bTBD\b|\[insert|\[placeholder", content, re.IGNORECASE):
            errors.append(f"{where} still contains a placeholder")

    distinct = len(seen)
    wanted = len(expected_speakers)
    if fmt == "monologue" and distinct > 1:
        errors.append(
            f"format is 'monologue' but {distinct} speakers appear - "
            "use 'interview' or 'panel' instead"
        )
    elif distinct != wanted:
        warnings.append(
            f"{distinct} speaker(s) present but format '{fmt}' expects {wanted} "
            f"({', '.join(expected_speakers)})"
        )

    unknown = [s for s in seen if s not in expected_speakers]
    if unknown:
        warnings.append(
            "speaker name(s) not in the expected set "
            f"{expected_speakers}: {', '.join(unknown)}"
        )

    budget = WORD_BUDGET[duration]
    if total_words == 0:
        errors.append("script contains no words")
    elif total_words < budget * 0.5:
        errors.append(
            f"{total_words} words is under half the {duration}-minute budget "
            f"({budget})"
        )
    elif total_words < budget * 0.75:
        warnings.append(
            f"{total_words} words is below the {duration}-minute budget ({budget})"
        )
    elif total_words > budget * 1.25:
        warnings.append(
            f"{total_words} words is over the {duration}-minute budget ({budget})"
        )

    if language != "en" and not any(
        re.search(r"[A-Za-z]{4,}", turn.get("content", ""))
        for turn in script
        if isinstance(turn, dict)
    ):
        warnings.append(
            f"language is {language} but no long Latin-script words appear in the script"
        )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", help="path to the episode JSON file")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    try:
        with open(args.episode, encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        print(f"cannot read {args.episode}: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"{args.episode} is not valid JSON: {exc}", file=sys.stderr)
        return 2

    errors, warnings = validate(data)

    if args.json:
        print(json.dumps({"errors": errors, "warnings": warnings}, indent=2))
    else:
        for warning in warnings:
            print(f"warning: {warning}")
        for error in errors:
            print(f"error: {error}")
        if not errors:
            print(f"ok: {len(errors)} errors, {len(warnings)} warnings")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
