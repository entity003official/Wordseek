from __future__ import annotations

import base64
import mimetypes
import logging
import re
import os
import shutil
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from ..core.config import settings
TaskSubmitted = Callable[[str], None]


def resolve_ffmpeg() -> str:
    configured = os.getenv("BEYOND_WORDS_FFMPEG_PATH", "").strip()
    if configured:
        executable = shutil.which(configured)
        if executable:
            return executable
        raise SpeechProviderError("FFMPEG_UNAVAILABLE", "音频转换工具路径无效，请管理员检查 FFmpeg 配置。", retryable=False)
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError) as error:
        raise SpeechProviderError("FFMPEG_UNAVAILABLE", "服务器缺少音频转换工具，请管理员安装 FFmpeg 后重试。原始录音已保留。", retryable=False) from error


def prepare_cloud_audio(path: Path) -> Path:
    """Create the mono 16 kHz FLAC required for reliable Qwen diarization."""
    if not path.is_file() or path.stat().st_size == 0:
        raise SpeechProviderError("AUDIO_FILE_EMPTY", "录音文件为空或不可用，请重新保存录音。", retryable=False)
    executable = resolve_ffmpeg()
    fd, name = tempfile.mkstemp(suffix=".flac")
    os.close(fd)
    output = Path(name)
    try:
        conversion = subprocess.run(
            [
                executable, "-nostdin", "-hide_banner", "-loglevel", "info", "-y", "-i", str(path),
                "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", "-af", "volumedetect", "-c:a", "flac", str(output),
            ],
            check=True,
            capture_output=True,
            timeout=600,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if output.stat().st_size == 0:
            raise subprocess.CalledProcessError(1, executable)
        volume_log = conversion.stderr.decode("utf-8", errors="replace")
        mean = re.search(r"mean_volume:\s*(-?[\d.]+) dB", volume_log)
        peak = re.search(r"max_volume:\s*(-?[\d.]+) dB", volume_log)
        if mean and peak and float(mean[1]) <= -75 and float(peak[1]) <= -60:
            output.unlink(missing_ok=True)
            raise SpeechProviderError(
                "AUDIO_NEAR_SILENT",
                "录音几乎没有声音，无法转写。请取消麦克风静音或切换输入设备，重新录音后先试听。原录音已保留。",
                retryable=False,
            )
    except OSError as error:
        output.unlink(missing_ok=True)
        raise SpeechProviderError("FFMPEG_UNAVAILABLE", "服务器无法运行音频转换工具，请管理员检查安装与权限。原始录音已保留。", retryable=False) from error
    except subprocess.TimeoutExpired as error:
        output.unlink(missing_ok=True)
        raise SpeechProviderError("AUDIO_PREPROCESSING_TIMEOUT", "录音转换超时，请稍后重新分析。原始录音已保留。", retryable=True) from error
    except subprocess.SubprocessError as error:
        output.unlink(missing_ok=True)
        raise SpeechProviderError(
            "AUDIO_PREPROCESSING_FAILED",
            "录音无法解码，可能没有音轨或文件不完整。原始录音已保留，请先试听检查。",
            retryable=False,
        ) from error
    return output


class SpeechProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class SpeechProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def analyze(
        self,
        path: Path,
        *,
        language_hints: list[str],
        speaker_policy: dict[str, Any],
        audio_url: str | None = None,
        existing_task_id: str | None = None,
        on_task_submitted: TaskSubmitted | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError


class QwenSpeechProvider(SpeechProvider):
    name = "qwen"
    model = settings.qwen_file_model

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.api_key = settings.read_qwen_api_key()
        self.base_url = settings.qwen_api_base_url
        self.client = client or httpx.Client(timeout=settings.qwen_timeout_seconds, follow_redirects=True)
        self.retry_count = 0

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _headers(self, *, async_request: bool = False, temporary_url: bool = False) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if async_request:
            headers["X-DashScope-Async"] = "enable"
        if temporary_url:
            headers["X-DashScope-OssResourceResolve"] = "enable"
        return headers

    @staticmethod
    def _raise_for_response(response: httpx.Response, operation: str) -> None:
        if response.is_success:
            return
        try:
            detail = response.json()
        except ValueError:
            detail = {}
        if not isinstance(detail, dict):
            detail = {}
        # Match known provider signals; never expose arbitrary upstream text,
        # which can contain URLs, credentials or request content.
        provider_message = str(detail.get("message") or "")
        if "ASR_RESPONSE_HAVE_NO_WORDS" in provider_message:
            raise SpeechProviderError(
                "QWEN_NO_SPEECH",
                "没有识别到语音。请确认麦克风有声音，说完一句话后再停止录音。",
                retryable=False,
            )
        safe_code = str(detail.get("code") or "")
        if not safe_code or len(safe_code) > 80 or not all(c.isalnum() or c in "._-" for c in safe_code):
            safe_code = "unknown"
        logging.getLogger(__name__).warning("Qwen speech request failed: HTTP %s, code=%s", response.status_code, safe_code)
        retryable = response.status_code == 429 or response.status_code >= 500
        code = {
            400: "QWEN_INVALID_REQUEST",
            401: "QWEN_AUTH_ERROR",
            403: "QWEN_PERMISSION_DENIED",
            413: "QWEN_AUDIO_TOO_LARGE",
            415: "QWEN_AUDIO_FORMAT_UNSUPPORTED",
            422: "QWEN_INVALID_REQUEST",
            429: "QWEN_RATE_LIMITED",
        }.get(response.status_code, "QWEN_UPSTREAM_ERROR" if response.status_code >= 500 else "QWEN_REQUEST_REJECTED")
        messages = {
            400: "语音转写请求或音频无法处理，请重试；若仍失败，请联系管理员检查转写参数。",
            401: "千问密钥无效或已过期，请管理员更新密钥。",
            403: "千问拒绝访问，请管理员检查模型权限、地域和账户状态。",
            413: "录音过大，请缩短录音后重试。",
            415: "千问不支持此音频格式，请重新录音。",
            422: "语音转写参数无效，请管理员检查配置。",
        }
        message = (
            f"千问语音服务在{operation}时暂时不可用，请稍后重试。"
            if retryable
            else messages.get(response.status_code, f"千问未能完成{operation}，请稍后重试。")
        )
        raise SpeechProviderError(code, message, retryable=retryable)

    def _request(self, method: str, url: str, operation: str, *, attempt_limit: int | None = None, **kwargs: Any) -> httpx.Response:
        max_attempts = attempt_limit if attempt_limit is not None else 1 + max(0, settings.qwen_max_retries)
        # Multipart streams cannot be replayed safely inside one HTTP request
        # loop. A failed upload is retried by the durable Celery job instead.
        if "files" in kwargs:
            max_attempts = 1
        last_error: SpeechProviderError | None = None
        for attempt in range(max_attempts):
            try:
                response = self.client.request(method, url, **kwargs)
                self._raise_for_response(response, operation)
                return response
            except (httpx.TimeoutException, httpx.TransportError) as error:
                last_error = SpeechProviderError(
                    "QWEN_NETWORK_ERROR", f"千问语音服务在{operation}时网络超时，请稍后重试。", retryable=True
                )
                last_error.__cause__ = error
            except SpeechProviderError as error:
                last_error = error
                if not error.retryable:
                    raise
            if attempt + 1 < max_attempts:
                self.retry_count += 1
                time.sleep(settings.qwen_retry_base_seconds * (2 ** attempt))
        if last_error:
            raise last_error
        raise SpeechProviderError("QWEN_PROVIDER_ERROR", "千问语音服务请求失败。", retryable=True)

    def _temporary_upload(self, path: Path) -> str:
        policy_response = self._request(
            "GET",
            "https://dashscope.aliyuncs.com/api/v1/uploads",
            "申请临时音频地址",
            headers=self._headers(),
            params={"action": "getPolicy", "model": self.model},
        )
        policy = policy_response.json().get("data") or {}
        required = {
            "policy", "signature", "upload_dir", "upload_host", "oss_access_key_id",
            "x_oss_object_acl", "x_oss_forbid_overwrite",
        }
        if not required.issubset(policy):
            raise SpeechProviderError("QWEN_UPLOAD_POLICY_INVALID", "千问未返回完整的临时上传凭证。", retryable=False)
        filename = "recording" + (path.suffix.lower() or ".webm")
        object_key = f"{policy['upload_dir'].rstrip('/')}/{filename}"
        data = {
            "OSSAccessKeyId": policy["oss_access_key_id"],
            "Signature": policy["signature"],
            "policy": policy["policy"],
            "x-oss-object-acl": policy["x_oss_object_acl"],
            "x-oss-forbid-overwrite": policy["x_oss_forbid_overwrite"],
            "key": object_key,
            "success_action_status": "200",
        }
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        with path.open("rb") as handle:
            self._request(
                "POST",
                str(policy["upload_host"]),
                "上传临时音频",
                data=data,
                files={"file": (filename, handle, mime)},
            )
        return f"oss://{object_key}"

    def _submit(self, audio_url: str, language_hints: list[str], speaker_policy: dict[str, Any]) -> str:
        parameters: dict[str, Any] = {
            "channel_id": [0],
            "diarization_enabled": True,
            "language_hints": language_hints[:4],
            "vocabulary": {"Anker": 5, "soundcore": 5, "Beyond Words": 5},
        }
        expected = speaker_policy.get("expected_count")
        if expected and int(expected) >= 2:
            parameters["speaker_count"] = int(expected)
        response = self._request(
            "POST",
            f"{self.base_url}/services/audio/asr/transcription",
            "提交转写",
            headers=self._headers(async_request=True, temporary_url=audio_url.startswith("oss://")),
            json={"model": self.model, "input": {"file_urls": [audio_url]}, "parameters": parameters},
        )
        output = response.json().get("output") or {}
        task_id = output.get("task_id")
        if not task_id:
            raise SpeechProviderError("QWEN_TASK_ID_MISSING", "千问没有返回任务编号。", retryable=False)
        return str(task_id)

    def _poll(self, task_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        deadline = time.monotonic() + settings.qwen_poll_timeout_seconds
        while time.monotonic() < deadline:
            response = self._request(
                "GET", f"{self.base_url}/tasks/{task_id}", "查询转写任务", headers=self._headers()
            )
            payload = response.json()
            output = payload.get("output") or {}
            status = str(output.get("task_status", "")).upper()
            failure_details = [output, *(output.get("results") or [])]
            if any("ASR_RESPONSE_HAVE_NO_WORDS" in str(item.get("code", "")) or "ASR_RESPONSE_HAVE_NO_WORDS" in str(item.get("message", "")) for item in failure_details if isinstance(item, dict)):
                raise SpeechProviderError(
                    "QWEN_NO_SPEECH", "千问没有识别到语音。请先试听原录音，确认麦克风录到了清晰的人声。", retryable=False,
                )
            if status == "SUCCEEDED":
                results = output.get("results") or []
                successful = next(
                    (item for item in results if item.get("subtask_status") == "SUCCEEDED" and item.get("transcription_url")),
                    None,
                )
                if not successful:
                    raise SpeechProviderError(
                        "QWEN_SUBTASK_FAILED", "千问任务已结束，但音频子任务失败。", retryable=True
                    )
                result_response = self._request(
                    "GET", str(successful["transcription_url"]), "下载转写结果"
                )
                return result_response.json(), payload.get("usage") or {}
            if status in {"FAILED", "CANCELED", "CANCELLED", "TERMINATED", "UNKNOWN"}:
                raise SpeechProviderError(
                    "QWEN_TASK_TERMINATED", "千问转写任务异常终止，请稍后重试。", retryable=True
                )
            time.sleep(settings.qwen_poll_interval_seconds)
        raise SpeechProviderError("QWEN_POLL_TIMEOUT", "等待千问转写结果超时。", retryable=True)

    @staticmethod
    def _normalize(result: dict[str, Any], usage: dict[str, Any]) -> dict[str, Any]:
        raw_sentences: list[dict[str, Any]] = []
        for transcript in result.get("transcripts") or []:
            raw_sentences.extend(transcript.get("sentences") or [])
        raw_sentences.sort(key=lambda item: (int(item.get("begin_time", 0)), int(item.get("end_time", 0))))
        speaker_map: dict[str, str] = {}
        turns: list[dict[str, Any]] = []
        words: list[dict[str, Any]] = []
        for sentence in raw_sentences:
            raw_speaker = sentence.get("speaker_id")
            if raw_speaker is None:
                speaker_id = "SPEAKER_UNKNOWN"
            else:
                key = str(raw_speaker)
                if key not in speaker_map:
                    speaker_map[key] = f"SPEAKER_{len(speaker_map):02d}"
                speaker_id = speaker_map[key]
            sentence_words = sentence.get("words") or []
            text = str(sentence.get("text") or "").strip()
            if not text and sentence_words:
                text = "".join(
                    f"{str(word.get('text') or '')}{str(word.get('punctuation') or '')}" for word in sentence_words
                ).strip()
            if text:
                turns.append({
                    "id": f"turn_{len(turns) + 1:03d}",
                    "speaker_id": speaker_id,
                    "start_ms": int(sentence.get("begin_time") or 0),
                    "end_ms": int(sentence.get("end_time") or sentence.get("begin_time") or 0),
                    "text": text,
                })
            for word in sentence_words:
                word_text = f"{str(word.get('text') or '')}{str(word.get('punctuation') or '')}"
                if word_text.strip():
                    words.append({
                        "speaker_id": speaker_id,
                        "start_ms": int(word.get("begin_time") or 0),
                        "end_ms": int(word.get("end_time") or word.get("begin_time") or 0),
                        "text": word_text,
                    })
        properties = result.get("properties") or {}
        speakers = list(speaker_map.values()) or ["SPEAKER_UNKNOWN"]
        duration_ms = properties.get("original_duration_in_milliseconds")
        if duration_ms is None and usage.get("duration") is not None:
            duration_ms = int(float(usage["duration"]) * 1000)
        return {
            "engine": "qwen",
            "model": settings.qwen_file_model,
            "language": None,
            "turns": turns,
            "words": words,
            "speakers": speakers,
            "diarization": {
                "status": "complete" if speaker_map else "unavailable",
                "model": settings.qwen_file_model,
                "speaker_count": len(speaker_map),
                "reason": None if speaker_map else "provider_did_not_return_speaker_ids",
            },
            "provider_usage": {
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "estimated_cost_cny": None,
            },
            "audio_duration_ms": duration_ms,
        }

    @staticmethod
    def fast_audio_duration(path: Path, speaker_policy: dict[str, Any]) -> int | None:
        # Read FLAC STREAMINFO rather than trusting client-reported duration.
        # Explicit speaker counts remain on the file API that supports them.
        if speaker_policy.get("expected_count") or settings.qwen_short_model != "qwen-audio-3.1-asr-flash":
            return None
        if path.suffix.lower() != ".flac" or not path.is_file() or path.stat().st_size > 7 * 1024 * 1024:
            return None
        with path.open("rb") as handle:
            header = handle.read(42)
        if len(header) < 42 or header[:4] != b"fLaC" or header[4] & 0x7f != 0:
            return None
        info = int.from_bytes(header[18:26], "big")
        rate = info >> 44
        samples = info & ((1 << 36) - 1)
        if not rate or not samples:
            return None
        duration_ms = (samples * 1000 + rate - 1) // rate
        return duration_ms if duration_ms <= 60000 else None

    def analyze_fast(self, path: Path, duration_ms: int) -> dict[str, Any]:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        response = self._request(
            "POST", f"{self.base_url}/services/aigc/multimodal-generation/generation", "转写录音",
            attempt_limit=1, timeout=45,
            headers={**self._headers(), "X-DashScope-SSE": "disable"},
            json={
                "model": settings.qwen_short_model,
                "input": {"messages": [{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": f"data:audio/flac;base64,{encoded}"}}]}]},
                "parameters": {"format": "flac", "sample_rate": "16000", "speaker_diarization_enabled": True},
            },
        )
        body = response.json()
        output = body.get("output") or {}
        sentences = output.get("sentences") or ([output["sentence"]] if output.get("sentence") else [])
        if not sentences:
            raise SpeechProviderError("QWEN_RESULT_INCOMPLETE", "千问未返回完整的话轮，请稍后重试。", retryable=True)
        normalized = self._normalize({
            "properties": {"original_duration_in_milliseconds": duration_ms},
            "transcripts": [{"sentences": sentences}],
        }, body.get("usage") or {})
        normalized["model"] = settings.qwen_short_model
        normalized["diarization"]["model"] = settings.qwen_short_model
        normalized["provider_retry_count"] = self.retry_count
        normalized["resumed_existing_task"] = False
        normalized["processing_route"] = "direct"
        return normalized

    def analyze(
        self,
        path: Path,
        *,
        language_hints: list[str],
        speaker_policy: dict[str, Any],
        audio_url: str | None = None,
        existing_task_id: str | None = None,
        on_task_submitted: TaskSubmitted | None = None,
    ) -> dict[str, Any]:
        if not self.available:
            raise SpeechProviderError("QWEN_NOT_CONFIGURED", "尚未配置千问 API Key。", retryable=False)
        if not existing_task_id:
            fast_duration = self.fast_audio_duration(path, speaker_policy)
            if fast_duration is not None:
                return self.analyze_fast(path, fast_duration)
        task_id = existing_task_id
        resumed_existing_task = bool(existing_task_id)
        if not task_id:
            if settings.qwen_audio_url_mode == "temporary":
                audio_url = self._temporary_upload(path)
            if not audio_url:
                raise SpeechProviderError(
                    "QWEN_PUBLIC_AUDIO_URL_REQUIRED",
                    "当前对象存储没有可供千问访问的公网签名地址，请配置 OSS 或改用 temporary 开发模式。",
                    retryable=False,
                )
            task_id = self._submit(audio_url, language_hints, speaker_policy)
            if on_task_submitted:
                on_task_submitted(task_id)
        result, usage = self._poll(task_id)
        normalized = self._normalize(result, usage)
        normalized["provider_retry_count"] = self.retry_count
        normalized["resumed_existing_task"] = resumed_existing_task
        return normalized

    def transcribe_short(self, path: Path, content_type: str, language_hints: list[str]) -> dict[str, Any]:
        if not self.available:
            raise SpeechProviderError("QWEN_NOT_CONFIGURED", "尚未配置千问 API Key。", retryable=False)
        # MediaRecorder containers can omit duration metadata. Decode locally
        # before submitting so all browsers use one complete, mono audio file.
        prepared = prepare_cloud_audio(path)
        try:
            raw = prepared.read_bytes()
        finally:
            prepared.unlink(missing_ok=True)
        encoded = base64.b64encode(raw).decode("ascii")
        if len(encoded) > 10 * 1024 * 1024:
            raise SpeechProviderError("QWEN_SHORT_AUDIO_TOO_LARGE", "练习录音超过同步接口 10 MB 限制。", retryable=False)
        data_uri = f"data:audio/flac;base64,{encoded}"
        payload = {
            "model": settings.qwen_short_model,
            "input": {"messages": [{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": data_uri}}]}]},
            "parameters": {
                "format": "flac",
                "sample_rate": "16000",
                "speaker_diarization_enabled": False,
                "language_hints": language_hints[:4],
                "vocabulary": {"Anker": 5, "soundcore": 5, "Beyond Words": 5},
            },
        }
        response = self._request(
            "POST",
            f"{self.base_url}/services/aigc/multimodal-generation/generation",
            "转写练习录音",
            headers={**self._headers(), "X-DashScope-SSE": "disable"},
            json=payload,
        )
        body = response.json()
        output = body.get("output") or {}
        return {
            "text": str(output.get("text") or "").strip(),
            "language": None,
            "model": settings.qwen_short_model,
            "provider": "qwen",
            "usage": body.get("usage") or {},
            "retry_count": self.retry_count,
        }
