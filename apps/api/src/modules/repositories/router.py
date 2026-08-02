from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.modules.auth.dependencies import CurrentUser
from src.modules.repositories import service
from src.modules.repositories.schemas import (
    RepositoriesAvailableResponse,
    RepositoriesConnectedResponse,
    RepositoryConnectRequest,
    RepositoryCurrentResponse,
    RepositoryResponse,
)

router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.get("/available", response_model=RepositoriesAvailableResponse)
async def get_available_repositories_endpoint(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> RepositoriesAvailableResponse:
    """Fetches live repositories from GitHub that the user can connect."""
    repos = await service.get_available_repositories(db, current_user.id)  # type: ignore
    return RepositoriesAvailableResponse(repositories=repos)


@router.get("/connected", response_model=RepositoriesConnectedResponse)
async def get_connected_repositories_endpoint(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> RepositoriesConnectedResponse:
    """Retrieves all repositories connected by the user."""
    repos = await service.get_connected_repositories(db, current_user.id)  # type: ignore
    return RepositoriesConnectedResponse(repositories=repos)


@router.get("/current", response_model=RepositoryCurrentResponse)
async def get_current_repository_endpoint(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> RepositoryCurrentResponse:
    """Retrieves the user's currently active connected repository."""
    repo = await service.get_current_repository(db, current_user.id)  # type: ignore
    return RepositoryCurrentResponse(repository=repo)


@router.post("/connect", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def connect_repository_endpoint(
    request: RepositoryConnectRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> RepositoryResponse:
    """Connects a repository to Reponis."""
    return await service.connect_repository(db, current_user.id, request.github_repo_id)  # type: ignore
