from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.modules.analytics.repository import AnalyticsRepository
from src.modules.analytics.schemas import WeeklyMetricItem, WeeklyMetricsResponse
from src.modules.auth.dependencies import CurrentUser
from src.modules.repositories.repository import RepositoriesRepository

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/repositories/{repository_id}/weekly",
    response_model=WeeklyMetricsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_weekly_metrics(
    repository_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> WeeklyMetricsResponse:
    repo_repository = RepositoriesRepository(session)
    repo = await repo_repository.get_by_id(repository_id)

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found.",
        )

    if repo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access metrics for this repository.",
        )

    analytics_repository = AnalyticsRepository(session)
    metrics = await analytics_repository.get_weekly_metrics(repository_id)

    return WeeklyMetricsResponse(
        repository_id=repository_id,
        metrics=[WeeklyMetricItem.model_validate(m) for m in metrics],
    )
