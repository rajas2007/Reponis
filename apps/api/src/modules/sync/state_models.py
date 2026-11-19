import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.modules.repositories.models import UserRepository


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RepositorySyncState(Base):
    __tablename__ = "repository_sync_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_repositories.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Commits state
    commits_head_sha = Column(String, nullable=True)
    commits_backfill_head_sha = Column(String, nullable=True)
    commits_backfill_next_page = Column(Integer, nullable=False, default=1)
    commits_backfill_status = Column(String, nullable=False, default="pending")
    commits_last_synced_at = Column(DateTime(timezone=True), nullable=True)

    # Compare API in-flight pagination
    compare_base_sha = Column(String, nullable=True)
    compare_head_sha = Column(String, nullable=True)
    compare_next_page = Column(Integer, nullable=False, default=1)

    # Compare API fallback (>1000 commits)
    commits_fallback_base_sha = Column(String, nullable=True)
    commits_fallback_head_sha = Column(String, nullable=True)
    commits_fallback_next_page = Column(Integer, nullable=False, default=1)
    commits_fallback_status = Column(String, nullable=False, default="inactive")

    # Pull requests state & closing sweep
    prs_last_updated_at = Column(DateTime(timezone=True), nullable=True)
    prs_backfill_started_at = Column(DateTime(timezone=True), nullable=True)
    prs_backfill_next_page = Column(Integer, nullable=False, default=1)
    prs_backfill_status = Column(String, nullable=False, default="pending")
    prs_closing_sweep_iteration = Column(Integer, nullable=False, default=0)
    prs_closing_sweep_next_page = Column(Integer, nullable=False, default=1)
    prs_closing_sweep_complete = Column(Boolean, nullable=False, default=False)

    # Issues state
    issues_last_updated_at = Column(DateTime(timezone=True), nullable=True)
    issues_backfill_next_page = Column(Integer, nullable=False, default=1)
    issues_backfill_status = Column(String, nullable=False, default="pending")

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    repository: Mapped["UserRepository"] = relationship(
        "UserRepository", back_populates="sync_state"
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("commits_backfill_next_page", 1)
        kwargs.setdefault("commits_backfill_status", "pending")
        kwargs.setdefault("compare_next_page", 1)
        kwargs.setdefault("commits_fallback_next_page", 1)
        kwargs.setdefault("commits_fallback_status", "inactive")
        kwargs.setdefault("prs_backfill_next_page", 1)
        kwargs.setdefault("prs_backfill_status", "pending")
        kwargs.setdefault("prs_closing_sweep_iteration", 0)
        kwargs.setdefault("prs_closing_sweep_next_page", 1)
        kwargs.setdefault("prs_closing_sweep_complete", False)
        kwargs.setdefault("issues_backfill_next_page", 1)
        kwargs.setdefault("issues_backfill_status", "pending")
        super().__init__(**kwargs)

    __table_args__ = (
        Index("uq_repo_sync_states_repo", "user_repository_id", unique=True),
    )
