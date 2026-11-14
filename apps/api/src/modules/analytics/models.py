import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.modules.repositories.models import UserRepository


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WeeklyMetric(Base):
    __tablename__ = "weekly_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_start = Column(Date, nullable=False)

    commit_count = Column(Integer, nullable=True)
    commit_frequency_per_day = Column(Numeric(6, 2), nullable=True)
    active_contributors = Column(Integer, nullable=True)

    prs_opened = Column(Integer, nullable=True)
    prs_merged = Column(Integer, nullable=True)
    prs_closed_without_merge = Column(Integer, nullable=True)
    pr_merge_rate = Column(Numeric(5, 4), nullable=True)

    cycle_time_total_p50 = Column(Numeric(10, 2), nullable=True)
    cycle_time_to_first_review_p50 = Column(Numeric(10, 2), nullable=True)
    cycle_time_review_to_approval_p50 = Column(Numeric(10, 2), nullable=True)
    cycle_time_approval_to_merge_p50 = Column(Numeric(10, 2), nullable=True)

    issues_opened = Column(Integer, nullable=True)
    issues_closed = Column(Integer, nullable=True)
    bugs_opened = Column(Integer, nullable=True)
    bugs_closed = Column(Integer, nullable=True)

    computed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    repository: Mapped["UserRepository"] = relationship("UserRepository")

    __table_args__ = (
        Index("idx_unique_repo_week_start", "repository_id", "week_start", unique=True),
    )
