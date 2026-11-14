from celery import Celery

from src.core.config import settings

celery_app = Celery(
    "reponis",
    broker=str(settings.REDIS_URL),
    backend=str(settings.REDIS_URL),
    include=[
        "src.modules.sync.tasks.sync_repository",
        "src.modules.analytics.tasks.compute_metrics",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    include=[
        "src.modules.sync.tasks.sync_repository",
        "src.modules.analytics.tasks.compute_metrics",
    ],
)
