from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.sync.models import SyncJob, SyncStatus


class SyncJobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_job(self, user_repository_id: UUID) -> Optional[SyncJob]:
        stmt = select(SyncJob).where(
            SyncJob.user_repository_id == user_repository_id,
            SyncJob.status.in_([SyncStatus.QUEUED, SyncStatus.RUNNING]),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_id(self, job_id: UUID) -> Optional[SyncJob]:
        stmt = select(SyncJob).where(SyncJob.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_history(self, user_repository_id: UUID, limit: int = 10) -> List[SyncJob]:
        stmt = (
            select(SyncJob)
            .where(SyncJob.user_repository_id == user_repository_id)
            .order_by(SyncJob.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, job: SyncJob) -> SyncJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def update(self, job: SyncJob) -> SyncJob:
        self.session.add(job)
        await self.session.flush()
        return job
