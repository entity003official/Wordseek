from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _csv(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, default).split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("BEYOND_WORDS_ENV", "development")
    database_url: str = os.getenv(
        "BEYOND_WORDS_DATABASE_URL",
        f"sqlite:///{(ROOT_DIR / 'backend' / 'data' / 'beyond_words_v1.db').as_posix()}",
    )
    redis_url: str = os.getenv("BEYOND_WORDS_REDIS_URL", "")
    celery_eager: bool = _bool("BEYOND_WORDS_CELERY_EAGER", True)
    session_secret: str = os.getenv("BEYOND_WORDS_SESSION_SECRET", "development-only-change-me")
    session_cookie_secure: bool = _bool("BEYOND_WORDS_SESSION_COOKIE_SECURE", False)
    session_idle_days: int = int(os.getenv("BEYOND_WORDS_SESSION_IDLE_DAYS", "7"))
    session_absolute_days: int = int(os.getenv("BEYOND_WORDS_SESSION_ABSOLUTE_DAYS", "30"))
    frontend_url: str = os.getenv("BEYOND_WORDS_FRONTEND_URL", "http://localhost:5173")
    cors_origins: tuple[str, ...] = _csv("BEYOND_WORDS_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    data_dir: Path = Path(os.getenv("BEYOND_WORDS_DATA_DIR", ROOT_DIR / "backend" / "data")).resolve()
    max_audio_bytes: int = int(os.getenv("BEYOND_WORDS_MAX_AUDIO_BYTES", str(250 * 1024 * 1024)))
    auto_create_schema: bool = _bool("BEYOND_WORDS_AUTO_CREATE_SCHEMA", True)

    deepseek_enabled: bool = _bool("BEYOND_WORDS_DEEPSEEK_ENABLED", True)
    deepseek_base_url: str = os.getenv("BEYOND_WORDS_DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    deepseek_model: str = os.getenv("BEYOND_WORDS_DEEPSEEK_MODEL", "deepseek-flash")
    deepseek_api_key_file: Path = Path(
        os.getenv("BEYOND_WORDS_DEEPSEEK_API_KEY_FILE", ROOT_DIR / "api-key" / "api-key.txt")
    ).resolve()
    deepseek_timeout_seconds: float = float(os.getenv("BEYOND_WORDS_DEEPSEEK_TIMEOUT_SECONDS", "45"))
    ai_review_regenerations_per_day: int = int(os.getenv("BEYOND_WORDS_AI_REGENERATIONS_PER_DAY", "3"))
    ai_feedback_per_day: int = int(os.getenv("BEYOND_WORDS_AI_FEEDBACK_PER_DAY", "20"))

    speech_backend: str = os.getenv("BEYOND_WORDS_SPEECH_BACKEND", "qwen").strip().lower()
    qwen_api_key_file: Path = Path(
        os.getenv("BEYOND_WORDS_QWEN_API_KEY_FILE", ROOT_DIR / "api-key" / "dashscope_api_key.txt")
    ).resolve()
    qwen_workspace_id_file: Path = Path(
        os.getenv("BEYOND_WORDS_QWEN_WORKSPACE_ID_FILE", ROOT_DIR / "api-key" / "dashscope_workspace_id.txt")
    ).resolve()
    qwen_base_url: str = os.getenv(
        "BEYOND_WORDS_QWEN_BASE_URL", "https://dashscope.aliyuncs.com/api/v1"
    ).rstrip("/")
    qwen_file_model: str = os.getenv(
        "BEYOND_WORDS_QWEN_FILE_MODEL", "qwen-audio-3.1-asr-flash-filetrans"
    )
    qwen_short_model: str = os.getenv(
        "BEYOND_WORDS_QWEN_SHORT_MODEL", "qwen-audio-3.1-asr-flash"
    )
    qwen_tts_model: str = os.getenv("BEYOND_WORDS_QWEN_TTS_MODEL", "qwen3-tts-flash")
    qwen_tts_voice: str = os.getenv("BEYOND_WORDS_QWEN_TTS_VOICE", "Cherry")
    qwen_tts_timeout_seconds: float = float(os.getenv("BEYOND_WORDS_QWEN_TTS_TIMEOUT_SECONDS", "90"))
    qwen_tts_max_audio_bytes: int = int(os.getenv("BEYOND_WORDS_QWEN_TTS_MAX_AUDIO_BYTES", str(10 * 1024 * 1024)))
    qwen_tts_generations_per_day: int = int(os.getenv("BEYOND_WORDS_QWEN_TTS_GENERATIONS_PER_DAY", "30"))
    qwen_audio_url_mode: str = os.getenv("BEYOND_WORDS_QWEN_AUDIO_URL_MODE", "temporary").strip().lower()
    qwen_timeout_seconds: float = float(os.getenv("BEYOND_WORDS_QWEN_TIMEOUT_SECONDS", "60"))
    qwen_poll_interval_seconds: float = float(os.getenv("BEYOND_WORDS_QWEN_POLL_INTERVAL_SECONDS", "2"))
    qwen_poll_timeout_seconds: float = float(os.getenv("BEYOND_WORDS_QWEN_POLL_TIMEOUT_SECONDS", "1800"))
    qwen_max_retries: int = int(os.getenv("BEYOND_WORDS_QWEN_MAX_RETRIES", "3"))
    qwen_retry_base_seconds: float = float(os.getenv("BEYOND_WORDS_QWEN_RETRY_BASE_SECONDS", "1"))

    storage_backend: str = os.getenv("BEYOND_WORDS_STORAGE_BACKEND", "local")
    minio_endpoint: str = os.getenv("BEYOND_WORDS_MINIO_ENDPOINT", "localhost:9000")
    minio_access_key: str = os.getenv("BEYOND_WORDS_MINIO_ACCESS_KEY", "beyondwords")
    minio_secret_key: str = os.getenv("BEYOND_WORDS_MINIO_SECRET_KEY", "change-this-minio-secret")
    minio_bucket: str = os.getenv("BEYOND_WORDS_MINIO_BUCKET", "beyond-words")
    minio_secure: bool = _bool("BEYOND_WORDS_MINIO_SECURE", False)

    oidc_enabled: bool = _bool("BEYOND_WORDS_OIDC_ENABLED", False)
    oidc_issuer: str = os.getenv("BEYOND_WORDS_OIDC_ISSUER", "")
    oidc_client_id: str = os.getenv("BEYOND_WORDS_OIDC_CLIENT_ID", "")
    oidc_client_secret: str = os.getenv("BEYOND_WORDS_OIDC_CLIENT_SECRET", "")
    oidc_display_name: str = os.getenv("BEYOND_WORDS_OIDC_DISPLAY_NAME", "企业账号")

    smtp_host: str = os.getenv("BEYOND_WORDS_SMTP_HOST", "")
    smtp_port: int = int(os.getenv("BEYOND_WORDS_SMTP_PORT", "587"))
    smtp_username: str = os.getenv("BEYOND_WORDS_SMTP_USERNAME", "")
    smtp_password: str = os.getenv("BEYOND_WORDS_SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("BEYOND_WORDS_SMTP_FROM", "")
    dev_show_reset_token: bool = _bool("BEYOND_WORDS_DEV_SHOW_RESET_TOKEN", True)
    otel_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    otel_service_name: str = os.getenv("OTEL_SERVICE_NAME", "beyond-words-api")
    grafana_url: str = os.getenv("BEYOND_WORDS_GRAFANA_URL", "").strip()

    @property
    def production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def user_test(self) -> bool:
        return self.environment.lower() == "user-test"

    @property
    def public_runtime(self) -> bool:
        return self.production or self.user_test

    def read_deepseek_api_key(self) -> str:
        env_key = os.getenv("BEYOND_WORDS_DEEPSEEK_API_KEY", "").strip()
        if env_key:
            return env_key
        try:
            return self.deepseek_api_key_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def read_qwen_api_key(self) -> str:
        env_key = os.getenv("BEYOND_WORDS_QWEN_API_KEY", "").strip()
        if env_key:
            return env_key
        try:
            return self.qwen_api_key_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def read_qwen_workspace_id(self) -> str:
        workspace_id = os.getenv("BEYOND_WORDS_QWEN_WORKSPACE_ID", "").strip()
        if workspace_id:
            return workspace_id
        try:
            return self.qwen_workspace_id_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    @property
    def qwen_api_base_url(self) -> str:
        workspace_id = self.read_qwen_workspace_id()
        if workspace_id:
            return f"https://{workspace_id}.cn-beijing.maas.aliyuncs.com/api/v1"
        return self.qwen_base_url

    def validate(self) -> None:
        if self.speech_backend != "qwen":
            raise RuntimeError("当前生产语音后端固定为 qwen")
        if self.qwen_audio_url_mode not in {"temporary", "presigned"}:
            raise RuntimeError("BEYOND_WORDS_QWEN_AUDIO_URL_MODE 必须是 temporary 或 presigned")
        if self.production and (self.session_secret == "development-only-change-me" or len(self.session_secret) < 32):
            raise RuntimeError("生产环境必须设置至少 32 字符的 BEYOND_WORDS_SESSION_SECRET")
        if self.production and not self.session_cookie_secure:
            raise RuntimeError("生产环境必须启用安全 Cookie")
        if self.production and not self.database_url.startswith(("postgresql://", "postgresql+")):
            raise RuntimeError("生产环境必须使用 PostgreSQL")
        if self.production and self.storage_backend != "minio":
            raise RuntimeError("生产环境必须使用 S3 兼容对象存储")
        if self.production and not self.frontend_url.startswith("https://"):
            raise RuntimeError("生产环境前端地址必须使用 HTTPS")
        if self.production and not self.redis_url.startswith(("redis://", "rediss://")):
            raise RuntimeError("生产环境必须配置 Redis 任务队列")
        if self.production and "*" in self.cors_origins:
            raise RuntimeError("生产环境不允许使用通配 CORS")
        if self.production and self.oidc_enabled and not (self.oidc_issuer and self.oidc_client_id and self.oidc_client_secret):
            raise RuntimeError("启用 OIDC 时必须完整配置 issuer、client id 和 client secret")


settings = Settings()
