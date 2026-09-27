import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import httpx

from backend.app.speech.providers import QwenSpeechProvider, SpeechProviderError


class RecordingClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


class SequenceClient:
    def __init__(self, responses) -> None:
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return next(self.responses)


class QwenSpeechProviderContractTest(unittest.TestCase):
    def test_submit_uses_official_async_filetrans_contract(self) -> None:
        response = httpx.Response(
            200,
            json={"output": {"task_status": "PENDING", "task_id": "task-123"}},
            request=httpx.Request("POST", "https://example.test"),
        )
        client = RecordingClient(response)
        provider = QwenSpeechProvider(client=client)
        provider.api_key = "test-key"
        provider.base_url = "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1"

        task_id = provider._submit(
            "oss://dashscope-instant/example/recording.webm",
            ["en", "zh"],
            {"mode": "auto", "min_count": 1, "max_count": 8, "expected_count": None},
        )

        self.assertEqual(task_id, "task-123")
        _, url, kwargs = client.calls[0]
        self.assertTrue(url.endswith("/services/audio/asr/transcription"))
        self.assertEqual(kwargs["headers"]["X-DashScope-Async"], "enable")
        self.assertEqual(kwargs["headers"]["X-DashScope-OssResourceResolve"], "enable")
        self.assertEqual(kwargs["json"]["model"], "qwen-audio-3.1-asr-flash-filetrans")
        self.assertTrue(kwargs["json"]["parameters"]["diarization_enabled"])
        self.assertNotIn("speaker_count", kwargs["json"]["parameters"])

    def test_normalize_preserves_timestamps_and_maps_any_speaker_count(self) -> None:
        result = {
            "properties": {"original_duration_in_milliseconds": 4200},
            "transcripts": [{"sentences": [
                {"begin_time": 100, "end_time": 900, "text": "Hello.", "speaker_id": 7, "words": []},
                {"begin_time": 1000, "end_time": 2100, "text": "Hi there.", "speaker_id": 4, "words": []},
                {"begin_time": 2200, "end_time": 3900, "text": "Welcome.", "speaker_id": 12, "words": []},
            ]}],
        }

        normalized = QwenSpeechProvider._normalize(result, {"duration": 4})

        self.assertEqual(normalized["speakers"], ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"])
        self.assertEqual(normalized["turns"][1]["start_ms"], 1000)
        self.assertEqual(normalized["audio_duration_ms"], 4200)
        self.assertEqual(normalized["diarization"]["speaker_count"], 3)
        self.assertIsNone(normalized["provider_usage"]["estimated_cost_cny"])

    def test_429_is_retryable_without_exposing_provider_body(self) -> None:
        response = httpx.Response(
            429,
            text='{"message":"sensitive upstream detail"}',
            request=httpx.Request("POST", "https://example.test"),
        )
        with self.assertRaises(SpeechProviderError) as caught:
            QwenSpeechProvider._raise_for_response(response, "提交转写")
        self.assertTrue(caught.exception.retryable)
        self.assertEqual(caught.exception.code, "QWEN_RATE_LIMITED")
        self.assertNotIn("sensitive", str(caught.exception))

    def test_invalid_key_is_stable_and_not_retryable(self) -> None:
        response = httpx.Response(
            401,
            text='{"message":"provider secret detail"}',
            request=httpx.Request("POST", "https://example.test"),
        )
        with self.assertRaises(SpeechProviderError) as caught:
            QwenSpeechProvider._raise_for_response(response, "提交转写")
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(caught.exception.code, "QWEN_AUTH_ERROR")
        self.assertNotIn("secret", str(caught.exception))

    def test_retryable_provider_error_is_retried_then_succeeds(self) -> None:
        request = httpx.Request("GET", "https://example.test")
        client = SequenceClient([
            httpx.Response(429, request=request),
            httpx.Response(503, request=request),
            httpx.Response(200, json={"ok": True}, request=request),
        ])
        provider = QwenSpeechProvider(client=client)
        with patch("backend.app.speech.providers.time.sleep") as sleep:
            response = provider._request("GET", "https://example.test", "测试重试")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(provider.retry_count, 2)
        self.assertEqual(sleep.call_count, 2)

    def test_existing_task_is_polled_without_resubmitting_or_uploading(self) -> None:
        provider = QwenSpeechProvider()
        provider.api_key = "test-key"
        provider._temporary_upload = Mock(side_effect=AssertionError("must not upload again"))
        provider._submit = Mock(side_effect=AssertionError("must not submit again"))
        provider._poll = Mock(return_value=({
            "properties": {"original_duration_in_milliseconds": 1000},
            "transcripts": [{"sentences": [
                {"begin_time": 0, "end_time": 1000, "text": "Hello.", "speaker_id": 0, "words": []},
            ]}],
        }, {}))

        result = provider.analyze(
            Path("unused.flac"),
            language_hints=["en"],
            speaker_policy={"mode": "auto", "min_count": 1, "max_count": 8},
            existing_task_id="task-existing",
        )

        provider._poll.assert_called_once_with("task-existing")
        self.assertEqual(result["turns"][0]["text"], "Hello.")

    def test_short_audio_uses_official_non_streaming_contract(self) -> None:
        response = httpx.Response(
            200,
            json={"output": {"text": "Hello from practice."}, "usage": {"duration": 2}},
            request=httpx.Request("POST", "https://example.test"),
        )
        client = RecordingClient(response)
        provider = QwenSpeechProvider(client=client)
        provider.api_key = "test-key"
        provider.base_url = "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1"

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "practice.webm"
            path.write_bytes(b"test-audio")
            prepared = Path(temp_dir) / "prepared.flac"
            prepared.write_bytes(b"converted-audio")
            with patch("backend.app.speech.providers.prepare_cloud_audio", return_value=prepared):
                result = provider.transcribe_short(path, "audio/webm;codecs=opus", ["en", "zh"])

        _, url, kwargs = client.calls[0]
        payload = kwargs["json"]
        self.assertTrue(url.endswith("/services/aigc/multimodal-generation/generation"))
        self.assertEqual(kwargs["headers"]["X-DashScope-SSE"], "disable")
        self.assertEqual(payload["model"], "qwen-audio-3.1-asr-flash")
        self.assertEqual(payload["parameters"]["format"], "flac")
        self.assertFalse(payload["parameters"]["speaker_diarization_enabled"])
        self.assertTrue(payload["input"]["messages"][0]["content"][0]["input_audio"]["data"].startswith("data:audio/flac;base64,"))
        self.assertEqual(result["text"], "Hello from practice.")


if __name__ == "__main__":
    unittest.main()
