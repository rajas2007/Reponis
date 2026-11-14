import statistics
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.analytics.repository import AnalyticsRepository
from src.modules.analytics.utils import get_week_start, get_week_start_datetime
from src.modules.sync.raw_models import Commit, Issue, PullRequest


def _calc_p50(values: List[float]) -> Optional[Decimal]:
    """Calculates median (P50) rounded to 2 decimal places. Returns None if values is empty."""
    if not values:
        return None
    med = statistics.median(values)
    return Decimal(str(round(med, 2)))


async def compute_repository_metrics(
    session: AsyncSession,
    repository_id: UUID,
    now: Optional[datetime] = None,
) -> None:
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    current_week_start_date = get_week_start(now)
    # Exactly 52 consecutive weekly buckets including the current week (current_week_start - 51 weeks to current_week_start)
    week_starts: List[date] = [
        current_week_start_date - timedelta(weeks=i) for i in reversed(range(52))
    ]
    window_start_dt = get_week_start_datetime(week_starts[0])
    window_end_dt = get_week_start_datetime(week_starts[-1]) + timedelta(days=7)

    stmt_commits = select(Commit).where(
        Commit.user_repository_id == repository_id,
        Commit.authored_date >= window_start_dt,
        Commit.authored_date < window_end_dt,
    )
    res_commits = await session.execute(stmt_commits)
    commits = list(res_commits.scalars().all())

    stmt_prs = (
        select(PullRequest)
        .options(selectinload(PullRequest.reviews))
        .where(PullRequest.user_repository_id == repository_id)
    )
    res_prs = await session.execute(stmt_prs)
    all_prs = list(res_prs.scalars().all())

    stmt_issues = select(Issue).where(Issue.user_repository_id == repository_id)
    res_issues = await session.execute(stmt_issues)
    all_issues = list(res_issues.scalars().all())

    metrics_to_upsert: List[Dict[str, Any]] = []
    computed_at = now

    for ws in week_starts:
        w_start_dt = get_week_start_datetime(ws)
        w_end_dt = w_start_dt + timedelta(days=7)

        # Commits
        week_commits = [
            c
            for c in commits
            if c.authored_date is not None and w_start_dt <= c.authored_date < w_end_dt
        ]
        commit_count = len(week_commits)
        commit_frequency_per_day = Decimal(str(round(commit_count / 7.0, 2)))
        active_contributors = len(
            {
                c.author_name or c.author_email
                for c in week_commits
                if (c.author_name or c.author_email)
            }
        )

        # PRs
        prs_opened = len(
            [
                pr
                for pr in all_prs
                if pr.created_at is not None and w_start_dt <= pr.created_at < w_end_dt
            ]
        )

        week_merged_prs = [
            pr
            for pr in all_prs
            if pr.merged_at is not None and w_start_dt <= pr.merged_at < w_end_dt
        ]
        prs_merged = len(week_merged_prs)

        prs_closed_without_merge = len(
            [
                pr
                for pr in all_prs
                if pr.closed_at is not None
                and pr.merged_at is None
                and w_start_dt <= pr.closed_at < w_end_dt
            ]
        )

        total_closed = prs_merged + prs_closed_without_merge
        if total_closed > 0:
            pr_merge_rate = Decimal(str(round(prs_merged / float(total_closed), 4)))
        else:
            pr_merge_rate = None

        total_cycle_times: List[float] = []
        time_to_first_review_times: List[float] = []
        review_to_approval_times: List[float] = []
        approval_to_merge_times: List[float] = []

        for pr in week_merged_prs:
            if pr.merged_at is None or pr.created_at is None:
                continue

            t_total_hours = (pr.merged_at - pr.created_at).total_seconds() / 3600.0
            total_cycle_times.append(t_total_hours)

            valid_reviews = [
                r for r in (pr.reviews or []) if r.submitted_at is not None and r.state is not None
            ]
            if valid_reviews:
                sorted_reviews = sorted(valid_reviews, key=lambda r: r.submitted_at)  # type: ignore[arg-type, return-value]
                first_review = sorted_reviews[0]
                first_review_at = first_review.submitted_at
                if first_review_at is not None:
                    t_first_review_hours = (
                        first_review_at - pr.created_at
                    ).total_seconds() / 3600.0
                    time_to_first_review_times.append(t_first_review_hours)

                    approvals = [r for r in sorted_reviews if (r.state or "").upper() == "APPROVED"]
                    if approvals and approvals[0].submitted_at is not None:
                        approved_at = approvals[0].submitted_at
                        t_review_to_approval = (
                            approved_at - first_review_at
                        ).total_seconds() / 3600.0
                        t_approval_to_merge = (pr.merged_at - approved_at).total_seconds() / 3600.0

                        review_to_approval_times.append(t_review_to_approval)
                        approval_to_merge_times.append(t_approval_to_merge)

        cycle_time_total_p50 = _calc_p50(total_cycle_times)
        cycle_time_to_first_review_p50 = _calc_p50(time_to_first_review_times)
        cycle_time_review_to_approval_p50 = _calc_p50(review_to_approval_times)
        cycle_time_approval_to_merge_p50 = _calc_p50(approval_to_merge_times)

        # Issue throughput
        issues_opened = len(
            [
                issue
                for issue in all_issues
                if issue.created_at is not None and w_start_dt <= issue.created_at < w_end_dt
            ]
        )
        issues_closed = len(
            [
                issue
                for issue in all_issues
                if issue.closed_at is not None and w_start_dt <= issue.closed_at < w_end_dt
            ]
        )
        bugs_opened = len(
            [
                issue
                for issue in all_issues
                if issue.is_bug
                and issue.created_at is not None
                and w_start_dt <= issue.created_at < w_end_dt
            ]
        )
        bugs_closed = len(
            [
                issue
                for issue in all_issues
                if issue.is_bug
                and issue.closed_at is not None
                and w_start_dt <= issue.closed_at < w_end_dt
            ]
        )

        metrics_to_upsert.append(
            {
                "id": uuid.uuid4(),
                "repository_id": repository_id,
                "week_start": ws,
                "commit_count": commit_count,
                "commit_frequency_per_day": commit_frequency_per_day,
                "active_contributors": active_contributors,
                "prs_opened": prs_opened,
                "prs_merged": prs_merged,
                "prs_closed_without_merge": prs_closed_without_merge,
                "pr_merge_rate": pr_merge_rate,
                "cycle_time_total_p50": cycle_time_total_p50,
                "cycle_time_to_first_review_p50": cycle_time_to_first_review_p50,
                "cycle_time_review_to_approval_p50": cycle_time_review_to_approval_p50,
                "cycle_time_approval_to_merge_p50": cycle_time_approval_to_merge_p50,
                "issues_opened": issues_opened,
                "issues_closed": issues_closed,
                "bugs_opened": bugs_opened,
                "bugs_closed": bugs_closed,
                "computed_at": computed_at,
            }
        )

    analytics_repo = AnalyticsRepository(session)
    await analytics_repo.upsert_weekly_metrics(metrics_to_upsert)
    await session.commit()
