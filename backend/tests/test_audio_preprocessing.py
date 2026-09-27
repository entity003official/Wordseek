import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.app.speech.providers import SpeechProviderError, prepare_cloud_audio, resolve_ffmpeg


class AudioPreprocessingTest(unittest.TestCase):
    @patch.dict(os.environ, {"BEYOND_WORDS_FFMPEG_PATH": ""})
    @patch("backend.app.speech.providers.shutil.which", return_value=None)
    @patch("imageio_ffmpeg.get_ffmpeg_exe", return_value="bundled-ffmpeg.exe")
    def test_uses_bundled_executable_without_system_path(self, bundled, which):
        self.assertEqual(resolve_ffmpeg(), "bundled-ffmpeg.exe")

    @patch.dict(os.environ, {"BEYOND_WORDS_FFMPEG_PATH": ""})
    @patch("backend.app.speech.providers.shutil.which", return_value="/usr/bin/ffmpeg")
    def test_prefers_system_executable(self, which):
        self.assertEqual(resolve_ffmpeg(), "/usr/bin/ffmpeg")

    def test_rejects_empty_audio_without_running_a_process(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "empty.webm"
            source.touch()
            with patch("backend.app.speech.providers.subprocess.run") as run:
                with self.assertRaises(SpeechProviderError) as raised:
                    prepare_cloud_audio(source)
                self.assertEqual(raised.exception.code, "AUDIO_FILE_EMPTY")
                run.assert_not_called()

    def test_reports_failure_type_and_cleans_partial_output(self):
        failures = [
            (FileNotFoundError(), "FFMPEG_UNAVAILABLE", False),
            (subprocess.TimeoutExpired("ffmpeg", 600), "AUDIO_PREPROCESSING_TIMEOUT", True),
            (subprocess.CalledProcessError(1, "ffmpeg"), "AUDIO_PREPROCESSING_FAILED", False),
        ]
        for failure, code, retryable in failures:
            with self.subTest(code=code), TemporaryDirectory() as directory:
                source = Path(directory) / "original.webm"
                source.write_bytes(b"original")
                outputs = []
                def fail(command, **kwargs):
                    outputs.append(Path(command[-1]))
                    raise failure
                with patch("backend.app.speech.providers.resolve_ffmpeg", return_value="ffmpeg"), patch("backend.app.speech.providers.subprocess.run", side_effect=fail):
                    with self.assertRaises(SpeechProviderError) as raised:
                        prepare_cloud_audio(source)
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(raised.exception.retryable, retryable)
                self.assertFalse(outputs[0].exists())
                self.assertEqual(source.read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
