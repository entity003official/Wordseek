import unittest
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, patch

from fastapi import HTTPException

from backend.app.api.health import QwenSpeechProvider, ready


class ReadinessTest(unittest.TestCase):
    def test_missing_qwen_key_fails_readiness(self) -> None:
        database = Mock()
        with (
            patch("backend.app.api.health.settings", SimpleNamespace(celery_eager=True)),
            patch("backend.app.api.health.get_storage", return_value=Mock()),
            patch.object(QwenSpeechProvider, "available", new_callable=PropertyMock, return_value=False),
            self.assertRaises(HTTPException) as caught,
        ):
            ready(database)

        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn("千问", str(caught.exception.detail))


if __name__ == "__main__":
    unittest.main()
