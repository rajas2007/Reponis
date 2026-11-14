from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WeeklyMetricItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week_start: date
    commit_count: Optional[int] = None
    commit_frequency_per_day: Optional[float] = None
    active_contributors: Optional[int] = None

    prs_opened: Optional[int] = None
    prs_merged: Optional[int] = None
    prs_closed_without_merge: Optional[int] = None
    pr_merge_rate: Optional[float] = None

    cycle_time_total_p50: Optional[float] = None
    cycle_time_to_first_review_p50: Optional[float] = None
    cycle_time_review_to_approval_p50: Optional[float] = None
    cycle_time_approval_to_merge_p50: Optional[float] = None

    issues_opened: Optional[int] = None
    issues_closed: Optional[int] = None
    bugs_opened: Optional[int] = None
    bugs_closed: Optional[int] = None

    computed_at: datetime


class WeeklyMetricsResponse(BaseModel):
    repository_id: UUID
    metrics: List[WeeklyMetricItem]
