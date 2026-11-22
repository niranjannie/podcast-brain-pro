"""Tests for the script contract, delivery directives and voice resolution.

Run with: python3 -m unittest test_script_pipeline -v

These cover the regression that broke multi speaker episodes: the generator emits
``speaker`` while the TTS layer used to read ``role``, so every host fell back to
"Speaker 1" and the voice mapping was wrong.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from script_pipeline import (  # noqa: E402
    build_units,
    chunk_units_for_engine,
    ensure_complete_ending,
    group_units,
    has_signoff,
    list_voices,
    looks_truncated,
    normalize_turns,
    plan_generation,
    resolve_voices,
    segment_gap_seconds,
    speaker_order,
    split_monologue_turns,
    split_units,
    strip_directives,
    trim_to_last_complete_sentence,
    units_to_script_lines,
)


class NormalizeTurnsTest(unittest.TestCase):
    def test_accepts_both_key_spellings(self):
        turns = normalize_turns(
            [
                {"speaker": "Host", "content": "hello"},
                {"role": "Guest", "content": "hi there"},
                {"role": "Guest", "text": "text key works too"},
            ]
        )
        self.assertEqual(
            turns,
            [
                {"speaker": "Host", "content": "hello"},
                {"speaker": "Guest", "content": "hi there"},
                {"speaker": "Guest", "content": "text key works too"},
            ],
        )

    def test_skips_empty_and_malformed_turns(self):
        turns = normalize_turns(
            [
                {"speaker": "Host", "content": "   "},
                "not a dict",
                {"speaker": "Host", "content": "kept"},
                None,
            ]
        )
        self.assertEqual(turns, [{"speaker": "Host", "content": "kept"}])

    def test_non_list_returns_empty(self):
        self.assertEqual(normalize_turns({"speaker": "Host"}), [])

    def test_speaker_order_is_first_appearance(self):
        turns = normalize_turns(
            [
                {"speaker": "Guest", "content": "one"},
                {"speaker": "Host", "content": "two"},
                {"speaker": "Guest", "content": "three"},
            ]
        )
        self.assertEqual(speaker_order(turns), ["Guest", "Host"])


class DirectiveTest(unittest.TestCase):
    def test_pause_belongs_to_the_text_before_it(self):
        units = split_units("Hello there. [[pause:0.8]] Now that was big.")
        self.assertEqual(len(units), 2)
        self.assertEqual(units[0]["text"], "Hello there.")
        self.assertEqual(units[0]["pause_after"], 0.8)
        self.assertEqual(units[1]["pause_after"], 0.0)

    def test_style_switches_for_the_rest_of_the_turn(self):
        units = split_units("Start. [[style:calm]] Softer now.")
        self.assertEqual(units[0]["style"], "neutral")
        self.assertEqual(units[1]["style"], "calm")

    def test_unknown_style_falls_back_to_neutral(self):
        units = split_units("Start. [[style:shouting]] Text.")
        self.assertEqual(units[1]["style"], "neutral")

    def test_pause_without_value_uses_half_a_second(self):
        units = split_units("Hello [[pause]] World")
        self.assertEqual(units[0]["pause_after"], 0.5)

    def test_pause_is_capped(self):
        units = split_units("Hello [[pause:600]] World")
        self.assertEqual(units[0]["pause_after"], 10.0)

    def test_directives_are_stripped_from_the_text(self):
        self.assertEqual(strip_directives("Hi [[pause:1.0]] there"), "Hi  there".strip())

    def test_text_without_directives_is_one_unit(self):
        units = split_units("Just words.")
        self.assertEqual(units, [{"text": "Just words.", "style": "neutral", "pause_after": 0.0}])


class UnitsAndChunkingTest(unittest.TestCase):
    def setUp(self):
        self.turns = normalize_turns(
            [
                {"speaker": "Host", "content": "Welcome. [[pause:0.5]] Today we talk AI."},
                {"speaker": "Guest", "content": "Thanks for having me."},
            ]
        )

    def test_speaker_numbers_are_global_and_stable(self):
        units = build_units(self.turns)
        self.assertEqual([u["speaker_id"] for u in units], [1, 1, 2])

    def test_grouping_keeps_a_pause_boundary(self):
        grouped = group_units(build_units(self.turns))
        self.assertEqual(len(grouped), 3)
        self.assertEqual(grouped[0]["text"], "Welcome.")
        self.assertEqual(grouped[0]["pause_after"], 0.5)

    def test_plan_keeps_speaker_ids_across_segments(self):
        long_turns = normalize_turns(
            [
                {"speaker": "Host", "content": "word " * 40},
                {"speaker": "Guest", "content": "word " * 40},
            ]
        )
        segments = plan_generation(group_units(build_units(long_turns)), max_words=50)
        self.assertGreater(len(segments), 1)
        self.assertEqual(segments[0][0]["speaker_id"], 1)
        self.assertEqual(segments[1][0]["speaker_id"], 2)

    def test_plan_never_splits_a_sentence(self):
        turns = normalize_turns([{"speaker": "Host", "content": "One two three. Four five six."}])
        segments = plan_generation(group_units(build_units(turns)), max_words=3)
        for segment in segments:
            for unit in segment:
                self.assertIn(unit["text"], ("One two three.", "Four five six."))

    def test_monologue_is_split_without_changing_words(self):
        text = "One two three. Four five six. Seven eight nine. Ten eleven twelve."
        turns = split_monologue_turns(text, target_words=7)
        self.assertEqual([len(turn["content"].split()) for turn in turns], [6, 6])
        self.assertEqual(" ".join(turn["content"] for turn in turns), text)

    def test_small_engine_chunks_long_sentences_without_losing_pause(self):
        turns = normalize_turns([
            {"speaker": "Host", "content": "one two three four five six seven eight nine ten [[pause:0.7]]"}
        ])
        chunks = chunk_units_for_engine(build_units(turns), max_words=4)
        self.assertEqual([len(chunk["text"].split()) for chunk in chunks], [4, 4, 2])
        self.assertEqual([chunk["pause_after"] for chunk in chunks], [0.0, 0.0, 0.7])
        self.assertTrue(all(chunk["turn_index"] == 0 for chunk in chunks))

    def test_chapter_turn_forces_a_new_segment(self):
        turns = normalize_turns([
            {"speaker": "Host", "content": "Opening turn."},
            {"speaker": "Guest", "content": "Guest answer."},
        ])
        grouped = group_units(build_units(turns), break_before_turns={1})
        segments = plan_generation(grouped, max_words=50, break_before_turns={1})
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[1][0]["turn_index"], 1)

    def test_script_lines_use_the_global_speaker_number(self):
        grouped = group_units(build_units(self.turns))
        script = units_to_script_lines(grouped)
        self.assertIn("Speaker 1: Welcome.", script)
        self.assertIn("Speaker 2: Thanks for having me.", script)

    def test_segment_gap_prefers_the_explicit_pause(self):
        self.assertEqual(segment_gap_seconds([{"pause_after": 1.25}]), 1.25)
        self.assertEqual(segment_gap_seconds([{"pause_after": 0.0}]), 0.4)


class VoiceResolutionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        for name in ("en-Carter_man.wav", "en-Alice_woman.wav", "en-Frank_man.wav"):
            open(os.path.join(self.tmp.name, name), "wb").close()
        self.voices = list_voices(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_lists_voice_files(self):
        self.assertEqual(
            [voice["id"] for voice in self.voices],
            ["en-Alice_woman", "en-Carter_man", "en-Frank_man"],
        )

    def test_speakers_get_distinct_voices_by_default(self):
        assignment, warnings = resolve_voices(["Host", "Guest"], self.voices)
        self.assertEqual(warnings, [])
        self.assertNotEqual(assignment["Host"], assignment["Guest"])

    def test_speaker_name_matching_wins(self):
        assignment, _ = resolve_voices(["Carter", "Frank"], self.voices)
        self.assertEqual(assignment["Carter"], "en-Carter_man")
        self.assertEqual(assignment["Frank"], "en-Frank_man")

    def test_explicit_voice_names_win(self):
        assignment, _ = resolve_voices(
            ["Host", "Guest"], self.voices, ["en-Frank_man", "en-Alice_woman"]
        )
        self.assertEqual(assignment["Host"], "en-Frank_man")
        self.assertEqual(assignment["Guest"], "en-Alice_woman")

    def test_unknown_voice_name_falls_back_with_a_warning(self):
        assignment, warnings = resolve_voices(["Host"], self.voices, ["not-a-voice"])
        self.assertTrue(warnings)
        self.assertIn("Host", assignment)

    def test_no_voice_files_reports_a_warning(self):
        assignment, warnings = resolve_voices(["Host"], [])
        self.assertEqual(assignment, {})
        self.assertTrue(warnings)


class TestEndingIntegrity(unittest.TestCase):
    """The episode must never end on a fragment.

    A script cut off by the provider's token budget used to be rendered as-is,
    so every episode ended mid-sentence and the audio stopped abruptly.
    """

    # The real text that produced the defect, cut off by the token budget.
    CUT_OFF = (
        "Good morning, listeners. Today we're untangling a habit that most of us "
        "just roll with twice a year. So, Europe's daylight-saving time started as "
        "a wartime fuel-saving trick, evolved through energy crises, and now sits "
        "at the crossroads of economics, health"
    )

    def test_cut_off_text_is_detected(self):
        self.assertTrue(looks_truncated(self.CUT_OFF))

    def test_complete_text_is_not_flagged(self):
        self.assertFalse(
            looks_truncated("That is all for today. Thanks for listening.")
        )

    def test_signoff_is_not_flagged(self):
        self.assertFalse(looks_truncated("We will see you next time. Until next time!"))

    def test_empty_text_is_flagged(self):
        self.assertTrue(looks_truncated(""))
        self.assertTrue(looks_truncated("   "))

    def test_indic_text_is_judged_by_punctuation(self):
        # No Latin letters, so the trailing word cannot be checked.
        self.assertFalse(looks_truncated("এটি একটি সম্পূর্ণ বাক্য।"))
        self.assertTrue(looks_truncated("এবং এটি অসম্পূর্ণ"))

    def test_trim_drops_the_dangling_fragment(self):
        trimmed = trim_to_last_complete_sentence("One. Two. And a dangling frag")
        self.assertEqual(trimmed, "One. Two.")

    def test_trim_keeps_a_closing_quote(self):
        trimmed = trim_to_last_complete_sentence('He said "stop." And then')
        self.assertTrue(trimmed.endswith('"'))

    def test_ending_is_repaired_with_a_generated_closing(self):
        calls = []

        def fake_llm(messages, max_tokens=600, temperature=0.7):
            calls.append(messages)
            return "It remains a live debate. Thanks for listening."

        script = [{"speaker": "Host", "content": self.CUT_OFF}]
        fixed = ensure_complete_ending(script, "English", fake_llm)

        self.assertEqual(len(calls), 1)
        self.assertFalse(looks_truncated(fixed[-1]["content"]))
        self.assertTrue(has_signoff(fixed[-1]["content"]))

    def test_ending_is_repaired_when_the_model_call_fails(self):
        def broken_llm(messages, max_tokens=600, temperature=0.7):
            raise RuntimeError("provider down")

        script = [{"speaker": "Host", "content": self.CUT_OFF}]
        fixed = ensure_complete_ending(script, "English", broken_llm)

        self.assertFalse(looks_truncated(fixed[-1]["content"]))
        self.assertTrue(has_signoff(fixed[-1]["content"]))

    def test_ending_is_repaired_without_any_model(self):
        script = [{"speaker": "Host", "content": self.CUT_OFF}]
        fixed = ensure_complete_ending(script, "English", None)
        self.assertFalse(looks_truncated(fixed[-1]["content"]))
        self.assertTrue(has_signoff(fixed[-1]["content"]))

    def test_an_existing_signoff_is_left_alone(self):
        calls = []

        def fake_llm(messages, max_tokens=600, temperature=0.7):
            calls.append(messages)
            return "Something else."

        content = "That is all for today. Thanks for listening."
        script = [{"speaker": "Host", "content": content}]
        fixed = ensure_complete_ending(script, "English", fake_llm)

        self.assertEqual(calls, [])
        self.assertEqual(fixed[-1]["content"], content)

    def test_a_truncated_generated_closing_is_trimmed(self):
        def fake_llm(messages, max_tokens=600, temperature=0.7):
            return "A closing that got cut off mid"

        script = [{"speaker": "Host", "content": self.CUT_OFF}]
        fixed = ensure_complete_ending(script, "English", fake_llm)
        self.assertFalse(looks_truncated(fixed[-1]["content"]))

    def test_multi_turn_script_only_repairs_the_last_turn(self):
        script = [
            {"speaker": "Host", "content": "Welcome to the show."},
            {"speaker": "Guest", "content": self.CUT_OFF},
        ]
        fixed = ensure_complete_ending(script, "English", None)
        self.assertEqual(fixed[0]["content"], "Welcome to the show.")
        self.assertFalse(looks_truncated(fixed[-1]["content"]))

    def test_empty_script_is_handled(self):
        self.assertEqual(ensure_complete_ending([], "English", None), [])


if __name__ == "__main__":
    unittest.main()
