"""Tests for the .env loader and the RSS feed generator.

Run with: python3 -m unittest test_backend_utils -v
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from env_loader import load_env_file, parse_env_file  # noqa: E402
from rss_generator import generate_podcast_rss  # noqa: E402


class EnvLoaderTest(unittest.TestCase):
    def test_parses_basic_pairs(self):
        self.assertEqual(parse_env_file("A=1\nB=two"), {"A": "1", "B": "two"})

    def test_ignores_comments_and_blanks(self):
        self.assertEqual(parse_env_file("# comment\n\nA=1\n"), {"A": "1"})

    def test_strips_export_prefix(self):
        self.assertEqual(parse_env_file("export A=1"), {"A": "1"})

    def test_strips_matching_quotes(self):
        self.assertEqual(parse_env_file('A="hello world"'), {"A": "hello world"})

    def test_inline_comment_on_unquoted_value(self):
        self.assertEqual(parse_env_file("A=1 # comment"), {"A": "1"})

    def test_hash_inside_quotes_is_kept(self):
        self.assertEqual(parse_env_file('A="1 # not a comment"'), {"A": "1 # not a comment"})

    def test_lines_without_equals_are_ignored(self):
        self.assertEqual(parse_env_file("not a pair"), {})

    def test_existing_environment_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w") as handle:
                handle.write("PBP_TEST_EXISTING=from_file\nPBP_TEST_NEW=fresh\n")
            os.environ["PBP_TEST_EXISTING"] = "from_env"
            try:
                applied = load_env_file(path)
                self.assertEqual(os.environ["PBP_TEST_EXISTING"], "from_env")
                self.assertEqual(os.environ["PBP_TEST_NEW"], "fresh")
                self.assertEqual(applied, {"PBP_TEST_NEW": "fresh"})
            finally:
                del os.environ["PBP_TEST_EXISTING"]
                del os.environ["PBP_TEST_NEW"]

    def test_missing_file_is_a_noop(self):
        self.assertEqual(load_env_file("/nonexistent/.env"), {})


class RssGeneratorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write_episode(self, name="episode one.wav", metadata=None, transcript=False, chapters=False):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as handle:
            handle.write(b"0" * 48000)  # one second at 24 kHz mono 16-bit
        if metadata is not None:
            with open(os.path.splitext(path)[0] + ".json", "w") as handle:
                json.dump(metadata, handle)
        if transcript:
            with open(os.path.splitext(path)[0] + ".transcript.json", "w") as handle:
                json.dump({"script": []}, handle)
        if chapters:
            with open(os.path.splitext(path)[0] + ".chapters.json", "w") as handle:
                json.dump({"version": "1.2.0", "chapters": [{"startTime": 0, "title": "Opening"}]}, handle)
        return path

    def test_duration_comes_from_metadata(self):
        self.write_episode(metadata={"duration_seconds": 95.0})
        feed = generate_podcast_rss(self.tmp.name)
        self.assertIn("<itunes:duration>01:35</itunes:duration>", feed)

    def test_duration_estimate_uses_24khz_mono(self):
        self.write_episode()
        feed = generate_podcast_rss(self.tmp.name)
        self.assertIn("<itunes:duration>00:01</itunes:duration>", feed)

    def test_guid_is_stable_when_episode_id_exists(self):
        self.write_episode(metadata={"episode_id": "abc-123"})
        feed = generate_podcast_rss(self.tmp.name)
        self.assertIn('<guid isPermaLink="false">abc-123</guid>', feed)

    def test_guid_falls_back_to_enclosure_url(self):
        self.write_episode()
        feed = generate_podcast_rss(self.tmp.name)
        self.assertIn("<guid>http://localhost:8000/outputs/episode%20one.wav</guid>", feed)

    def test_enclosure_url_is_quoted(self):
        self.write_episode()
        feed = generate_podcast_rss(self.tmp.name)
        self.assertIn("episode%20one.wav", feed)

    def test_pubdate_is_utc(self):
        path = self.write_episode()
        timestamp = os.stat(path).st_mtime
        expected = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
            "%a, %d %b %Y %H:%M:%S +0000"
        )
        feed = generate_podcast_rss(self.tmp.name)
        self.assertIn(f"<pubDate>{expected}</pubDate>", feed)

    def test_transcript_element_is_emitted_when_sidecar_exists(self):
        self.write_episode(transcript=True)
        feed = generate_podcast_rss(self.tmp.name)
        self.assertIn("<podcast:transcript", feed)

    def test_chapters_element_is_emitted_when_sidecar_exists(self):
        self.write_episode(chapters=True)
        feed = generate_podcast_rss(self.tmp.name)
        self.assertIn('<podcast:chapters', feed)
        self.assertIn('episode%20one.chapters.json', feed)
        self.assertIn('type="application/json+chapters"', feed)

    def test_no_transcript_element_without_sidecar(self):
        self.write_episode()
        feed = generate_podcast_rss(self.tmp.name)
        self.assertNotIn("<podcast:transcript", feed)

    def test_channel_metadata(self):
        self.write_episode()
        feed = generate_podcast_rss(
            self.tmp.name,
            channel_image="https://example.com/art.png",
            channel_email="host@example.com",
        )
        self.assertIn('<itunes:image href="https://example.com/art.png"/>', feed)
        self.assertIn("<itunes:email>host@example.com</itunes:email>", feed)
        self.assertIn("<atom:link", feed)
        self.assertIn("<lastBuildDate>", feed)
        self.assertIn("<itunes:explicit>false</itunes:explicit>", feed)


if __name__ == "__main__":
    unittest.main()
