import unittest

import httpx

from backend.app.speech.tts import QwenTtsProvider, TtsProviderError


class RecordingClient:
    def __init__(self, responses) -> None:
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return next(self.responses)


class QwenTtsProviderContractTest(unittest.TestCase):
    def test_uses_qwen3_official_contract_and_downloads_audio(self) -> None:
        request = httpx.Request("POST", "https://example.test")
        client = RecordingClient([
            httpx.Response(
                200,
                json={"output": {"audio": {"url": "https://audio.example.test/result.wav"}}, "usage": {"input_tokens": 8}},
                request=request,
            ),
            httpx.Response(
                200,
                content=b"RIFF-test-audio",
                headers={"content-type": "audio/wav"},
                request=httpx.Request("GET", "https://audio.example.test/result.wav"),
            ),
        ])
        provider = QwenTtsProvider(client=client)
        provider.api_key = "test-key"
        provider.base_url = "https://dashscope.aliyuncs.com/api/v1"
        provider.model = "qwen3-tts-flash"
        provider.voice = "Cherry"

        result = provider.synthesize("How many passengers will there be?")

        method, url, kwargs = client.calls[0]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/services/aigc/multimodal-generation/generation"))
        self.assertEqual(kwargs["json"], {
            "model": "qwen3-tts-flash",
            "input": {
                "text": "How many passengers will there be?",
                "voice": "Cherry",
                "language_type": "English",
            },
        })
        self.assertEqual(client.calls[1][0:2], ("GET", "https://audio.example.test/result.wav"))
        self.assertEqual(result.audio, b"RIFF-test-audio")
        self.assertEqual(result.content_type, "audio/wav")

    def test_auth_error_is_stable_and_does_not_expose_provider_body(self) -> None:
        client = RecordingClient([
            httpx.Response(
                401,
                text='{"message":"secret provider detail"}',
                request=httpx.Request("POST", "https://example.test"),
            ),
        ])
        provider = QwenTtsProvider(client=client)
        provider.api_key = "test-key"
        with self.assertRaises(TtsProviderError) as caught:
            provider.synthesize("Hello")
        self.assertEqual(caught.exception.code, "QWEN_TTS_AUTH_ERROR")
        self.assertFalse(caught.exception.retryable)
        self.assertNotIn("secret provider detail", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
