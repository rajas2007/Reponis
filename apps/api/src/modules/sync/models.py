import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, String, text
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

    # Fencing and scheduling fields
    retry_at = Column(DateTime(timezone=True), nullable=True)
    dispatch_lease_until = Column(DateTime(timezone=True), nullable=True)
    worker_lease_until = Column(DateTime(timezone=True), nullable=True)
    worker_epoch = Column(Integer, nullable=False, default=0)
    worker_token = Column(UUID(as_uuid=True), nullable=True)

    started_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    repository: Mapped["UserRepository"] = relationship("UserRepository")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("worker_epoch", 0)
        super().__init__(**kwargs)

    __table_args__ = (
        Index(
            "idx_unique_active_sync_per_repo",
            "user_repository_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        Index(
            "idx_sync_jobs_queued_dispatch",
            "status",
            "retry_at",
            "dispatch_lease_until",
            postgresql_where=text("status = 'queued'"),
        ),
        Index(
            "idx_sync_jobs_running_lease",
            "status",
            "worker_lease_until",
            postgresql_where=text("status = 'running'"),
        ),
    )
