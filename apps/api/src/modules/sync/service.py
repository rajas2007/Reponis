import uuid
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.repositories.repository import RepositoriesRepository
from src.modules.sync.models import SyncJob, SyncStatus, TriggeredBy
from src.modules.sync.repository import SyncJobRepository
from src.modules.sync.tasks.sync_repository import sync_repository_task


async def start_sync(session: AsyncSession, user_id: uuid.UUID) -> SyncJob:
    repo_repo = RepositoriesRepository(session)
    active_repo = await repo_repo.get_active_by_user_id(user_id)

    if not active_repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active repository connected.",
        )

    sync_repo = SyncJobRepository(session)

    # Check if a queued or running job exists
    from typing import cast

    repo_id = cast(uuid.UUID, active_repo.id)
    existing_job = await sync_repo.get_active_job(repo_id)
    if existing_job:
        return existing_job

    # Create new job
    from typing import Any

    new_job = SyncJob(
        user_repository_id=cast(Any, repo_id),
        status=SyncStatus.QUEUED,
        triggered_by=TriggeredBy.MANUAL,
        progress_data={
            "stage": "initializing",
            "current_page": 0,
            "total_pages": 0,
            "commits": 0,
            "pull_requests": 0,
            "issues": 0,
            "message": "Queued for synchronization",
            "resume_at": None,
        },
    )

    await sync_repo.create(new_job)
    await session.commit()
    await session.refresh(new_job)

    # Trigger Celery task
    sync_repository_task.delay(str(new_job.id))

    return new_job


async def get_job(session: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID) -> SyncJob:
    sync_repo = SyncJobRepository(session)
    job = await sync_repo.get_by_id(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sync job not found.",
        )

    # Ensure job belongs to the user
    from typing import cast

    job_repo_id = cast(uuid.UUID, job.user_repository_id)
    repo_repo = RepositoriesRepository(session)
    user_repo = await repo_repo.get_by_id(job_repo_id)

    if not user_repo or user_repo.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    return job


async def get_history(session: AsyncSession, user_id: uuid.UUID) -> List[SyncJob]:
    repo_repo = RepositoriesRepository(session)
    active_repo = await repo_repo.get_active_by_user_id(user_id)

    if not active_repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active repository connected.",
        )

    sync_repo = SyncJobRepository(session)
    from typing import cast

    repo_id = cast(uuid.UUID, active_repo.id)
    return await sync_repo.get_history(repo_id)
