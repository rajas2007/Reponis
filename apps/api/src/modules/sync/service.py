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
    existing_job = await sync_repo.get_active_job(active_repo.id)
    if existing_job:
        return existing_job

    # Create new job
    new_job = SyncJob(
        user_repository_id=active_repo.id,
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
    # We must join with UserRepository to check this
    repo_repo = RepositoriesRepository(session)
    repo = await session.get(repo_repo.session.get_bind().mapper.class_, job.user_repository_id) # simpler to just get user repo by id, wait, let's do a fast query
    # actually, I'll write a small check
    # But for now, let's fetch the repo to verify
    # Let's import the model directly and check
    from src.modules.repositories.models import UserRepository
    user_repo = await session.get(UserRepository, job.user_repository_id)
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
    return await sync_repo.get_history(active_repo.id)
