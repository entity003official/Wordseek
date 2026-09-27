import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class QwenOnlyBoundaryTest(unittest.TestCase):
    def test_local_provider_is_archived_outside_runtime(self) -> None:
        expected = [
            "backend/asr.py",
            "backend/diarization.py",
            "backend/speech_pipeline.py",
            "backend/model_setup.py",
            "backend/local_provider.py",
            "deploy/Dockerfile.speech",
            "deploy/requirements-asr.txt",
            "tests/test_diarization.py",
            "evaluation/transcribe_local_sample.py",
        ]
        archive = ROOT / "archive" / "local-speech-provider"
        self.assertTrue((archive / "README.zh-CN.md").is_file())
        for relative in expected:
            self.assertTrue((archive / relative).is_file(), relative)

    def test_default_compose_uses_lightweight_qwen_worker(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("worker-qwen:", compose)
        self.assertNotIn("worker-gpu:", compose)
        self.assertNotIn("worker-speech:", compose)
        self.assertNotIn("capabilities: [gpu]", compose)

    def test_user_test_compose_exposes_only_the_same_origin_gateway(self) -> None:
        override = (ROOT / "docker-compose.user-test.yml").read_text(encoding="utf-8")
        caddy = (ROOT / "deploy" / "Caddyfile.user-test").read_text(encoding="utf-8")
        self.assertIn('"127.0.0.1:18080:8080"', override)
        self.assertIn("BEYOND_WORDS_ENV: user-test", override)
        self.assertIn('BEYOND_WORDS_SESSION_COOKIE_SECURE: "false"', override)
        self.assertNotIn("8000:8000", override)
        self.assertIn("reverse_proxy api:8000", caddy)
        self.assertIn("reverse_proxy web:8080", caddy)

    def test_active_backend_has_no_local_model_imports(self) -> None:
        active_files = list((ROOT / "backend" / "app").rglob("*.py"))
        content = "\n".join(path.read_text(encoding="utf-8") for path in active_files)
        for forbidden in ("faster_whisper", "pyannote", "LocalSpeechProvider", "local_asr_available"):
            self.assertNotIn(forbidden, content)


if __name__ == "__main__":
    unittest.main()
