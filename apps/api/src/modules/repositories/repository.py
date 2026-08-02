from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.repositories.models import UserRepository


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RepositoriesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_by_user_id(self, user_id: UUID) -> Optional[UserRepository]:
        stmt = select(UserRepository).where(
            UserRepository.user_id == user_id,
            UserRepository.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all_by_user_id(self, user_id: UUID) -> List[UserRepository]:
        stmt = (
            select(UserRepository)
            .where(UserRepository.user_id == user_id)
            .order_by(UserRepository.connected_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_github_id(
        self, user_id: UUID, github_repo_id: int
    ) -> Optional[UserRepository]:
        stmt = select(UserRepository).where(
            UserRepository.user_id == user_id, UserRepository.github_repo_id == github_repo_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def disconnect_active(self, user_id: UUID) -> None:
        stmt = (
            update(UserRepository)
            .where(
                UserRepository.user_id == user_id,
                UserRepository.is_active.is_(True),
            )
            .values(is_active=False, disconnected_at=utc_now(), updated_at=utc_now())
        )
        await self.session.execute(stmt)

    async def create(self, user_repo: UserRepository) -> UserRepository:
        self.session.add(user_repo)
        await self.session.flush()
        return user_repo

    async def update(self, user_repo: UserRepository) -> UserRepository:
        user_repo.updated_at = utc_now()
        await self.session.flush()
        return user_repo
