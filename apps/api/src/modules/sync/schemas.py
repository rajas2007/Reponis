from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.modules.sync.models import SyncStatus


class ProgressData(BaseModel):
    stage: str
    current_page: int = 1
    total_pages: int = 1
    commits: int = 0
    pull_requests: int = 0
    issues: int = 0
    message: Optional[str] = None
    resume_at: Optional[str] = None


class SyncJobResponse(BaseModel):
    id: UUID
    status: SyncStatus
    progress_data: ProgressData
    started_at: datetime
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
