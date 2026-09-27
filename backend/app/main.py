from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import structlog
import redis.asyncio as async_redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from .api import admin, auth, health, jobs, practice, profile, sessions, live_speech
from .core.config import settings
from .core.logging_config import configure_dependency_logging
from .core.observability import configure_observability, instrument_api, register_queue_depth_metrics
from .db import SessionLocal, init_development_database
from .db import engine
from .models import AnalysisJob
from .workers.tasks import process_ai, process_speech

configure_dependency_logging()
structlog.configure(processors=[structlog.processors.TimeStamper(fmt="iso"), structlog.processors.add_log_level, structlog.processors.JSONRenderer()])
logger = structlog.get_logger()
_rate_windows: dict[str, deque[float]] = defaultdict(deque)
redis_client = async_redis.from_url(settings.redis_url, decode_responses=True) if settings.redis_url else None


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate()
    init_development_database()
    if not settings.celery_eager:
        with SessionLocal() as db:
            pending = list(db.query(AnalysisJob).filter(AnalysisJob.status.in_(["queued", "running"])).all())
            for job in pending:
                job.status = "queued"
                job.progress = 0
            db.commit()
        for job in pending:
            (process_speech if job.kind == "speech" else process_ai).delay(job.id)
    yield
    if redis_client:
        await redis_client.aclose()


app = FastAPI(
    title="Beyond Words API",
    version="1.0.0",
    docs_url="/api/docs" if not settings.public_runtime else None,
    openapi_url="/api/openapi.json" if not settings.public_runtime else None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, https_only=settings.session_cookie_secure, same_site="lax")

try:
    meter = configure_observability(settings.otel_service_name)
    request_counter = meter.create_counter("beyond_words.http.requests")
    request_duration = meter.create_histogram("beyond_words.http.duration", unit="ms")
    register_queue_depth_metrics(meter)
    instrument_api(app, engine)
except Exception as error:
    logger.warning("otel_initialization_skipped", error_type=type(error).__name__)
    request_counter = None
    request_duration = None


@app.middleware("http")
async def security_and_request_id(request: Request, call_next):
    request_started = time.perf_counter()
    request_id = (request.headers.get("X-Request-ID") or str(uuid.uuid4()))[:80]
    request.state.request_id = request_id
    if request.url.path in {"/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/forgot-password"}:
        key = f"{request.client.host if request.client else 'unknown'}:{request.url.path}"
        now = time.monotonic()
        limited = False
        if redis_client:
            try:
                redis_key = f"rate:{key}:{int(time.time() // 60)}"
                count = await redis_client.incr(redis_key)
                if count == 1:
                    await redis_client.expire(redis_key, 70)
                limited = count > 10
            except Exception:
                limited = False
        if not redis_client:
            window = _rate_windows[key]
            while window and now - window[0] > 60:
                window.popleft()
            limited = len(window) >= 10
            window.append(now)
        if limited:
            return JSONResponse(status_code=429, content={"error": {"code": "RATE_LIMITED", "message": "请求过于频繁，请稍后重试", "request_id": request_id, "retryable": True}})
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "microphone=(self), camera=()"
    if settings.production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    route = request.scope.get("route")
    route_template = getattr(route, "path", None) or "__unmatched__"
    logger.info("http_request", method=request.method, path=route_template, status=response.status_code, request_id=request_id)
    if request_counter and request_duration:
        attributes = {"http.request.method": request.method, "http.route": route_template, "http.response.status_code": response.status_code}
        request_counter.add(1, attributes)
        request_duration.record((time.perf_counter() - request_started) * 1000, attributes)
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, error: HTTPException):
    request_id = getattr(request.state, "request_id", "unknown")
    if isinstance(error.detail, dict):
        code = str(error.detail.get("code", "REQUEST_FAILED"))
        message = str(error.detail.get("message", "请求失败"))
        retryable = bool(error.detail.get("retryable", False))
    else:
        code = {400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 413: "PAYLOAD_TOO_LARGE", 415: "UNSUPPORTED_MEDIA_TYPE", 422: "VALIDATION_FAILED", 429: "RATE_LIMITED", 503: "SERVICE_UNAVAILABLE"}.get(error.status_code, "REQUEST_FAILED")
        message = str(error.detail)
        retryable = error.status_code in {429, 500, 502, 503}
    return JSONResponse(status_code=error.status_code, content={"error": {"code": code, "message": message, "request_id": request_id, "retryable": retryable}})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError):
    fields = [".".join(str(part) for part in item.get("loc", [])[1:]) for item in error.errors()]
    return JSONResponse(
        status_code=422,
        content={"error": {
            "code": "VALIDATION_FAILED",
            "message": "请检查填写内容是否完整、格式是否正确",
            "request_id": getattr(request.state, "request_id", "unknown"),
            "retryable": False,
            "fields": [field for field in fields if field],
        }},
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("unhandled_request_error", request_id=request_id, path=request.url.path, error_type=type(error).__name__)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "服务暂时不可用，请稍后重试", "request_id": request_id, "retryable": True}},
    )


for api_router in (live_speech.router, auth.router, profile.router, sessions.router, practice.router, jobs.router, admin.router, health.router):
    app.include_router(api_router, prefix="/api/v1")


@app.get("/api/health", include_in_schema=False)
def legacy_health_redirect() -> dict:
    return {"status": "upgrade-required", "api": "/api/v1", "message": "客户端请使用版本化接口"}
