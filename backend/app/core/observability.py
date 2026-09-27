from __future__ import annotations

import os
import socket
from typing import Any

import structlog

from .config import settings


logger = structlog.get_logger()
_configured = False
_queue_gauge: Any | None = None


def configure_observability(service_name: str | None = None):
    """Configure OTLP once per process and return a meter even when OTLP is disabled."""
    global _configured
    from opentelemetry import metrics

    name = service_name or settings.otel_service_name
    if not settings.otel_endpoint or _configured:
        return metrics.get_meter(name)
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({
            "service.name": name,
            "service.instance.id": f"{socket.gethostname()}-{os.getpid()}",
        })
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
            endpoint=settings.otel_endpoint,
            insecure=settings.otel_endpoint.startswith("http://"),
        )))
        trace.set_tracer_provider(tracer_provider)
        metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter(
            endpoint=settings.otel_endpoint,
            insecure=settings.otel_endpoint.startswith("http://"),
        ))
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
        _configured = True
    except Exception as error:
        logger.warning("otel_initialization_skipped", error_type=type(error).__name__)
    return metrics.get_meter(name)


def instrument_api(app, engine) -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        SQLAlchemyInstrumentor().instrument(engine=engine)
    except Exception as error:
        logger.warning("otel_api_instrumentation_skipped", error_type=type(error).__name__)


def register_queue_depth_metrics(meter) -> None:
    global _queue_gauge
    if _queue_gauge is not None or not settings.redis_url or settings.celery_eager:
        return
    try:
        from opentelemetry.metrics import Observation
        from redis import Redis

        def observe(_options):
            client = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
            try:
                return [
                    Observation(client.llen("default"), {"queue": "default"}),
                    Observation(client.llen("speech"), {"queue": "speech"}),
                ]
            except Exception:
                return []
            finally:
                client.close()

        _queue_gauge = meter.create_observable_gauge(
            "beyond_words.queue.depth",
            callbacks=[observe],
            description="Celery broker queue depth",
        )
    except Exception as error:
        logger.warning("queue_metric_initialization_skipped", error_type=type(error).__name__)


_task_meter = None
_task_attempts = None
_task_duration = None
_provider_duration = None


def record_task_attempt(
    *,
    kind: str,
    status: str,
    provider: str,
    duration_seconds: float,
    error_code: str | None = None,
    provider_latency_ms: int | None = None,
) -> None:
    global _task_meter, _task_attempts, _task_duration, _provider_duration
    try:
        if _task_meter is None:
            from opentelemetry import metrics

            _task_meter = metrics.get_meter("beyond-words-workers")
            _task_attempts = _task_meter.create_counter("beyond_words.task.attempts")
            _task_duration = _task_meter.create_histogram("beyond_words.task.duration", unit="s")
            _provider_duration = _task_meter.create_histogram("beyond_words.provider.duration", unit="ms")
        attributes = {
            "task.kind": kind,
            "task.status": status,
            "provider": provider,
            "error.code": error_code or "none",
        }
        _task_attempts.add(1, attributes)
        _task_duration.record(max(0, duration_seconds), attributes)
        if provider_latency_ms is not None:
            _provider_duration.record(max(0, provider_latency_ms), {"provider": provider, "task.kind": kind})
    except Exception as error:
        logger.warning("task_metric_recording_skipped", error_type=type(error).__name__)
