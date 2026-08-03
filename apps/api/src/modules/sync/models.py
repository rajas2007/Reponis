import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any, Dict

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, text, Enum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.modules.repositories.models import UserRepository


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SyncStatus(str, PyEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TriggeredBy(str, PyEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Enums: queued, running, completed, failed, cancelled
    status = Column(
        Enum(SyncStatus, name="sync_status"),
        nullable=False,
        default=SyncStatus.QUEUED,
    )
    
    # Enums: manual, scheduled, webhook
    triggered_by = Column(
        Enum(TriggeredBy, name="triggered_by"),
        nullable=False,
        default=TriggeredBy.MANUAL,
    )
    
    progress_data = Column(JSONB, nullable=False, default=dict)
    
    error_message = Column(String, nullable=True)
    
    started_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    repository: Mapped["UserRepository"] = relationship("UserRepository")

    __table_args__ = (
        Index(
            "idx_unique_active_sync_per_repo",
            "user_repository_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )
