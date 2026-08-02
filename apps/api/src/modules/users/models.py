import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.modules.repositories.models import UserRepository


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    github_connection: Mapped[Optional["GitHubConnection"]] = relationship(
        "GitHubConnection", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    repositories: Mapped[List["UserRepository"]] = relationship(
        "UserRepository", back_populates="user", cascade="all, delete-orphan"
    )


class GitHubConnection(Base):
    __tablename__ = "github_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    encrypted_access_token = Column(String, nullable=False)
    scopes = Column(String, nullable=True)
    token_type = Column(String, nullable=False, default="bearer")
    connected_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="github_connection")
