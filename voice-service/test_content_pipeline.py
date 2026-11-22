"""Deterministic tests for content extras generation and validation.

Run with: python3 -m unittest test_content_pipeline -v
The recording callback is the only model boundary used here; tests make no
network requests or real model calls.
"""

import copy
import json
import os
import sys
import unittest
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from content_pipeline import generate_content_extras, with_chapter_timing  # noqa: E402


SCRIPT = [
    {"speaker": "Host", "content": "Welcome to the source-grounded discussion."},
    {"role": "Guest", "text": "The first example is already in this script."},
    {"speaker": "Host", "content": "The host asks a question."},
    {"role": "Guest", "text": "The guest answers with the supplied example."},
    {"speaker": "Host", "content": "The discussion considers a limitation."},
    {"speaker": "Host", "content": "The host closes with a recap."},
]


def make_payload(chapter_starts=(0, 2, 4), clip_ranges=((0, 1), (2, 3), (4, 5))):
    return {
        "title": "A source-grounded discussion",
        "summary": "The hosts discuss the examples already present in the script.",
        "description": "An episode description based only on the supplied turns.",
        "takeaways": ["First takeaway", "Second takeaway", "Third takeaway"],
        "social_captions": [
            "First caption",
            "Second caption",
            "Third caption",
            "Fourth caption",
            "Fifth caption",
        ],
        "chapters": [
            {"title": f"Chapter {index + 1}", "start_turn": start}
            for index, start in enumerate(chapter_starts)
        ],
        "social_clips": [
            {
                "title": f"Clip {index + 1}",
                "start_turn": start,
                "end_turn": end,
                "caption": f"Caption for clip {index + 1}",
            }
            for index, (start, end) in enumerate(clip_ranges)
        ],
    }


