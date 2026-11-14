"""create_sync_jobs_raw_and_weekly_metrics

Revision ID: 5bc6206f6784
Revises: 4ab5195f5673
Create Date: 2026-08-10 20:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5bc6206f6784"
down_revision: Union[str, None] = "4ab5195f5673"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. sync_status & triggered_by enums and sync_jobs table if not existing
    sync_status_enum = postgresql.ENUM(
        "queued",
        "running",
        "completed",
        "failed",
        "cancelled",
        name="sync_status",
        create_type=False,
    )
    sync_status_enum.create(op.get_bind(), checkfirst=True)

    triggered_by_enum = postgresql.ENUM(
        "manual", "scheduled", "webhook", name="triggered_by", create_type=False
    )
    triggered_by_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("user_repository_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued",
                "running",
                "completed",
                "failed",
                "cancelled",
                name="sync_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "triggered_by",
            postgresql.ENUM(
                "manual", "scheduled", "webhook", name="triggered_by", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("progress_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_repository_id"], ["user_repositories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sync_jobs_user_repository_id"), "sync_jobs", ["user_repository_id"], unique=False
    )
    op.create_index(
        "idx_unique_active_sync_per_repo",
        "sync_jobs",
        ["user_repository_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )

    # 2. raw tables: raw_commits, raw_pull_requests, raw_pull_request_reviews, raw_issues
    op.create_table(
        "raw_commits",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("user_repository_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("sha", sa.String(), nullable=False),
        sa.Column("author_name", sa.String(), nullable=True),
        sa.Column("author_email", sa.String(), nullable=True),
        sa.Column("authored_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_repository_id"], ["user_repositories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_raw_commits_user_repository_id"),
        "raw_commits",
        ["user_repository_id"],
        unique=False,
    )
    op.create_index(
        "idx_raw_commits_repo_sha", "raw_commits", ["user_repository_id", "sha"], unique=True
    )
    op.create_index(
        "idx_raw_commits_repo_authored_date",
        "raw_commits",
        ["user_repository_id", "authored_date"],
        unique=False,
    )

    op.create_table(
        "raw_pull_requests",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("user_repository_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("github_pr_id", sa.String(), nullable=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("author_login", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_repository_id"], ["user_repositories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_raw_pull_requests_user_repository_id"),
        "raw_pull_requests",
        ["user_repository_id"],
        unique=False,
    )
    op.create_index(
        "idx_raw_prs_repo_number",
        "raw_pull_requests",
        ["user_repository_id", "number"],
        unique=True,
    )
    op.create_index(
        "idx_raw_prs_repo_created_at",
        "raw_pull_requests",
        ["user_repository_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_raw_prs_repo_merged_at",
        "raw_pull_requests",
        ["user_repository_id", "merged_at"],
        unique=False,
    )
    op.create_index(
        "idx_raw_prs_repo_closed_at",
        "raw_pull_requests",
        ["user_repository_id", "closed_at"],
        unique=False,
    )

    op.create_table(
        "raw_pull_request_reviews",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("pull_request_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("github_review_id", sa.String(), nullable=True),
        sa.Column("user_login", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pull_request_id"], ["raw_pull_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_raw_pull_request_reviews_pull_request_id"),
        "raw_pull_request_reviews",
        ["pull_request_id"],
        unique=False,
    )
    op.create_index(
        "idx_raw_pr_reviews_pr_submitted",
        "raw_pull_request_reviews",
        ["pull_request_id", "submitted_at"],
        unique=False,
    )

    op.create_table(
        "raw_issues",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("user_repository_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("github_issue_id", sa.String(), nullable=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("is_bug", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_repository_id"], ["user_repositories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_raw_issues_user_repository_id"), "raw_issues", ["user_repository_id"], unique=False
    )
    op.create_index(
        "idx_raw_issues_repo_number", "raw_issues", ["user_repository_id", "number"], unique=True
    )
    op.create_index(
        "idx_raw_issues_repo_created_at",
        "raw_issues",
        ["user_repository_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_raw_issues_repo_closed_at",
        "raw_issues",
        ["user_repository_id", "closed_at"],
        unique=False,
    )

    # 3. weekly_metrics table
    op.create_table(
        "weekly_metrics",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("commit_count", sa.Integer(), nullable=True),
        sa.Column("commit_frequency_per_day", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("active_contributors", sa.Integer(), nullable=True),
        sa.Column("prs_opened", sa.Integer(), nullable=True),
        sa.Column("prs_merged", sa.Integer(), nullable=True),
        sa.Column("prs_closed_without_merge", sa.Integer(), nullable=True),
        sa.Column("pr_merge_rate", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("cycle_time_total_p50", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column(
            "cycle_time_to_first_review_p50", sa.Numeric(precision=10, scale=2), nullable=True
        ),
        sa.Column(
            "cycle_time_review_to_approval_p50", sa.Numeric(precision=10, scale=2), nullable=True
        ),
        sa.Column(
            "cycle_time_approval_to_merge_p50", sa.Numeric(precision=10, scale=2), nullable=True
        ),
        sa.Column("issues_opened", sa.Integer(), nullable=True),
        sa.Column("issues_closed", sa.Integer(), nullable=True),
        sa.Column("bugs_opened", sa.Integer(), nullable=True),
        sa.Column("bugs_closed", sa.Integer(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["user_repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_weekly_metrics_repository_id"), "weekly_metrics", ["repository_id"], unique=False
    )
    op.create_index(
        "idx_unique_repo_week_start", "weekly_metrics", ["repository_id", "week_start"], unique=True
    )


def downgrade() -> None:
    op.drop_index("idx_unique_repo_week_start", table_name="weekly_metrics")
    op.drop_index(op.f("ix_weekly_metrics_repository_id"), table_name="weekly_metrics")
    op.drop_table("weekly_metrics")

    op.drop_index("idx_raw_issues_repo_closed_at", table_name="raw_issues")
    op.drop_index("idx_raw_issues_repo_created_at", table_name="raw_issues")
    op.drop_index("idx_raw_issues_repo_number", table_name="raw_issues")
    op.drop_index(op.f("ix_raw_issues_user_repository_id"), table_name="raw_issues")
    op.drop_table("raw_issues")

    op.drop_index("idx_raw_pr_reviews_pr_submitted", table_name="raw_pull_request_reviews")
    op.drop_index(
        op.f("ix_raw_pull_request_reviews_pull_request_id"), table_name="raw_pull_request_reviews"
    )
    op.drop_table("raw_pull_request_reviews")

    op.drop_index("idx_raw_prs_repo_closed_at", table_name="raw_pull_requests")
    op.drop_index("idx_raw_prs_repo_merged_at", table_name="raw_pull_requests")
    op.drop_index("idx_raw_prs_repo_created_at", table_name="raw_pull_requests")
    op.drop_index("idx_raw_prs_repo_number", table_name="raw_pull_requests")
    op.drop_index(op.f("ix_raw_pull_requests_user_repository_id"), table_name="raw_pull_requests")
    op.drop_table("raw_pull_requests")

    op.drop_index("idx_raw_commits_repo_authored_date", table_name="raw_commits")
    op.drop_index("idx_raw_commits_repo_sha", table_name="raw_commits")
    op.drop_index(op.f("ix_raw_commits_user_repository_id"), table_name="raw_commits")
    op.drop_table("raw_commits")

    op.drop_index("idx_unique_active_sync_per_repo", table_name="sync_jobs")
    op.drop_index(op.f("ix_sync_jobs_user_repository_id"), table_name="sync_jobs")
    op.drop_table("sync_jobs")

    bind = op.get_bind()
    postgresql.ENUM(name="triggered_by").drop(bind, checkfirst=True)
    postgresql.ENUM(name="sync_status").drop(bind, checkfirst=True)
