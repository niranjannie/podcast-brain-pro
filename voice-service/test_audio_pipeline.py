import io
import unittest
import warnings

import numpy as np
from scipy.io import wavfile

from audio_pipeline import ffmpeg_available, normalize_loudness, stitch_wav_bytes


def wav_bytes(samples: np.ndarray, rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    wavfile.write(buffer, rate, samples)
    return buffer.getvalue()


class StitchWavBytesTest(unittest.TestCase):
    def test_stitched_wav_has_valid_sizes_and_requested_silence(self):
        first = np.full(2400, 1000, dtype=np.int16)
        second = np.full(1200, -1000, dtype=np.int16)

        with warnings.catch_warnings():
            warnings.simplefilter("error", wavfile.WavFileWarning)
            stitched = stitch_wav_bytes(
                [wav_bytes(first), wav_bytes(second)], gaps_ms=[100]
            )
            rate, samples = wavfile.read(io.BytesIO(stitched))

        self.assertEqual(rate, 24000)
        self.assertEqual(len(samples), 2400 + 2400 + 1200)
        np.testing.assert_array_equal(samples[:2400], first)
        np.testing.assert_array_equal(samples[2400:4800], np.zeros(2400, dtype=np.int16))
        np.testing.assert_array_equal(samples[4800:], second)

    def test_stereo_shape_is_preserved(self):
        first = np.ones((120, 2), dtype=np.int16)
        second = np.full((120, 2), 2, dtype=np.int16)
        stitched = stitch_wav_bytes([wav_bytes(first), wav_bytes(second)], gaps_ms=[0])
        _, samples = wavfile.read(io.BytesIO(stitched))
        self.assertEqual(samples.shape, (240, 2))

    @unittest.skipUnless(ffmpeg_available(), "ffmpeg is not installed")
    def test_loudness_normalization_writes_a_valid_riff_header(self):
        rate = 24000
        samples = (np.sin(np.arange(rate // 4) * 0.1) * 10000).astype(np.int16)
        normalized = normalize_loudness(wav_bytes(samples))
        with warnings.catch_warnings():
            warnings.simplefilter("error", wavfile.WavFileWarning)
            output_rate, output = wavfile.read(io.BytesIO(normalized))
        self.assertEqual(output_rate, rate)
        self.assertGreater(len(output), 0)

    def test_mismatched_sample_rates_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "different sample rates"):
            stitch_wav_bytes([
                wav_bytes(np.zeros(100, dtype=np.int16), 24000),
                wav_bytes(np.zeros(100, dtype=np.int16), 16000),
            ])


if __name__ == "__main__":
    unittest.main()
