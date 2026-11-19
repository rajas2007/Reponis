import uuid
from datetime import datetime, timezone

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

import src.modules.analytics.models  # noqa: F401
import src.modules.users.models  # noqa: F401
from src.core.database import Base
from src.modules.repositories.models import UserRepository
from src.modules.sync.models import SyncJob, SyncStatus, TriggeredBy
from src.modules.sync.raw_models import PullRequest, PullRequestReview
from src.modules.sync.state_models import RepositorySyncState


def test_sync_job_fencing_fields_and_defaults() -> None:
    job_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    job = SyncJob(
        id=job_id,
        user_repository_id=repo_id,
        status=SyncStatus.QUEUED,
        triggered_by=TriggeredBy.MANUAL,
    )

    # Verify defaults
    assert job.worker_epoch == 0
    assert job.retry_at is None
    assert job.dispatch_lease_until is None
    assert job.worker_lease_until is None
    assert job.worker_token is None

    # Verify table indexes
    index_names = {idx.name for idx in SyncJob.__table__.indexes}
    assert "idx_unique_active_sync_per_repo" in index_names
    assert "idx_sync_jobs_queued_dispatch" in index_names
    assert "idx_sync_jobs_running_lease" in index_names

    # Verify columns exist on the table
    column_names = {c.name for c in SyncJob.__table__.columns}
    assert "retry_at" in column_names
    assert "dispatch_lease_until" in column_names
    assert "worker_lease_until" in column_names
    assert "worker_epoch" in column_names
    assert "worker_token" in column_names


def test_raw_pull_requests_checkpoint_fields_and_indexes() -> None:
    pr = PullRequest(
        user_repository_id=uuid.uuid4(),
        number=42,
        state="open",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Verify defaults
    assert pr.reviews_status == "pending"
    assert pr.reviews_next_page == 1
    assert pr.reviews_synced_at is None

    # Verify table indexes
    index_names = {idx.name for idx in PullRequest.__table__.indexes}
    assert "idx_raw_prs_review_sweep_open" in index_names
    assert "idx_raw_prs_review_sweep_merged" in index_names

    column_names = {c.name for c in PullRequest.__table__.columns}
    assert "reviews_status" in column_names
    assert "reviews_next_page" in column_names
    assert "reviews_synced_at" in column_names


def test_raw_pull_request_reviews_synthetic_id_and_constraints() -> None:
    review = PullRequestReview(
        pull_request_id=uuid.uuid4(),
        github_review_id="123456",
        state="APPROVED",
        submitted_at=datetime.now(timezone.utc),
    )

    # Verify defaults
    assert review.is_synthetic_id is False

    # Verify unique index
    indexes = {str(idx.name): idx for idx in PullRequestReview.__table__.indexes}
    assert "uq_raw_pr_reviews_pr_github_review_id" in indexes
    uq_index = indexes["uq_raw_pr_reviews_pr_github_review_id"]
    assert uq_index.unique is True
    cols = [col.name for col in uq_index.columns]
    assert "pull_request_id" in cols
    assert "github_review_id" in cols

    column_names = {c.name for c in PullRequestReview.__table__.columns}
    assert "is_synthetic_id" in column_names
    assert "github_review_id" in column_names


def test_repository_sync_state_defaults_and_indexes() -> None:
    repo_id = uuid.uuid4()
    state = RepositorySyncState(user_repository_id=repo_id)

    # Check commit defaults
    assert state.commits_head_sha is None
    assert state.commits_backfill_head_sha is None
    assert state.commits_backfill_next_page == 1
    assert state.commits_backfill_status == "pending"
    assert state.commits_last_synced_at is None

    # Check compare API defaults
    assert state.compare_base_sha is None
    assert state.compare_head_sha is None
    assert state.compare_next_page == 1

    # Check fallback defaults
    assert state.commits_fallback_base_sha is None
    assert state.commits_fallback_head_sha is None
    assert state.commits_fallback_next_page == 1
    assert state.commits_fallback_status == "inactive"

    # Check PR defaults
    assert state.prs_last_updated_at is None
    assert state.prs_backfill_started_at is None
    assert state.prs_backfill_next_page == 1
    assert state.prs_backfill_status == "pending"
    assert state.prs_closing_sweep_iteration == 0
    assert state.prs_closing_sweep_next_page == 1
    assert state.prs_closing_sweep_complete is False

    # Check issues defaults
    assert state.issues_last_updated_at is None
    assert state.issues_backfill_next_page == 1
    assert state.issues_backfill_status == "pending"

    # Verify index
    indexes = {str(idx.name): idx for idx in RepositorySyncState.__table__.indexes}
    assert "uq_repo_sync_states_repo" in indexes
    assert indexes["uq_repo_sync_states_repo"].unique is True


def test_model_relationships() -> None:
    repo_id = uuid.uuid4()
    repo = UserRepository(
        id=repo_id,  # type: ignore[arg-type]
        user_id=uuid.uuid4(),  # type: ignore[arg-type]
        github_repo_id=123,
        owner="owner",
        name="repo",
        full_name="owner/repo",
        visibility="public",
        html_url="https://github.com/owner/repo",
        default_branch="main",
    )
    state = RepositorySyncState(user_repository_id=repo.id)
    repo.sync_state = state

    assert repo.sync_state == state
    assert state.repository == repo

    pr = PullRequest(
        id=uuid.uuid4(),
        user_repository_id=repo.id,
        number=1,
        state="open",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    rev = PullRequestReview(
        id=uuid.uuid4(),
        pull_request_id=pr.id,
        github_review_id="999",
        state="APPROVED",
        submitted_at=datetime.now(timezone.utc),
    )
    pr.reviews.append(rev)

    assert len(pr.reviews) == 1
    assert rev.pull_request == pr


def test_alembic_revision_chain() -> None:
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)

    # The head should be e5a1b2c3d4f5
    heads = script.get_heads()
    assert heads == ["e5a1b2c3d4f5"]

    rev = script.get_revision("e5a1b2c3d4f5")
    assert rev is not None
    assert rev.down_revision == "5bc6206f6784"


def test_all_tables_in_base_metadata() -> None:
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "users",
        "github_connections",
        "user_repositories",
        "sync_jobs",
        "repository_sync_states",
        "raw_commits",
        "raw_pull_requests",
        "raw_pull_request_reviews",
        "raw_issues",
        "weekly_metrics",
    }
    assert expected.issubset(table_names)


