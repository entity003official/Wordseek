from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from ..core.config import settings


class TtsProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class TtsResult:
    audio: bytes
    content_type: str
    usage: dict[str, Any]
    latency_ms: int
    retry_count: int


class QwenTtsProvider:
    name = "qwen"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.api_key = settings.read_qwen_api_key()
        self.base_url = settings.qwen_api_base_url
        self.model = settings.qwen_tts_model
        self.voice = settings.qwen_tts_voice
        self.client = client or httpx.Client(timeout=settings.qwen_tts_timeout_seconds, follow_redirects=True)
        self.retry_count = 0

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _error_for_status(status_code: int, operation: str) -> TtsProviderError:
        retryable = status_code == 429 or status_code >= 500
        code = {
            400: "QWEN_TTS_INVALID_REQUEST",
            401: "QWEN_TTS_AUTH_ERROR",
            403: "QWEN_TTS_PERMISSION_DENIED",
            429: "QWEN_TTS_RATE_LIMITED",
        }.get(status_code, "QWEN_TTS_UPSTREAM_ERROR" if status_code >= 500 else "QWEN_TTS_REQUEST_REJECTED")
        message = (
            f"千问语音合成服务在{operation}时暂时不可用，请稍后重试。"
            if retryable
            else f"千问语音合成服务拒绝了{operation}请求，请管理员检查 API Key、模型权限和余额。"
        )
        return TtsProviderError(code, message, retryable=retryable)

    def _request(self, method: str, url: str, operation: str, **kwargs: Any) -> httpx.Response:
        attempts = 1 + max(0, settings.qwen_max_retries)
        last_error: TtsProviderError | None = None
        for attempt in range(attempts):
            try:
                response = self.client.request(method, url, **kwargs)
                if response.is_success:
                    return response
                last_error = self._error_for_status(response.status_code, operation)
                if not last_error.retryable:
                    raise last_error
            except (httpx.TimeoutException, httpx.TransportError) as error:
                last_error = TtsProviderError(
                    "QWEN_TTS_NETWORK_ERROR",
                    f"千问语音合成服务在{operation}时网络超时，请稍后重试。",
                    retryable=True,
                )
                last_error.__cause__ = error
            if attempt + 1 < attempts:
                self.retry_count += 1
                time.sleep(settings.qwen_retry_base_seconds * (2 ** attempt))
        if last_error:
            raise last_error
        raise TtsProviderError("QWEN_TTS_PROVIDER_ERROR", "千问语音合成请求失败。", retryable=True)

    def synthesize(self, text: str, language: str = "English") -> TtsResult:
        if not self.available:
            raise TtsProviderError("QWEN_TTS_NOT_CONFIGURED", "尚未配置千问 API Key。", retryable=False)
        started = time.perf_counter()
        response = self._request(
            "POST",
            f"{self.base_url}/services/aigc/multimodal-generation/generation",
            "生成练习语音",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "input": {"text": text, "voice": self.voice, "language_type": language},
            },
        )
        body = response.json()
        audio_url = str(((body.get("output") or {}).get("audio") or {}).get("url") or "")
        if not audio_url:
            raise TtsProviderError(
                "QWEN_TTS_INVALID_RESPONSE",
                "千问语音合成没有返回可用音频，请稍后重试。",
                retryable=True,
            )
        audio_response = self._request("GET", audio_url, "下载合成语音")
        audio = audio_response.content
        if not audio or len(audio) > settings.qwen_tts_max_audio_bytes:
            raise TtsProviderError(
                "QWEN_TTS_INVALID_AUDIO",
                "千问返回的合成语音为空或超过大小限制。",
                retryable=False,
            )
        content_type = audio_response.headers.get("content-type", "audio/wav").split(";", 1)[0]
        if not content_type.startswith("audio/"):
            content_type = "audio/wav"
        return TtsResult(
            audio=audio,
            content_type=content_type,
            usage=body.get("usage") or {},
            latency_ms=round((time.perf_counter() - started) * 1000),
            retry_count=self.retry_count,
        )
