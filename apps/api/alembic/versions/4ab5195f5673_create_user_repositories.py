"""create_user_repositories

Revision ID: 4ab5195f5673
Revises: 0bd2768cb6d6
Create Date: 2026-08-02 01:59:46.385795

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4ab5195f5673"
down_revision: Union[str, None] = "0bd2768cb6d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_repositories",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("github_repo_id", sa.BigInteger(), nullable=False),
        sa.Column("owner", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("visibility", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("html_url", sa.String(), nullable=False),
        sa.Column("default_branch", sa.String(), nullable=False),
        sa.Column("sync_status", sa.String(), nullable=False, server_default="never_synced"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_repositories_user_id"), "user_repositories", ["user_id"], unique=False
    )
    op.create_index(
        "idx_unique_active_repo_per_user",
        "user_repositories",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("idx_unique_active_repo_per_user", table_name="user_repositories")
    op.drop_index(op.f("ix_user_repositories_user_id"), table_name="user_repositories")
    op.drop_table("user_repositories")
