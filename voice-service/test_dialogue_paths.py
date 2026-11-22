import asyncio
import base64
import io
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
from scipy.io import wavfile

import main


def wav_bytes(duration_seconds: float, value: int = 1000) -> bytes:
    rate = 24000
    samples = np.full(int(rate * duration_seconds), value, dtype=np.int16)
    buffer = io.BytesIO()
    wavfile.write(buffer, rate, samples)
    return buffer.getvalue()


class LocalDialogueTest(unittest.TestCase):
    def test_qwen_uses_distinct_voices_and_measures_chapters(self):
        req = main.TTSLongformRequest(
            script=[
                {"speaker": "Host", "content": "Opening turn."},
                {"speaker": "Guest", "content": "Guest answer."},
            ],
            engine="qwen3-tts",
            voice_names=["Ryan", "Aiden"],
            extras={"chapters": [{"title": "Opening", "start_turn": 0}, {"title": "Answer", "start_turn": 1}]},
        )
        calls = []

        def fake_synthesize(engine, text, **kwargs):
            calls.append((engine, text, kwargs))
            return wav_bytes(0.1 if len(calls) == 1 else 0.2)

        with patch.object(main, "synthesize", side_effect=fake_synthesize):
            audio, chunks, _seconds, chapter_starts = main._do_tts_engine_script_sync(
                req, main.normalize_turns(req.script), 350, "test"
            )

        self.assertEqual([call[2]["voice"] for call in calls], ["Ryan", "Aiden"])
        self.assertEqual(chunks, 2)
        self.assertEqual(chapter_starts, {0: 0.0, 1: 0.35})
        _, samples = wavfile.read(io.BytesIO(audio))
        self.assertEqual(len(samples), 13200)

    def test_chatterbox_uses_consented_reference_per_speaker(self):
        req = main.TTSLongformRequest(
            script=[
                {"speaker": "Host", "content": "Opening turn."},
                {"speaker": "Guest", "content": "Guest answer."},
            ],
            engine="chatterbox",
            voice_names=["host.wav", "guest.wav"],
        )
        references = [
            {"id": "host.wav", "name": "Host", "path": "/consented/host.wav", "reference_text": "Host reference"},
            {"id": "guest.wav", "name": "Guest", "path": "/consented/guest.wav", "reference_text": "Guest reference"},
        ]
        calls = []
        with (
            patch.object(main, "_consented_references", return_value=references),
            patch.object(main, "synthesize", side_effect=lambda *args, **kwargs: calls.append(kwargs) or wav_bytes(0.1)),
        ):
            main._do_tts_engine_script_sync(req, main.normalize_turns(req.script), 350, "test")
        self.assertEqual(
            [call["reference_path"] for call in calls],
            ["/consented/host.wav", "/consented/guest.wav"],
        )


class SarvamDialogueTest(unittest.TestCase):
    def test_sarvam_uses_per_turn_voices_and_writes_chapters(self):
        req = main.SarvamTTSRequest(
            text="Opening turn.\n\nGuest answer.",
            script=[
                {"speaker": "Host", "content": "Opening turn."},
                {"speaker": "Guest", "content": "Guest answer."},
            ],
            voice_names=["shubh", "shreya"],
            target_language_code="hi-IN",
            language="hi-IN",
            save_to_disk=True,
            topic="Dialogue test",
            extras={
                "title": "Dialogue test",
                "description": "Test episode",
                "chapters": [{"title": "Opening", "start_turn": 0}, {"title": "Answer", "start_turn": 1}],
            },
        )
        audio_by_voice = {
            "shubh": wav_bytes(0.1, 1000),
            "shreya": wav_bytes(0.2, -1000),
        }
        speakers = []

        class FakeResponse:
            ok = True
            status_code = 200
            text = ""

            def __init__(self, audio):
                self.audio = audio

            def json(self):
                return {"audios": [base64.b64encode(self.audio).decode()]}

        def fake_post(_url, headers=None, json=None, timeout=None):
            speakers.append(json["speaker"])
            return FakeResponse(audio_by_voice[json["speaker"]])

        async def render():
            with patch.object(main.requests, "post", side_effect=fake_post):
                response = await main.tts_sarvam(req)
                return b"".join([part async for part in response.body_iterator])

        with tempfile.TemporaryDirectory() as output_dir:
            with (
                patch.object(main, "OUTPUT_DIR", output_dir),
                patch.object(main, "LOUDNESS_NORMALIZATION", False),
                patch.object(main, "measure_loudness", return_value=None),
            ):
                audio = asyncio.run(render())
                saved_files = [name for name in os.listdir(output_dir) if name.endswith(".wav")]
                self.assertEqual(len(saved_files), 1)
                saved = os.path.join(output_dir, saved_files[0])
                with open(os.path.splitext(saved)[0] + ".chapters.json") as handle:
                    chapters = json.load(handle)

        self.assertEqual(speakers, ["shubh", "shreya"])
        _, samples = wavfile.read(io.BytesIO(audio))
        self.assertEqual(len(samples), 24000 * 0.3)
        self.assertEqual(chapters["chapters"][0]["startTime"], 0.0)
        self.assertEqual(chapters["chapters"][1]["startTime"], 0.1)

    def test_scripted_request_honours_explicit_first_speaker(self):
        req = main.SarvamTTSRequest(
            text="A short turn.",
            script=[{"speaker": "Host", "content": "A short turn."}],
            speaker="shreya",
            target_language_code="en-IN",
            language="en",
            save_to_disk=False,
        )
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {"audios": [base64.b64encode(wav_bytes(0.1)).decode()]}
        with (
            patch.object(main.requests, "post", return_value=response) as post,
            patch.object(main, "LOUDNESS_NORMALIZATION", False),
            patch.object(main, "measure_loudness", return_value=None),
        ):
            asyncio.run(main.tts_sarvam(req))
        self.assertEqual(post.call_args.kwargs["json"]["speaker"], "shreya")

    def test_indic_fallback_is_rejected_without_sarvam(self):
        req = main.SarvamTTSRequest(
            text="हिंदी परीक्षण",
            target_language_code="hi-IN",
            language="hi-IN",
            save_to_disk=True,
        )
        with patch.object(main, "get_api_key", return_value=None):
            with self.assertRaises(main.HTTPException) as raised:
                asyncio.run(main.tts_sarvam(req))
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("no downgraded file", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
