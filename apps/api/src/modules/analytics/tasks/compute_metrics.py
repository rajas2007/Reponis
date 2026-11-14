import logging
import uuid

from asgiref.sync import async_to_sync
from celery import shared_task

from src.core.database import AsyncSessionLocal
from src.modules.analytics.service import compute_repository_metrics

logger = logging.getLogger(__name__)


async def _run_compute_repository_metrics(repository_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        try:
            await compute_repository_metrics(session, repository_id)
            logger.info("Successfully computed metrics for repository %s", repository_id)
        except Exception:
            logger.exception("Failed to compute metrics for repository %s", repository_id)
            # Analytics failure must not crash unhandled or modify sync status


@shared_task(name="compute_repository_metrics_task")
def compute_repository_metrics_task(repository_id_str: str) -> None:
    repository_id = uuid.UUID(repository_id_str)
    async_to_sync(_run_compute_repository_metrics)(repository_id)