def test_alembic_offline_upgrade_and_downgrade_sql(capsys: pytest.CaptureFixture[str]) -> None:
    from alembic import command

    alembic_cfg = Config("alembic.ini")

    # Capture upgrade SQL
    command.upgrade(alembic_cfg, "5bc6206f6784:e5a1b2c3d4f5", sql=True)
    captured = capsys.readouterr()
    sql_upgrade = captured.out

    # Verify upgrade SQL components
    assert "ALTER TABLE sync_jobs ADD COLUMN retry_at" in sql_upgrade
    assert "ALTER TABLE sync_jobs ADD COLUMN dispatch_lease_until" in sql_upgrade
    assert "ALTER TABLE sync_jobs ADD COLUMN worker_lease_until" in sql_upgrade
    assert "ALTER TABLE sync_jobs ADD COLUMN worker_epoch" in sql_upgrade
    assert "ALTER TABLE sync_jobs ADD COLUMN worker_token" in sql_upgrade
    assert "CREATE INDEX idx_sync_jobs_queued_dispatch" in sql_upgrade
    assert "CREATE INDEX idx_sync_jobs_running_lease" in sql_upgrade

    assert "ALTER TABLE raw_pull_requests ADD COLUMN reviews_status" in sql_upgrade
    assert "ALTER TABLE raw_pull_requests ADD COLUMN reviews_next_page" in sql_upgrade
    assert "ALTER TABLE raw_pull_requests ADD COLUMN reviews_synced_at" in sql_upgrade
    assert "CREATE INDEX idx_raw_prs_review_sweep_open" in sql_upgrade
    assert "CREATE INDEX idx_raw_prs_review_sweep_merged" in sql_upgrade

    assert "ALTER TABLE raw_pull_request_reviews ADD COLUMN is_synthetic_id" in sql_upgrade
    assert "reponis:synth:%" in sql_upgrade
    assert "reponis:synth:review:" in sql_upgrade
    assert "ALTER TABLE raw_pull_request_reviews ALTER COLUMN github_review_id SET NOT NULL" in sql_upgrade
    assert "CREATE UNIQUE INDEX uq_raw_pr_reviews_pr_github_review_id" in sql_upgrade

    assert "CREATE TABLE repository_sync_states" in sql_upgrade
    assert "CREATE UNIQUE INDEX uq_repo_sync_states_repo" in sql_upgrade
    assert "UPDATE alembic_version SET version_num='e5a1b2c3d4f5'" in sql_upgrade

    # Capture downgrade SQL
    command.downgrade(alembic_cfg, "e5a1b2c3d4f5:5bc6206f6784", sql=True)
    captured = capsys.readouterr()
    sql_downgrade = captured.out

    # Verify downgrade SQL components
    assert "DROP TABLE repository_sync_states" in sql_downgrade
    assert "DROP INDEX uq_repo_sync_states_repo" in sql_downgrade
    assert "DROP INDEX uq_raw_pr_reviews_pr_github_review_id" in sql_downgrade
    assert "ALTER TABLE raw_pull_request_reviews ALTER COLUMN github_review_id DROP NOT NULL" in sql_downgrade
    assert "UPDATE raw_pull_request_reviews" in sql_downgrade
    assert "WHERE is_synthetic_id = TRUE" in sql_downgrade
    assert "ALTER TABLE raw_pull_request_reviews DROP COLUMN is_synthetic_id" in sql_downgrade
    assert "DROP INDEX idx_raw_prs_review_sweep_merged" in sql_downgrade
    assert "DROP INDEX idx_raw_prs_review_sweep_open" in sql_downgrade
    assert "ALTER TABLE raw_pull_requests DROP COLUMN reviews_synced_at" in sql_downgrade
    assert "ALTER TABLE raw_pull_requests DROP COLUMN reviews_next_page" in sql_downgrade
    assert "ALTER TABLE raw_pull_requests DROP COLUMN reviews_status" in sql_downgrade
    assert "DROP INDEX idx_sync_jobs_running_lease" in sql_downgrade
    assert "DROP INDEX idx_sync_jobs_queued_dispatch" in sql_downgrade
    assert "ALTER TABLE sync_jobs DROP COLUMN worker_token" in sql_downgrade
    assert "ALTER TABLE sync_jobs DROP COLUMN worker_epoch" in sql_downgrade
    assert "ALTER TABLE sync_jobs DROP COLUMN worker_lease_until" in sql_downgrade
    assert "ALTER TABLE sync_jobs DROP COLUMN dispatch_lease_until" in sql_downgrade
    assert "ALTER TABLE sync_jobs DROP COLUMN retry_at" in sql_downgrade
    assert "UPDATE alembic_version SET version_num='5bc6206f6784'" in sql_downgrade
