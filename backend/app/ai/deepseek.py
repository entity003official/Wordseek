from __future__ import annotations

import json
import logging
import random
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx

from ..core.config import settings
from ..core.security import stable_private_id


@dataclass
class DeepSeekResult:
    payload: dict[str, Any]
    usage: dict[str, Any]
    latency_ms: int
    finish_reason: str | None


class DeepSeekError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False, status_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status_code = status_code


class CircuitBreaker:
    def __init__(self, threshold: int = 5, cooldown_seconds: int = 60):
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.opened_at = 0.0
        self.lock = threading.Lock()

    def before_call(self) -> None:
        with self.lock:
            if self.failures >= self.threshold and time.monotonic() - self.opened_at < self.cooldown_seconds:
                raise DeepSeekError("AI_CIRCUIT_OPEN", "AI 服务暂时不可用", retryable=True)
            if self.failures >= self.threshold:
                self.failures = 0

    def success(self) -> None:
        with self.lock:
            self.failures = 0

    def failure(self) -> None:
        with self.lock:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = time.monotonic()


breaker = CircuitBreaker()


def _extract_json(content: str) -> dict[str, Any]:
    normalized = content.strip()
    if normalized.startswith("```"):
        normalized = normalized.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    parsed = json.loads(normalized)
    if not isinstance(parsed, dict):
        raise ValueError("模型结果必须是 JSON 对象")
    return parsed


class DeepSeekClient:
    def __init__(self) -> None:
        self.api_key = settings.read_deepseek_api_key()

    @property
    def configured(self) -> bool:
        return settings.deepseek_enabled and bool(self.api_key)

    def complete_json(
        self,
        *,
        user_id: str,
        system_prompt: str,
        input_payload: dict[str, Any],
        max_tokens: int,
    ) -> DeepSeekResult:
        if not self.configured:
            raise DeepSeekError("AI_NOT_CONFIGURED", "DeepSeek API 尚未配置")
        breaker.before_call()
        body = {
            "model": settings.deepseek_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(input_payload, ensure_ascii=False)},
            ],
            "thinking": {"type": "disabled"},
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens,
            "user_id": stable_private_id(user_id),
            "stream": False,
        }
        started = time.perf_counter()
        last_error: DeepSeekError | None = None
        for attempt in range(3):
            try:
                response = httpx.post(
                    f"{settings.deepseek_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=body,
                    timeout=httpx.Timeout(settings.deepseek_timeout_seconds, connect=5.0),
                )
                if response.status_code >= 400:
                    retryable = response.status_code in {429, 500, 503}
                    code = {
                        400: "AI_BAD_REQUEST",
                        401: "AI_AUTH_FAILED",
                        402: "AI_BALANCE_EXHAUSTED",
                        422: "AI_INVALID_PARAMETERS",
                        429: "AI_PROVIDER_RATE_LIMITED",
                        500: "AI_PROVIDER_ERROR",
                        503: "AI_PROVIDER_OVERLOADED",
                    }.get(response.status_code, "AI_PROVIDER_ERROR")
                    raise DeepSeekError(code, "DeepSeek 请求失败", retryable=retryable, status_code=response.status_code)
                reply = response.json()
                choice = reply["choices"][0]
                if choice.get("finish_reason") == "length":
                    body["max_tokens"] = min(body["max_tokens"] * 2, 8192)
                    raise DeepSeekError("AI_RESPONSE_TRUNCATED", "AI 结果未生成完整，请重试", retryable=True)
                message = choice["message"]
                payload = _extract_json(message.get("content") or "")
                latency_ms = int((time.perf_counter() - started) * 1000)
                breaker.success()
                return DeepSeekResult(
                    payload=payload,
                    usage=reply.get("usage") or {},
                    latency_ms=latency_ms,
                    finish_reason=reply["choices"][0].get("finish_reason"),
                )
            except DeepSeekError as error:
                last_error = error
                if not error.retryable or attempt == 2:
                    break
            except httpx.TimeoutException:
                last_error = DeepSeekError("AI_TIMEOUT", "DeepSeek 响应超时，请重试", retryable=True)
            except httpx.HTTPError:
                last_error = DeepSeekError("AI_NETWORK_ERROR", "无法连接 DeepSeek，请稍后重试", retryable=True)
            except (KeyError, IndexError, AttributeError, TypeError, ValueError) as error:
                logging.getLogger(__name__).warning("DeepSeek response parse failed: %s", type(error).__name__)
                last_error = DeepSeekError("AI_INVALID_RESPONSE", "DeepSeek 返回了无法校验的结果", retryable=True)
                if attempt == 2:
                    break
            time.sleep((2**attempt) + random.uniform(0.05, 0.35))
        breaker.failure()
        raise last_error or DeepSeekError("AI_PROVIDER_ERROR", "DeepSeek 请求失败", retryable=True)


def deepseek_status() -> dict[str, Any]:
    client = DeepSeekClient()
    return {
        "provider": "deepseek",
        "model": settings.deepseek_model,
        "configured": client.configured,
        "audio_shared": False,
        "thinking": "disabled",
    }
