from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.modules.auth.dependencies import CurrentUser
from src.modules.sync import service
from src.modules.sync.schemas import SyncJobResponse

router = APIRouter(prefix="/sync", tags=["Sync"])


@router.post("/start", response_model=SyncJobResponse, status_code=status.HTTP_201_CREATED)
async def start_sync_endpoint(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> SyncJobResponse:
    """Starts synchronization for the active repository."""
    job = await service.start_sync(db, current_user.id)  # type: ignore
    return SyncJobResponse.model_validate(job)


@router.get("/history", response_model=List[SyncJobResponse])
async def get_sync_history_endpoint(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> List[SyncJobResponse]:
    """Retrieves sync history for the active repository."""
    history = await service.get_history(db, current_user.id)  # type: ignore
    return [SyncJobResponse.model_validate(job) for job in history]


@router.get("/{job_id}", response_model=SyncJobResponse)
async def get_sync_job_endpoint(
    job_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> SyncJobResponse:
    """Retrieves a specific sync job status."""
    job = await service.get_job(db, job_id, current_user.id)  # type: ignore
    return SyncJobResponse.model_validate(job)