class RecordingLLM:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, messages, max_tokens=600, temperature=0.7):
        self.calls.append(
            {
                "messages": copy.deepcopy(messages),
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        return self.response

    @property
    def call_count(self):
        return len(self.calls)


class ContentExtrasTest(unittest.TestCase):
    def generate(
        self,
        payload=None,
        *,
        raw_response=None,
        script=None,
        chapter_count: Optional[int] = 3,
    ):
        if raw_response is None:
            raw_response = json.dumps(payload if payload is not None else make_payload())
        llm = RecordingLLM(raw_response)
        result = generate_content_extras(
            "A grounded topic",
            SCRIPT if script is None else script,
            10,
            "English",
            chapter_count,
            llm,
        )
        return result, llm

    def assert_invalid(
        self,
        payload,
        pattern,
        *,
        script=None,
        chapter_count: Optional[int] = 3,
    ):
        llm = RecordingLLM(json.dumps(payload))
        with self.assertRaisesRegex(ValueError, pattern):
            generate_content_extras(
                "A grounded topic",
                SCRIPT if script is None else script,
                10,
                "English",
                chapter_count,
                llm,
            )
        self.assertEqual(llm.call_count, 1, "invalid output must not trigger a retry")

    def test_valid_output_has_canonical_json_ready_schema(self):
        payload = make_payload()
        payload["unexpected"] = "ignored"
        payload["social_clips"][0]["spoken_text"] = (
            "**Invented speech** [[pause:9]]"
        )

        result, llm = self.generate(payload)

        self.assertEqual(
            set(result),
            {
                "title",
                "summary",
                "description",
                "takeaways",
                "social_captions",
                "chapters",
                "social_clips",
            },
        )
        self.assertEqual(len(result["takeaways"]), 3)
        self.assertEqual(len(result["social_captions"]), 5)
        self.assertEqual(len(result["chapters"]), 3)
        self.assertEqual(len(result["social_clips"]), 3)
        self.assertEqual(
            set(result["social_clips"][0]),
            {"title", "start_turn", "end_turn", "caption", "spoken_text"},
        )
        self.assertEqual(
            result["social_clips"][0]["spoken_text"],
            "Welcome to the source-grounded discussion.\n"
            "The first example is already in this script.",
        )
        self.assertNotIn("Invented speech", json.dumps(result))
        self.assertNotIn("[[pause", json.dumps(result))
        # This must not raise: callers can pass the result directly to json.dumps.
        json.dumps(result, ensure_ascii=False)

        self.assertEqual(llm.call_count, 1)
        call = llm.calls[0]
        self.assertIsInstance(call["max_tokens"], int)
        self.assertGreater(call["max_tokens"], 0)
        self.assertEqual(call["temperature"], 0.2)
        self.assertEqual(
            [message["role"] for message in call["messages"]], ["system", "user"]
        )
        system_prompt = call["messages"][0]["content"]
        user_prompt = call["messages"][1]["content"]
        self.assertIn("Do not invent facts, quotations, statistics", system_prompt)
        self.assertIn('Requested language: "English"', user_prompt)
        self.assertIn('Topic: "A grounded topic"', user_prompt)
        self.assertIn("Duration in minutes: 10", user_prompt)
        self.assertIn("Maximum chapter count: 3", user_prompt)
        self.assertIn("Required social clip count: 3", user_prompt)
        self.assertIn('"turn": 0', user_prompt)
        self.assertIn("zero-based", user_prompt)
        self.assertIn("inclusive", user_prompt)

    def test_fenced_json_with_surrounding_prose_is_extracted(self):
        response = (
            "Here is the requested metadata.\n```json\n"
            + json.dumps(make_payload())
            + "\n```\nThe object above follows the schema."
        )
        result, llm = self.generate(raw_response=response)
        self.assertEqual(result["title"], "A source-grounded discussion")
        self.assertEqual(llm.call_count, 1)

    def test_malformed_json_raises_actionable_error_without_retry(self):
        cases = [
            ("```json\n{title: not valid JSON}\n```", "valid JSON object"),
            ("", "empty"),
            ("[]", "top level"),
            (None, "must be a string"),
        ]
        for response, pattern in cases:
            with self.subTest(response=response):
                llm = RecordingLLM(response)
                with self.assertRaisesRegex(ValueError, pattern):
                    generate_content_extras(
                        "A grounded topic", SCRIPT, 10, "English", 3, llm
                    )
                self.assertEqual(llm.call_count, 1)

    def test_required_fields_and_exact_text_list_counts_are_validated(self):
        missing = make_payload()
        del missing["summary"]
        self.assert_invalid(missing, "missing required keys: summary")

        short_takeaways = make_payload()
        short_takeaways["takeaways"] = short_takeaways["takeaways"][:2]
        self.assert_invalid(short_takeaways, "takeaways.*exactly 3")

        long_captions = make_payload()
        long_captions["social_captions"].append("Sixth caption")
        self.assert_invalid(long_captions, "social_captions.*exactly 5")

        empty_takeaway = make_payload()
        empty_takeaway["takeaways"][1] = "   "
        self.assert_invalid(empty_takeaway, r"takeaways\[1\].*nonempty string")

        invalid_title = make_payload()
        invalid_title["title"] = ["not", "a", "string"]
        self.assert_invalid(invalid_title, "title.*nonempty string")

    def test_chapter_range_order_uniqueness_and_count_are_validated(self):
        cases = []

        payload = make_payload()
        payload["chapters"][0]["start_turn"] = 1
        cases.append(("first chapter", payload, "first chapter.*turn 0"))

        payload = make_payload()
        payload["chapters"][2]["start_turn"] = 2
        cases.append(("duplicate", payload, "strictly increasing and unique"))

        payload = make_payload()
        payload["chapters"][2]["start_turn"] = 1
        cases.append(("decreasing", payload, "strictly increasing and unique"))

        payload = make_payload()
        payload["chapters"][2]["start_turn"] = len(SCRIPT)
        cases.append(("out of range", payload, "outside the normalized script range"))

        payload = make_payload()
        payload["chapters"][0]["start_turn"] = -1
        cases.append(("negative", payload, "outside the normalized script range"))

        payload = make_payload()
        payload["chapters"].append({"title": "Too many", "start_turn": 5})
        cases.append(("too many", payload, "at most chapter_count.*3"))

        payload = make_payload()
        payload["chapters"][1]["start_turn"] = True
        cases.append(("boolean index", payload, "integer zero-based turn index"))

        payload = make_payload(chapter_starts=())
        cases.append(("missing chapters", payload, "first chapter at turn 0"))

        payload = make_payload()
        payload["chapters"] = {}
        cases.append(("not a list", payload, "chapters must be a JSON array"))

        for name, broken, pattern in cases:
            with self.subTest(name=name):
                self.assert_invalid(broken, pattern)

    def test_social_clip_range_and_count_are_validated(self):
        cases = []

        payload = make_payload()
        payload["social_clips"] = payload["social_clips"][:2]
        cases.append(("too few", payload, "social_clips.*exactly 3"))

        payload = make_payload()
        payload["social_clips"].append(copy.deepcopy(payload["social_clips"][0]))
        cases.append(("too many", payload, "social_clips.*exactly 3"))

        payload = make_payload()
        payload["social_clips"][0]["start_turn"] = 1
        payload["social_clips"][0]["end_turn"] = 0
        cases.append(("reversed range", payload, "start_turn.*less than or equal"))

        payload = make_payload()
        payload["social_clips"][0]["start_turn"] = -1
        cases.append(("negative start", payload, "start_turn.*outside"))

        payload = make_payload()
        payload["social_clips"][2]["end_turn"] = len(SCRIPT)
        cases.append(("end out of range", payload, "end_turn.*outside"))

        payload = make_payload()
        payload["social_clips"][0]["end_turn"] = "1"
        cases.append(("string index", payload, "end_turn.*integer"))

        payload = make_payload()
        payload["social_clips"] = {}
        cases.append(("not a list", payload, "social_clips must be a JSON array"))

        payload = make_payload()
        payload["social_clips"][0]["caption"] = ""
        cases.append(("empty caption", payload, "caption.*nonempty string"))

        for name, broken, pattern in cases:
            with self.subTest(name=name):
                self.assert_invalid(broken, pattern)

    def test_directives_are_stripped_and_empty_spoken_turns_are_rejected(self):
        script = [
            {"speaker": "Host", "content": "Hello [[pause:0.5]] there."},
            {"speaker": "Guest", "content": "[[style:calm]]"},
            {
                "speaker": "Host",
                "content": "[[style:serious]] Second [[pause]] idea.",
            },
            {"speaker": "Guest", "content": "Third idea."},
            {"speaker": "Host", "content": "Fourth idea."},
        ]
        payload = make_payload(
            chapter_starts=(0, 2), clip_ranges=((0, 0), (2, 2), (3, 3))
        )

        result, llm = self.generate(payload, script=script, chapter_count=2)
        self.assertEqual(llm.call_count, 1)
        self.assertEqual(result["social_clips"][0]["spoken_text"], "Hello there.")
        self.assertEqual(result["social_clips"][1]["spoken_text"], "Second idea.")
        exported = json.dumps(result["social_clips"])
        self.assertNotIn("[[pause", exported)
        self.assertNotIn("[[style", exported)

        broken = copy.deepcopy(payload)
        broken["social_clips"][0]["end_turn"] = 1
        self.assert_invalid(
            broken,
            "turn 1.*no spoken text",
            script=script,
            chapter_count=2,
        )

        broken_chapters = copy.deepcopy(payload)
        broken_chapters["chapters"][1]["start_turn"] = 1
        self.assert_invalid(
            broken_chapters,
            "start_turn.*has no spoken text",
            script=script,
            chapter_count=2,
        )

    def test_indexes_are_based_on_normalized_not_raw_script_positions(self):
        script = [
            None,
            {"role": "Host", "text": " Turn zero "},
            {"speaker": "Skipped", "content": "   "},
            {"speaker": "Guest", "content": "Turn one"},
            "malformed",
            {"speaker": "Host", "content": "Turn two"},
            {"role": "Guest", "text": "Turn three"},
            {"speaker": "Host", "content": "Turn four"},
            {"speaker": "Guest", "content": "Turn five"},
        ]
        result, llm = self.generate(script=script)
        self.assertEqual(
            result["social_clips"][0]["spoken_text"], "Turn zero\nTurn one"
        )
        self.assertEqual(result["chapters"][2]["start_turn"], 4)
        self.assertEqual(llm.call_count, 1)
        prompt = llm.calls[0]["messages"][1]["content"]
        self.assertNotIn("Skipped", prompt)
        self.assertIn('"speaker": "Host"', prompt)

    def test_short_script_generates_one_clip_per_available_turn(self):
        payload = make_payload(chapter_starts=(0,), clip_ranges=((0, 0), (1, 1)))
        result, llm = self.generate(payload, script=SCRIPT[:2], chapter_count=1)
        self.assertEqual(len(result["social_clips"]), 2)
        self.assertEqual(llm.call_count, 1)
        self.assertIn(
            "Required social clip count: 2",
            llm.calls[0]["messages"][1]["content"],
        )

        broken = make_payload(chapter_starts=(0,), clip_ranges=((0, 0),))
        self.assert_invalid(
            broken,
            "social_clips.*exactly 2",
            script=SCRIPT[:2],
            chapter_count=1,
        )

    def test_empty_script_allows_empty_chapters_and_clips(self):
        payload = make_payload(chapter_starts=(), clip_ranges=())
        result, llm = self.generate(payload, script=[], chapter_count=4)
        self.assertEqual(result["chapters"], [])
        self.assertEqual(result["social_clips"], [])
        self.assertEqual(llm.call_count, 1)

    def test_none_chapter_count_disables_chapters(self):
        payload = make_payload(chapter_starts=())
        result, llm = self.generate(payload, chapter_count=None)
        self.assertEqual(result["chapters"], [])
        self.assertEqual(len(result["social_clips"]), 3)
        self.assertEqual(llm.call_count, 1)

    def test_same_response_produces_identical_results(self):
        response = json.dumps(make_payload())
        first, first_llm = self.generate(raw_response=response)
        second, second_llm = self.generate(raw_response=response)
        self.assertEqual(first, second)
        self.assertEqual(
            json.dumps(first, ensure_ascii=False, sort_keys=True),
            json.dumps(second, ensure_ascii=False, sort_keys=True),
        )
        self.assertEqual(first_llm.call_count, 1)
        self.assertEqual(second_llm.call_count, 1)
        self.assertEqual(first_llm.calls[0], second_llm.calls[0])

    def test_chapter_timing_uses_measured_start_for_each_turn(self):
        extras = {"chapters": [{"title": "One", "start_turn": 0}, {"title": "Two", "start_turn": 3}]}
        timed = with_chapter_timing(extras, {0: 0.0, 3: 12.3456})
        self.assertEqual(timed["chapters"][1]["startTime"], 12.346)
        with self.assertRaisesRegex(ValueError, "chapter turn 3"):
            with_chapter_timing(extras, {0: 0.0})


if __name__ == "__main__":
    unittest.main()
