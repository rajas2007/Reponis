import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

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


class Commit(Base):
    __tablename__ = "raw_commits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sha = Column(String, nullable=False)
    author_name = Column(String, nullable=True)
    author_email = Column(String, nullable=True)
    authored_date = Column(DateTime(timezone=True), nullable=False)
    message = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    repository: Mapped["UserRepository"] = relationship("UserRepository")

    __table_args__ = (
        Index("idx_raw_commits_repo_sha", "user_repository_id", "sha", unique=True),
        Index("idx_raw_commits_repo_authored_date", "user_repository_id", "authored_date"),
    )


class PullRequest(Base):
    __tablename__ = "raw_pull_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    github_pr_id = Column(String, nullable=True)
    number = Column(Integer, nullable=False)
    title = Column(String, nullable=True)
    state = Column(String, nullable=False)  # open, closed, merged
    author_login = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    merged_at = Column(DateTime(timezone=True), nullable=True)

    repository: Mapped["UserRepository"] = relationship("UserRepository")
    reviews: Mapped[list["PullRequestReview"]] = relationship(
        "PullRequestReview", back_populates="pull_request", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_raw_prs_repo_number", "user_repository_id", "number", unique=True),
        Index("idx_raw_prs_repo_created_at", "user_repository_id", "created_at"),
        Index("idx_raw_prs_repo_merged_at", "user_repository_id", "merged_at"),
        Index("idx_raw_prs_repo_closed_at", "user_repository_id", "closed_at"),
    )


class PullRequestReview(Base):
    __tablename__ = "raw_pull_request_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pull_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("raw_pull_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    github_review_id = Column(String, nullable=True)
    user_login = Column(String, nullable=True)
    state = Column(String, nullable=False)  # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED
    submitted_at = Column(DateTime(timezone=True), nullable=False)

    pull_request: Mapped["PullRequest"] = relationship("PullRequest", back_populates="reviews")

    __table_args__ = (Index("idx_raw_pr_reviews_pr_submitted", "pull_request_id", "submitted_at"),)


class Issue(Base):
    __tablename__ = "raw_issues"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    github_issue_id = Column(String, nullable=True)
    number = Column(Integer, nullable=False)
    title = Column(String, nullable=True)
    state = Column(String, nullable=False)  # open, closed
    is_bug = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    repository: Mapped["UserRepository"] = relationship("UserRepository")

    __table_args__ = (
        Index("idx_raw_issues_repo_number", "user_repository_id", "number", unique=True),
        Index("idx_raw_issues_repo_created_at", "user_repository_id", "created_at"),
        Index("idx_raw_issues_repo_closed_at", "user_repository_id", "closed_at"),
    )
