import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.repositories.models import UserRepository
from src.modules.sync.models import SyncJob, SyncStatus, TriggeredBy
from src.modules.sync.tasks.sync_repository import _run_sync


@pytest.mark.asyncio
async def test_sync_repository_ingestion_pipeline():
    job_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    user_id = uuid.uuid4()

    job = SyncJob(
        id=job_id,
        user_repository_id=repo_id,
        status=SyncStatus.QUEUED,
        triggered_by=TriggeredBy.MANUAL,
        progress_data={},
    )
    repo = UserRepository(
        id=repo_id,
        user_id=user_id,
        github_repo_id=999,
        owner="octocat",
        name="Hello-World",
        full_name="octocat/Hello-World",
        visibility="public",
        html_url="https://github.com/octocat/Hello-World",
        default_branch="main",
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.get.return_value = repo

    # Mock user github connection
    mock_conn = MagicMock()
    mock_conn.encrypted_access_token = "encrypted_token_123"

    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = mock_conn
    mock_execute_res.scalar_one.return_value = uuid.uuid4()
    mock_session.execute.return_value = mock_execute_res

    # Mock raw GitHub data
    sample_commits = [
        {
            "sha": "c1a2b3",
            "commit": {
                "author": {
                    "name": "Mona Lisa",
                    "email": "mona@github.com",
                    "date": "2026-08-11T12:00:00Z",
                },
                "message": "feat: initial commit",
            },
        }
    ]

    sample_prs = [
        {
            "id": 1001,
            "number": 42,
            "title": "Add analytics",
            "state": "closed",
            "user": {"login": "monalisa"},
            "created_at": "2026-08-10T10:00:00Z",
            "updated_at": "2026-08-11T15:00:00Z",
            "closed_at": "2026-08-11T15:00:00Z",
            "merged_at": "2026-08-11T15:00:00Z",
        }
    ]

    sample_reviews = [
        {
            "id": 501,
            "user": {"login": "reviewer1"},
            "state": "APPROVED",
            "submitted_at": "2026-08-11T14:00:00Z",
        }
    ]

    sample_issues = [
        # Normal issue
        {
            "id": 2001,
            "number": 1,
            "title": "Documentation improvement",
            "state": "closed",
            "labels": [{"name": "documentation"}],
            "created_at": "2026-08-10T09:00:00Z",
            "updated_at": "2026-08-10T11:00:00Z",
            "closed_at": "2026-08-10T11:00:00Z",
        },
        # Bug issue
        {
            "id": 2002,
            "number": 2,
            "title": "Calculation crash bug",
            "state": "open",
            "labels": [{"name": "bug"}, {"name": "priority"}],
            "created_at": "2026-08-12T08:00:00Z",
            "updated_at": "2026-08-12T08:00:00Z",
            "closed_at": None,
        },
        # Pull request masquerading as issue in GitHub API (should be ignored)
        {
            "id": 2003,
            "number": 42,
            "title": "Add analytics",
            "pull_request": {"url": "https://api.github.com/..."},
        },
    ]

    with patch("src.modules.sync.tasks.sync_repository.AsyncSessionLocal") as mock_sess_cls:
        mock_sess_cls.return_value.__aenter__.return_value = mock_session
        with patch(
            "src.modules.sync.tasks.sync_repository.SyncJobRepository.get_by_id", return_value=job
        ):
            with patch(
                "src.modules.sync.tasks.sync_repository.decrypt", return_value="decrypted_gh_token"
            ):
                with patch(
                    "src.modules.sync.tasks.sync_repository.fetch_repository_commits",
                    return_value=sample_commits,
                ) as mock_fetch_commits:
                    with patch(
                        "src.modules.sync.tasks.sync_repository.fetch_repository_pull_requests",
                        return_value=sample_prs,
                    ) as mock_fetch_prs:
                        with patch(
                            "src.modules.sync.tasks.sync_repository.fetch_pull_request_reviews",
                            return_value=sample_reviews,
                        ) as mock_fetch_reviews:
                            with patch(
                                "src.modules.sync.tasks.sync_repository.fetch_repository_issues",
                                return_value=sample_issues,
                            ) as mock_fetch_issues:
                                with patch(
                                    "src.modules.analytics.tasks.compute_metrics.compute_repository_metrics_task.delay"
                                ) as mock_delay:
                                    await _run_sync(job_id)

                                    # Verify GitHub clients were called with expected parameters
                                    mock_fetch_commits.assert_called_once_with(
                                        token="decrypted_gh_token",
                                        full_name="octocat/Hello-World",
                                        page=1,
                                        per_page=100,
                                    )
                                    mock_fetch_prs.assert_called_once_with(
                                        token="decrypted_gh_token",
                                        full_name="octocat/Hello-World",
                                        page=1,
                                        per_page=100,
                                    )
                                    mock_fetch_reviews.assert_called_once_with(
                                        token="decrypted_gh_token",
                                        full_name="octocat/Hello-World",
                                        pull_number=42,
                                    )
                                    mock_fetch_issues.assert_called_once_with(
                                        token="decrypted_gh_token",
                                        full_name="octocat/Hello-World",
                                        page=1,
                                        per_page=100,
                                    )

                                    # Verify sync status & progress data
                                    assert job.status == SyncStatus.COMPLETED
                                    assert job.progress_data["commits"] == 1
                                    assert job.progress_data["pull_requests"] == 1
                                    assert job.progress_data["issues"] == 2  # PR in issues ignored

                                    # Verify downstream analytics task triggered
                                    mock_delay.assert_called_once_with(str(repo_id))


@pytest.mark.asyncio
async def test_sync_repository_failure_handling():
    job_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    user_id = uuid.uuid4()

    job = SyncJob(
        id=job_id,
        user_repository_id=repo_id,
        status=SyncStatus.QUEUED,
        triggered_by=TriggeredBy.MANUAL,
        progress_data={},
    )
    repo = UserRepository(
        id=repo_id,
        user_id=user_id,
        github_repo_id=999,
        owner="octocat",
        name="Hello-World",
        full_name="octocat/Hello-World",
        visibility="public",
        html_url="https://github.com/octocat/Hello-World",
        default_branch="main",
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.get.return_value = repo

    mock_conn = MagicMock()
    mock_conn.encrypted_access_token = "encrypted_token_123"
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = mock_conn
    mock_session.execute.return_value = mock_execute_res

    with patch("src.modules.sync.tasks.sync_repository.AsyncSessionLocal") as mock_sess_cls:
        mock_sess_cls.return_value.__aenter__.return_value = mock_session
        with patch(
            "src.modules.sync.tasks.sync_repository.SyncJobRepository.get_by_id", return_value=job
        ):
            with patch("src.modules.sync.tasks.sync_repository.decrypt", return_value="token"):
                # Simulate GitHub API network or auth failure
                with patch(
                    "src.modules.sync.tasks.sync_repository.fetch_repository_commits",
                    side_effect=Exception("GitHub 503 Service Unavailable"),
                ):
                    with patch(
                        "src.modules.analytics.tasks.compute_metrics.compute_repository_metrics_task.delay"
                    ) as mock_delay:
                        await _run_sync(job_id)

                        # Sync must fail gracefully and not trigger analytics
                        assert job.status == SyncStatus.FAILED
                        assert "GitHub 503 Service Unavailable" in (job.error_message or "")
                        mock_delay.assert_not_called()
