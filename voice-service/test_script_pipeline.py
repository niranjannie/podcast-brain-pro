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
    parse_conversation_script,
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


class TestDisclosure(unittest.TestCase):
    """Every episode must say it is synthetic.

    EU AI Act Article 50 requires an audible disclosure on synthetic audio from
    2 August 2026, and a machine-readable marking alongside it.
    """

    def test_every_language_has_a_disclosure_line(self):
        from script_pipeline import DISCLOSURE_LINES
        for language in ["en", "hi-IN", "ta-IN", "te-IN", "kn-IN", "bn-IN",
                         "mr-IN", "gu-IN", "ml-IN", "pa-IN", "od-IN"]:
            self.assertIn(language, DISCLOSURE_LINES)
            self.assertTrue(DISCLOSURE_LINES[language].strip())

    def test_disclosure_is_spoken_by_the_first_host(self):
        from script_pipeline import add_disclosure
        script = [
            {"speaker": "Host", "content": "Welcome to the show."},
            {"speaker": "Guest", "content": "Thanks for having me."},
        ]
        fixed = add_disclosure(script, "en")
        self.assertTrue(fixed[0]["content"].startswith(
            "This episode was generated by artificial intelligence"))
        self.assertIn("Welcome to the show.", fixed[0]["content"])
        # The other turns are untouched.
        self.assertEqual(fixed[1]["content"], "Thanks for having me.")

    def test_disclosure_uses_the_episode_language(self):
        from script_pipeline import add_disclosure
        script = [{"speaker": "Host", "content": "नमस्ते"}]
        fixed = add_disclosure(script, "hi-IN")
        self.assertIn("कृत्रिम बुद्धिमत्ता", fixed[0]["content"])

    def test_disclosure_is_not_added_twice(self):
        from script_pipeline import add_disclosure
        script = [{"speaker": "Host", "content": "Welcome to the show."}]
        once = add_disclosure(script, "en")
        twice = add_disclosure(once, "en")
        self.assertEqual(once[0]["content"], twice[0]["content"])
        self.assertEqual(twice[0]["content"].count("generated by artificial intelligence"), 1)

    def test_disclosure_can_be_disabled(self):
        from script_pipeline import add_disclosure
        script = [{"speaker": "Host", "content": "Welcome to the show."}]
        fixed = add_disclosure(script, "en", enabled=False)
        self.assertEqual(fixed[0]["content"], "Welcome to the show.")

    def test_empty_script_is_handled(self):
        from script_pipeline import add_disclosure
        self.assertEqual(add_disclosure([], "en"), [])

    def test_disclosure_is_never_repeated_inside_a_turn(self):
        from script_pipeline import add_disclosure
        script = [{"speaker": "Host", "content": "Welcome to the show."}]
        fixed = add_disclosure(script, "en")
        self.assertEqual(fixed[0]["content"].count("artificial intelligence"), 1)


class ConversationParsingTest(unittest.TestCase):
    """Raw model output must become ordered turns with the right voices.

    The recurring failure: a model writing an Indic script labels its speakers
    with the role word in the target language ("সঞ্চালক:" for "Host"). The parser
    used to drop those lines entirely, so a two-host conversation collapsed into
    one voice and the episode lost its content.
    """

    def test_canonical_labels_are_parsed(self):
        script = parse_conversation_script(
            "Host: Welcome to the show.\nGuest: Thanks for having me.\nHost: Let's begin.",
            ["Host", "Guest"],
        )
        self.assertEqual([t["speaker"] for t in script], ["Host", "Guest", "Host"])
        self.assertEqual(script[0]["content"], "Welcome to the show.")

    def test_localised_labels_map_to_the_cast_in_order(self):
        raw = (
            "সঞ্চালক: আজ আমরা শহরে গাছ নিয়ে আলোচনা করব।\n"
            "অতিথি: ধন্যবাদ, খুব ভালো প্রশ্ন।\n"
            "সঞ্চালক: গাছ ছায়া দেয়।"
        )
        script = parse_conversation_script(raw, ["Host", "Guest"])
        self.assertEqual([t["speaker"] for t in script], ["Host", "Guest", "Host"])
        # The localised label must not be spoken.
        self.assertNotIn("সঞ্চালক", script[0]["content"])
        self.assertNotIn("অতিথি", script[1]["content"])
        # And the words themselves must survive.
        self.assertIn("ছায়া", script[2]["content"])

    def test_localised_labels_map_in_every_script(self):
        cases = {
            "kannada": "ಸಂಚಾಲಕ: ಇಂದು ಮರಗಳ ಬಗ್ಗೆ.\nಅತಿಥಿ: ಧನ್ಯವಾದ.",
            "tamil": "தலைவர்: இன்று மரங்கள் பற்றி.\nவிருந்தினர்: நன்றி.",
            "telugu": "దర్శకుడు: ఈరోజు చెట్లు.\nఅతిథి: ధన్యవాదం.",
            "hindi": "प्रस्तुतकर्ता: आज पेड़ों के बारे में।\nअतिथि: धन्यवाद।",
            "marathi": "सूत्रसंचालक: आज झाडांवर.\nअतिथी: धन्यवाद.",
        }
        for language, raw in cases.items():
            with self.subTest(language=language):
                script = parse_conversation_script(raw, ["Host", "Guest"])
                self.assertEqual(
                    [t["speaker"] for t in script], ["Host", "Guest"], language
                )

    def test_a_canonical_label_advances_the_pointer(self):
        # "Host:" first, then a localised label: the localised one must be the
        # guest, not a second host.
        raw = "Host: Welcome.\nঅতিথি: ধন্যবাদ।\nHost: Let's begin."
        script = parse_conversation_script(raw, ["Host", "Guest"])
        self.assertEqual([t["speaker"] for t in script], ["Host", "Guest", "Host"])

    def test_an_unknown_ascii_label_keeps_its_words(self):
        raw = "Host: Welcome.\nAlice: a line from someone else.\nHost: Back to you."
        script = parse_conversation_script(raw, ["Host", "Guest"])
        spoken = " ".join(t["content"] for t in script)
        # The words must survive, and the unfamiliar label must not be spoken.
        self.assertIn("a line from someone else.", spoken)
        self.assertNotIn("Alice", spoken)

    def test_a_label_differing_only_in_case_is_the_same_speaker(self):
        raw = "HOST: Welcome.\nGUEST: Thanks.\nHost: Begin."
        script = parse_conversation_script(raw, ["Host", "Guest"])
        self.assertEqual([t["speaker"] for t in script], ["Host", "Guest", "Host"])

    def test_a_canonical_label_keeps_its_own_voice_even_out_of_order(self):
        raw = "Guest: Hello.\nHost: Hi.\nGuest: Bye."
        script = parse_conversation_script(raw, ["Host", "Guest"])
        self.assertEqual([t["speaker"] for t in script], ["Guest", "Host", "Guest"])

    def test_a_third_label_reuses_the_last_cast_member(self):
        raw = "Host: One.\nGuest: Two.\nHost: Three.\nNarrator: Four."
        script = parse_conversation_script(raw, ["Host", "Guest"])
        self.assertEqual(script[-1]["speaker"], "Guest")
        self.assertIn("Four.", script[-1]["content"])

    def test_plain_paragraphs_join_the_current_speaker(self):
        raw = "Host: First line.\nSecond line of the same thought.\nGuest: Mine."
        script = parse_conversation_script(raw, ["Host", "Guest"])
        self.assertEqual(len(script), 2)
        self.assertIn("Second line", script[0]["content"])


if __name__ == "__main__":
    unittest.main()
