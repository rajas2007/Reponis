"""incremental_sync_and_reviews_v6_2

Revision ID: e5a1b2c3d4f5
Revises: 5bc6206f6784
Create Date: 2026-11-19 15:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a1b2c3d4f5"
down_revision: Union[str, None] = "5bc6206f6784"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update sync_jobs with fencing and scheduling columns
    op.add_column("sync_jobs", sa.Column("retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sync_jobs", sa.Column("dispatch_lease_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sync_jobs", sa.Column("worker_lease_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sync_jobs", sa.Column("worker_epoch", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sync_jobs", sa.Column("worker_token", postgresql.UUID(as_uuid=True), nullable=True))

    op.create_index(
        "idx_sync_jobs_queued_dispatch",
        "sync_jobs",
        ["status", "retry_at", "dispatch_lease_until"],
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(
        "idx_sync_jobs_running_lease",
        "sync_jobs",
        ["status", "worker_lease_until"],
        postgresql_where=sa.text("status = 'running'"),
    )

    # 2. Update raw_pull_requests with review synchronization checkpoints
    op.add_column(
        "raw_pull_requests",
        sa.Column("reviews_status", sa.String(), nullable=False, server_default="pending"),
    )
    op.add_column(
        "raw_pull_requests",
        sa.Column("reviews_next_page", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "raw_pull_requests",
        sa.Column("reviews_synced_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "idx_raw_prs_review_sweep_open",
        "raw_pull_requests",
        ["user_repository_id", "reviews_synced_at"],
        postgresql_where=sa.text("state = 'open'"),
    )
    op.create_index(
        "idx_raw_prs_review_sweep_merged",
        "raw_pull_requests",
        ["user_repository_id", "merged_at", "reviews_synced_at"],
        postgresql_where=sa.text("state = 'closed'"),
    )

    # 3. Update raw_pull_request_reviews with synthetic id tracking and unique constraint
    op.add_column(
        "raw_pull_request_reviews",
        sa.Column("is_synthetic_id", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # Pre-migration validation: assert no existing records collide with synthetic namespace
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM raw_pull_request_reviews
                WHERE github_review_id LIKE 'reponis:synth:%'
            ) THEN
                RAISE EXCEPTION 'Pre-migration check failed: existing records match synthetic prefix.';
            END IF;
        END $$;
    """)

    # Irreversible Deduplication: Keep latest submitted_at DESC, id DESC
    op.execute("""
        DELETE FROM raw_pull_request_reviews
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY pull_request_id, github_review_id
                           ORDER BY submitted_at DESC, id DESC
                       ) as rn
                FROM raw_pull_request_reviews
                WHERE github_review_id IS NOT NULL
            ) ranked
            WHERE ranked.rn > 1
        );
    """)

    # Collision-safe synthetic backfill
    op.execute("""
        UPDATE raw_pull_request_reviews
        SET github_review_id = 'reponis:synth:review:' || id::text,
            is_synthetic_id = TRUE
        WHERE github_review_id IS NULL;
    """)

    op.alter_column("raw_pull_request_reviews", "github_review_id", nullable=False)
    op.create_index(
        "uq_raw_pr_reviews_pr_github_review_id",
        "raw_pull_request_reviews",
        ["pull_request_id", "github_review_id"],
        unique=True,
    )

    # 4. Create repository_sync_states table
    op.create_table(
        "repository_sync_states",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commits_head_sha", sa.String(), nullable=True),
        sa.Column("commits_backfill_head_sha", sa.String(), nullable=True),
        sa.Column("commits_backfill_next_page", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "commits_backfill_status", sa.String(), nullable=False, server_default="pending"
        ),
        sa.Column("commits_last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("compare_base_sha", sa.String(), nullable=True),
        sa.Column("compare_head_sha", sa.String(), nullable=True),
        sa.Column("compare_next_page", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("commits_fallback_base_sha", sa.String(), nullable=True),
        sa.Column("commits_fallback_head_sha", sa.String(), nullable=True),
        sa.Column("commits_fallback_next_page", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "commits_fallback_status", sa.String(), nullable=False, server_default="inactive"
        ),
        sa.Column("prs_last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prs_backfill_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prs_backfill_next_page", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("prs_backfill_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column(
            "prs_closing_sweep_iteration", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "prs_closing_sweep_next_page", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column(
            "prs_closing_sweep_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("issues_last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issues_backfill_next_page", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "issues_backfill_status", sa.String(), nullable=False, server_default="pending"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "uq_repo_sync_states_repo",
        "repository_sync_states",
        ["user_repository_id"],
        unique=True,
    )


def downgrade() -> None:
    # 1. Drop repository_sync_states
    op.drop_index("uq_repo_sync_states_repo", table_name="repository_sync_states")
    op.drop_table("repository_sync_states")

    # 2. Revert raw_pull_request_reviews
    op.drop_index("uq_raw_pr_reviews_pr_github_review_id", table_name="raw_pull_request_reviews")
    op.alter_column("raw_pull_request_reviews", "github_review_id", nullable=True)
    op.execute("""
        UPDATE raw_pull_request_reviews
        SET github_review_id = NULL
        WHERE is_synthetic_id = TRUE;
    """)
    op.drop_column("raw_pull_request_reviews", "is_synthetic_id")

    # 3. Revert raw_pull_requests
    op.drop_index("idx_raw_prs_review_sweep_merged", table_name="raw_pull_requests")
    op.drop_index("idx_raw_prs_review_sweep_open", table_name="raw_pull_requests")
    op.drop_column("raw_pull_requests", "reviews_synced_at")
    op.drop_column("raw_pull_requests", "reviews_next_page")
    op.drop_column("raw_pull_requests", "reviews_status")

    # 4. Revert sync_jobs
    op.drop_index("idx_sync_jobs_running_lease", table_name="sync_jobs")
    op.drop_index("idx_sync_jobs_queued_dispatch", table_name="sync_jobs")
    op.drop_column("sync_jobs", "worker_token")
    op.drop_column("sync_jobs", "worker_epoch")
    op.drop_column("sync_jobs", "worker_lease_until")
    op.drop_column("sync_jobs", "dispatch_lease_until")
    op.drop_column("sync_jobs", "retry_at")
