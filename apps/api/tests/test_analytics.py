import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.modules.analytics.models import WeeklyMetric
from src.modules.analytics.service import (
    _calc_p50,
    compute_repository_metrics,
)
from src.modules.analytics.utils import get_week_start
from src.modules.repositories.models import UserRepository
from src.modules.sync.models import SyncJob, SyncStatus, TriggeredBy
from src.modules.sync.raw_models import Commit, Issue, PullRequest, PullRequestReview
from src.modules.sync.tasks.sync_repository import _run_sync
from src.modules.users.models import User


def test_calc_p50():
    assert _calc_p50([]) is None
    assert _calc_p50([10.0]) == Decimal("10.00")
    assert _calc_p50([10.0, 20.0]) == Decimal("15.00")
    assert _calc_p50([5.0, 15.0, 20.0]) == Decimal("15.00")


def test_celery_task_registration():
    """Verify Celery tasks are automatically discoverable via the include configuration."""
    from src.core.celery import celery_app

    # Worker initialization or loader import triggers include modules
    celery_app.loader.import_default_modules()
    registered = list(celery_app.tasks.keys())
    assert "sync_repository_task" in registered
    assert "compute_repository_metrics_task" in registered


@pytest.mark.asyncio
async def test_compute_repository_metrics_fixtures():
    """
    Tests Fixtures 1, 2, 3, 4, 5 from TDD.
    """
    repo_id = uuid.uuid4()
    now = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    current_ws = get_week_start(now)  # 2026-08-17 (Monday)
    prev_ws = get_week_start(
        datetime(2026, 8, 10, 10, 0, 0, tzinfo=timezone.utc)
    )  # 2026-08-10 (Monday)

    # Fixture 1: Zero-PR Week (prev_ws has 10 commits, 0 PRs)
    commits: list[Commit] = [
        Commit(
            id=uuid.uuid4(),
            user_repository_id=repo_id,
            sha=f"sha_{i}",
            author_name=f"dev_{i % 3}",
            authored_date=datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc),
        )
        for i in range(10)
    ]

    # Fixture 2: PR with no review events merged in current_ws
    # Created 2026-08-17 01:00, merged 2026-08-17 05:00 (cycle time 4 hours)
    pr_no_review = PullRequest(
        id=uuid.uuid4(),
        user_repository_id=repo_id,
        number=101,
        state="closed",
        created_at=datetime(2026, 8, 17, 1, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 17, 5, 0, 0, tzinfo=timezone.utc),
        merged_at=datetime(2026, 8, 17, 5, 0, 0, tzinfo=timezone.utc),
        closed_at=datetime(2026, 8, 17, 5, 0, 0, tzinfo=timezone.utc),
    )
    pr_no_review.reviews = []

    # Fixture 3: PR Boundary (Opened Week N, Merged Week N+1)
    # Opened Sunday 23:59 (in prev_ws: 2026-08-16 23:59), merged Monday 01:00 (in current_ws: 2026-08-17 01:00)
    pr_boundary = PullRequest(
        id=uuid.uuid4(),
        user_repository_id=repo_id,
        number=102,
        state="closed",
        created_at=datetime(2026, 8, 16, 23, 59, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 17, 1, 0, 0, tzinfo=timezone.utc),
        merged_at=datetime(2026, 8, 17, 1, 0, 0, tzinfo=timezone.utc),
        closed_at=datetime(2026, 8, 17, 1, 0, 0, tzinfo=timezone.utc),
    )
    pr_boundary.reviews = []

    # Closed without merge PR in current_ws
    pr_closed_unmerged = PullRequest(
        id=uuid.uuid4(),
        user_repository_id=repo_id,
        number=103,
        state="closed",
        created_at=datetime(2026, 8, 17, 2, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 17, 3, 0, 0, tzinfo=timezone.utc),
        merged_at=None,
        closed_at=datetime(2026, 8, 17, 3, 0, 0, tzinfo=timezone.utc),
    )
    pr_closed_unmerged.reviews = []

    # Merged PR with reviews and approval in current_ws
    # Created 2026-08-17 00:00, reviewed 2026-08-17 02:00, approved 2026-08-17 06:00, merged 2026-08-17 08:00
    # time_to_first_review = 2h, review_to_approval = 4h, approval_to_merge = 2h, total_cycle = 8h
    pr_with_reviews = PullRequest(
        id=uuid.uuid4(),
        user_repository_id=repo_id,
        number=104,
        state="closed",
        created_at=datetime(2026, 8, 17, 0, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 17, 8, 0, 0, tzinfo=timezone.utc),
        merged_at=datetime(2026, 8, 17, 8, 0, 0, tzinfo=timezone.utc),
        closed_at=datetime(2026, 8, 17, 8, 0, 0, tzinfo=timezone.utc),
    )
    r1 = PullRequestReview(
        id=uuid.uuid4(),
        pull_request_id=pr_with_reviews.id,
        state="COMMENTED",
        submitted_at=datetime(2026, 8, 17, 2, 0, 0, tzinfo=timezone.utc),
    )
    r2 = PullRequestReview(
        id=uuid.uuid4(),
        pull_request_id=pr_with_reviews.id,
        state="APPROVED",
        submitted_at=datetime(2026, 8, 17, 6, 0, 0, tzinfo=timezone.utc),
    )
    pr_with_reviews.reviews = [r1, r2]

    # Merged PR with review but NEVER APPROVED in current_ws
    # Created 2026-08-17 00:00, reviewed 2026-08-17 04:00, merged 2026-08-17 10:00
    # Included in time_to_first_review (4h) and total_cycle (10h), excluded from review_to_approval and approval_to_merge
    pr_never_approved = PullRequest(
        id=uuid.uuid4(),
        user_repository_id=repo_id,
        number=105,
        state="closed",
        created_at=datetime(2026, 8, 17, 0, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc),
        merged_at=datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc),
        closed_at=datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc),
    )
    r_comment = PullRequestReview(
        id=uuid.uuid4(),
        pull_request_id=pr_never_approved.id,
        state="CHANGES_REQUESTED",
        submitted_at=datetime(2026, 8, 17, 4, 0, 0, tzinfo=timezone.utc),
    )
    pr_never_approved.reviews = [r_comment]

    # Fixture 5: Bug vs Non-bug Issue Classification in current_ws
    issue_bug = Issue(
        id=uuid.uuid4(),
        user_repository_id=repo_id,
        number=1,
        state="closed",
        is_bug=True,
        created_at=datetime(2026, 8, 17, 1, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 17, 2, 0, 0, tzinfo=timezone.utc),
        closed_at=datetime(2026, 8, 17, 2, 0, 0, tzinfo=timezone.utc),
    )
    issue_non_bug = Issue(
        id=uuid.uuid4(),
        user_repository_id=repo_id,
        number=2,
        state="closed",
        is_bug=False,
        created_at=datetime(2026, 8, 17, 3, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 17, 4, 0, 0, tzinfo=timezone.utc),
        closed_at=datetime(2026, 8, 17, 4, 0, 0, tzinfo=timezone.utc),
    )

    all_prs = [pr_no_review, pr_boundary, pr_closed_unmerged, pr_with_reviews, pr_never_approved]
    all_issues = [issue_bug, issue_non_bug]

    mock_session = AsyncMock()

    # Mock execute results based on query model
    async def mock_execute(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "raw_commits" in stmt_str:
            mock_result.scalars.return_value.all.return_value = commits
        elif "raw_pull_requests" in stmt_str:
            mock_result.scalars.return_value.all.return_value = all_prs
        elif "raw_issues" in stmt_str:
            mock_result.scalars.return_value.all.return_value = all_issues
        else:
            mock_result.scalars.return_value.all.return_value = []
        return mock_result

    mock_session.execute.side_effect = mock_execute

    upserted_metrics = []

    with patch(
        "src.modules.analytics.service.AnalyticsRepository.upsert_weekly_metrics",
        new_callable=AsyncMock,
    ) as mock_upsert:

        async def capture_upsert(metrics_data):
            nonlocal upserted_metrics
            upserted_metrics = list(metrics_data)

        mock_upsert.side_effect = capture_upsert

        await compute_repository_metrics(mock_session, repo_id, now=now)

    # Exactly 52 weeks computed
    assert len(upserted_metrics) == 52

    # Latest bucket is the current week
    assert upserted_metrics[-1]["week_start"] == current_ws
    # Earliest bucket is 51 weeks prior
    assert upserted_metrics[0]["week_start"] == current_ws - timedelta(weeks=51)

    # Inspect Fixture 1: Zero-PR Week (prev_ws: 2026-08-10)
    w_prev = next(m for m in upserted_metrics if m["week_start"] == prev_ws)
    assert w_prev["commit_count"] == 10
    assert w_prev["commit_frequency_per_day"] == Decimal("1.43")
    assert w_prev["active_contributors"] == 3
    # Fixture 3 check on prev_ws: PR boundary opened Sunday 23:59 of this week
    assert w_prev["prs_opened"] == 1
    assert w_prev["prs_merged"] == 0
    assert w_prev["prs_closed_without_merge"] == 0
    assert w_prev["pr_merge_rate"] is None
    assert w_prev["cycle_time_total_p50"] is None
    assert w_prev["cycle_time_to_first_review_p50"] is None
    assert w_prev["cycle_time_review_to_approval_p50"] is None
    assert w_prev["cycle_time_approval_to_merge_p50"] is None

    # Inspect Fixture 2, 3, 5 in current_ws: 2026-08-17
    w_curr = next(m for m in upserted_metrics if m["week_start"] == current_ws)
    assert w_curr["prs_opened"] == 4
    assert w_curr["prs_merged"] == 4
    assert w_curr["prs_closed_without_merge"] == 1
    assert w_curr["pr_merge_rate"] == Decimal("0.8000")

    # Cycle times for current_ws:
    # 1. pr_no_review: total = 4h
    # 2. pr_boundary: total = (1h + 1min) ~ 1.02h
    # 3. pr_with_reviews: total = 8h, first_rev = 2h, rev_to_app = 4h, app_to_merge = 2h
    # 4. pr_never_approved: total = 10h, first_rev = 4h
    # Total cycle times: [4.0, 1.0167, 8.0, 10.0] -> sorted: [1.02, 4.0, 8.0, 10.0] -> median: (4 + 8) / 2 = 6.0h
    assert w_curr["cycle_time_total_p50"] in (Decimal("6.01"), Decimal("6.00"))
    # time_to_first_review: [2.0, 4.0] -> median: 3.0h
    assert w_curr["cycle_time_to_first_review_p50"] == Decimal("3.00")
    # review_to_approval: [4.0] -> median: 4.0h
    assert w_curr["cycle_time_review_to_approval_p50"] == Decimal("4.00")
    # approval_to_merge: [2.0] -> median: 2.0h
    assert w_curr["cycle_time_approval_to_merge_p50"] == Decimal("2.00")

    # Fixture 5 check:
    assert w_curr["issues_opened"] == 2
    assert w_curr["issues_closed"] == 2
    assert w_curr["bugs_opened"] == 1
    assert w_curr["bugs_closed"] == 1

    # Empty week check
    w_empty = upserted_metrics[0]
    assert w_empty["commit_count"] == 0
    assert w_empty["prs_opened"] == 0
    assert w_empty["prs_merged"] == 0
    assert w_empty["pr_merge_rate"] is None
    assert w_empty["cycle_time_total_p50"] is None
    assert w_empty["issues_opened"] == 0
    assert w_empty["bugs_opened"] == 0


@pytest.mark.asyncio
async def test_analytics_api():
    repo_id = uuid.uuid4()
    user_id = uuid.uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    repo = UserRepository(
        id=repo_id,
        user_id=user_id,
        github_repo_id=12345,
        owner="testuser",
        name="testrepo",
        full_name="testuser/testrepo",
        visibility="public",
        html_url="https://github.com/testuser/testrepo",
        default_branch="main",
    )

    mock_db = AsyncMock()

    from src.core.database import get_db
    from src.modules.auth.dependencies import get_current_user_from_cookie

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user_from_cookie] = lambda: user

    # 1. Repo not found
    with patch(
        "src.modules.repositories.repository.RepositoriesRepository.get_by_id", return_value=None
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/v1/analytics/repositories/{repo_id}/weekly")
            assert resp.status_code == 404

    # 2. Forbidden (repo belongs to different user)
    other_repo = UserRepository(
        id=repo_id,
        user_id=uuid.uuid4(),
        github_repo_id=12345,
        owner="other",
        name="otherrepo",
        full_name="other/otherrepo",
        visibility="public",
        html_url="https://github.com/other/otherrepo",
        default_branch="main",
    )
    with patch(
        "src.modules.repositories.repository.RepositoriesRepository.get_by_id",
        return_value=other_repo,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/v1/analytics/repositories/{repo_id}/weekly")
            assert resp.status_code == 403

    # 3. Successful fetch with empty or populated metrics
    sample_metric = WeeklyMetric(
        id=uuid.uuid4(),
        repository_id=repo_id,
        week_start=date(2026, 8, 10),
        commit_count=15,
        commit_frequency_per_day=Decimal("2.14"),
        active_contributors=2,
        prs_opened=3,
        prs_merged=2,
        prs_closed_without_merge=1,
        pr_merge_rate=Decimal("0.6667"),
        cycle_time_total_p50=Decimal("12.50"),
        cycle_time_to_first_review_p50=Decimal("2.00"),
        cycle_time_review_to_approval_p50=Decimal("4.50"),
        cycle_time_approval_to_merge_p50=Decimal("6.00"),
        issues_opened=5,
        issues_closed=4,
        bugs_opened=1,
        bugs_closed=1,
        computed_at=datetime(2026, 8, 10, 14, 0, 0, tzinfo=timezone.utc),
    )
    with patch(
        "src.modules.repositories.repository.RepositoriesRepository.get_by_id", return_value=repo
    ):
        with patch(
            "src.modules.analytics.repository.AnalyticsRepository.get_weekly_metrics",
            return_value=[sample_metric],
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(f"/api/v1/analytics/repositories/{repo_id}/weekly")
                assert resp.status_code == 200
                data = resp.json()
                assert data["repository_id"] == str(repo_id)
                assert len(data["metrics"]) == 1
                assert data["metrics"][0]["commit_count"] == 15
                assert data["metrics"][0]["cycle_time_total_p50"] == 12.50

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_completion_triggers_analytics():
    job_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    job = SyncJob(
        id=job_id,
        user_repository_id=repo_id,
        status=SyncStatus.QUEUED,
        triggered_by=TriggeredBy.MANUAL,
        progress_data={},
    )
    repo = UserRepository(
        id=repo_id,
        user_id=uuid.uuid4(),
        github_repo_id=999,
        owner="test",
        name="test",
        full_name="test/test",
        visibility="public",
        html_url="https://github.com/test/test",
        default_branch="main",
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.get.return_value = repo

    with patch("src.modules.sync.tasks.sync_repository.AsyncSessionLocal") as mock_sess_cls:
        mock_sess_cls.return_value.__aenter__.return_value = mock_session
        with patch(
            "src.modules.sync.tasks.sync_repository.SyncJobRepository.get_by_id", return_value=job
        ):
            with patch("src.modules.sync.tasks.sync_repository.select"):
                with patch("src.modules.sync.tasks.sync_repository.decrypt", return_value="token"):
                    with patch(
                        "src.modules.sync.tasks.sync_repository.fetch_repository_commits",
                        return_value=[],
                    ):
                        with patch(
                            "src.modules.sync.tasks.sync_repository.fetch_repository_pull_requests",
                            return_value=[],
                        ):
                            with patch(
                                "src.modules.sync.tasks.sync_repository.fetch_repository_issues",
                                return_value=[],
                            ):
                                with patch(
                                    "src.modules.analytics.tasks.compute_metrics.compute_repository_metrics_task.delay"
                                ) as mock_delay:
                                    # Mock connection returned
                                    mock_conn = MagicMock()
                                    mock_conn.encrypted_access_token = "fake_enc"
                                    mock_res = MagicMock()
                                    mock_res.scalar_one_or_none.return_value = mock_conn
                                    mock_session.execute.return_value = mock_res

                                    await _run_sync(job_id)
                                    assert job.status == SyncStatus.COMPLETED
                                    mock_delay.assert_called_once_with(str(repo_id))
