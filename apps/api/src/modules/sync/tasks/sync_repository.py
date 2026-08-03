import asyncio
import uuid
from typing import Any, Dict

from asgiref.sync import async_to_sync
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.modules.repositories.models import UserRepository
from src.modules.sync.models import SyncJob, SyncStatus
from src.modules.sync.repository import SyncJobRepository


async def _run_sync(job_id: uuid.UUID):
    async with AsyncSessionLocal() as session:
        sync_repo = SyncJobRepository(session)
        job = await sync_repo.get_by_id(job_id)
        
        if not job or job.status != SyncStatus.QUEUED:
            return

        # Mark as running
        job.status = SyncStatus.RUNNING
        job.progress_data = {
            **job.progress_data,
            "stage": "repository_metadata",
            "message": "Starting sync...",
        }
        
        # In a real app we'd catch RateLimitExceptions from GitHub layer here.
        # For MVP we will mock the sleep or failure.
        
        await sync_repo.update(job)
        await session.commit()
        
        # Get repository to sync
        user_repo = await session.get(UserRepository, job.user_repository_id)
        if not user_repo:
            job.status = SyncStatus.FAILED
            job.error_message = "Repository not found in database."
            from src.modules.sync.models import utc_now
            job.finished_at = utc_now()
            await session.commit()
            return
            
        try:
            # 1. Repo metadata
            job.progress_data = {**job.progress_data, "stage": "repository_metadata"}
            await session.commit()
            
            # 2. Commits
            job.progress_data = {**job.progress_data, "stage": "commits"}
            await session.commit()
            
            # 3. Pull Requests
            job.progress_data = {**job.progress_data, "stage": "pull_requests"}
            await session.commit()
            
            # 4. Issues
            job.progress_data = {**job.progress_data, "stage": "issues"}
            await session.commit()
            
            # Mark completed
            job.status = SyncStatus.COMPLETED
            from src.modules.sync.models import utc_now
            job.finished_at = utc_now()
            job.progress_data = {
                **job.progress_data,
                "message": "Synchronization completed successfully."
            }
            await session.commit()
            
        except Exception as e:
            job.status = SyncStatus.FAILED
            job.error_message = str(e)
            job.progress_data = {
                **job.progress_data,
                "message": "Synchronization failed."
            }
            from src.modules.sync.models import utc_now
            job.finished_at = utc_now()
            await session.commit()


@shared_task(name="sync_repository_task")
def sync_repository_task(job_id_str: str) -> None:
    job_id = uuid.UUID(job_id_str)
    async_to_sync(_run_sync)(job_id)
