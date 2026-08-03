import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.modules.users.models import User


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRepository(Base):
    __tablename__ = "user_repositories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    github_repo_id = Column(BigInteger, nullable=False)
    owner = Column(String, nullable=False)
    name = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    visibility = Column(String, nullable=False)
    description = Column(String, nullable=True)
    language = Column(String, nullable=True)
    html_url = Column(String, nullable=False)
    default_branch = Column(String, nullable=False)

    # Enums for sync_status: never_synced, syncing, completed, failed
    sync_status = Column(String, nullable=False, default="never_synced")

    is_active = Column(Boolean, nullable=False, default=True)
    connected_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    disconnected_at = Column(DateTime(timezone=True), nullable=True)
    
    # Incremental sync cursors
    last_commit_sha = Column(String, nullable=True)
    last_pr_updated_at = Column(DateTime(timezone=True), nullable=True)
    last_issue_updated_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="repositories")

    __table_args__ = (
        Index(
            "idx_unique_active_repo_per_user",
            "user_id",
            unique=True,
            postgresql_where=Column("is_active").is_(True),
        ),
    )
