from typing import List, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.analytics.models import WeeklyMetric


class AnalyticsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_weekly_metrics(self, repository_id: UUID) -> List[WeeklyMetric]:
        stmt = (
            select(WeeklyMetric)
            .where(WeeklyMetric.repository_id == repository_id)
            .order_by(WeeklyMetric.week_start.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_weekly_metrics(self, metrics_data: Sequence[dict]) -> None:
        if not metrics_data:
            return

        insert_stmt = insert(WeeklyMetric).values(metrics_data)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["repository_id", "week_start"],
            set_={
                "commit_count": insert_stmt.excluded.commit_count,
                "commit_frequency_per_day": insert_stmt.excluded.commit_frequency_per_day,
                "active_contributors": insert_stmt.excluded.active_contributors,
                "prs_opened": insert_stmt.excluded.prs_opened,
                "prs_merged": insert_stmt.excluded.prs_merged,
                "prs_closed_without_merge": insert_stmt.excluded.prs_closed_without_merge,
                "pr_merge_rate": insert_stmt.excluded.pr_merge_rate,
                "cycle_time_total_p50": insert_stmt.excluded.cycle_time_total_p50,
                "cycle_time_to_first_review_p50": insert_stmt.excluded.cycle_time_to_first_review_p50,
                "cycle_time_review_to_approval_p50": insert_stmt.excluded.cycle_time_review_to_approval_p50,
                "cycle_time_approval_to_merge_p50": insert_stmt.excluded.cycle_time_approval_to_merge_p50,
                "issues_opened": insert_stmt.excluded.issues_opened,
                "issues_closed": insert_stmt.excluded.issues_closed,
                "bugs_opened": insert_stmt.excluded.bugs_opened,
                "bugs_closed": insert_stmt.excluded.bugs_closed,
                "computed_at": insert_stmt.excluded.computed_at,
            },
        )
        await self.session.execute(upsert_stmt)
