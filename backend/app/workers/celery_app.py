from celery import Celery
from celery.signals import worker_process_init

from ..core.config import settings
from ..core.logging_config import configure_dependency_logging


configure_dependency_logging()
broker = settings.redis_url or "memory://"
backend = settings.redis_url or "cache+memory://"
celery_app = Celery("beyond_words", broker=broker, backend=backend)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.celery_eager,
    broker_connection_retry_on_startup=True,
    task_send_sent_event=True,
    worker_send_task_events=True,
    timezone="UTC",
)
celery_app.autodiscover_tasks(["backend.app.workers"])


@worker_process_init.connect
def configure_worker_observability(**_kwargs) -> None:
    from ..core.observability import configure_observability

    configure_observability(settings.otel_service_name)
