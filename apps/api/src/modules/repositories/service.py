import uuid
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.core.encryption import decrypt
from src.integrations.github.repos import fetch_repository_by_id, fetch_user_repositories
from src.modules.repositories.models import UserRepository
from src.modules.repositories.repository import RepositoriesRepository
from src.modules.repositories.schemas import RepositoryAvailable, RepositoryResponse
from src.modules.users.models import GitHubConnection


async def _get_decrypted_token(session: AsyncSession, user_id: uuid.UUID) -> str:
    result = await session.execute(
        select(GitHubConnection).where(GitHubConnection.user_id == user_id)
    )
    connection = result.scalar_one_or_none()
    if not connection or not connection.encrypted_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub connection not found"
        )
    return decrypt(str(connection.encrypted_access_token))


async def get_available_repositories(
    session: AsyncSession, user_id: uuid.UUID
) -> List[RepositoryAvailable]:
    """Fetches repositories from GitHub where the user has pull access."""
    token = await _get_decrypted_token(session, user_id)
    raw_repos = await fetch_user_repositories(token, max_pages=3)

    available = []
    for r in raw_repos:
        available.append(
            RepositoryAvailable(
                github_repo_id=r["id"],
                owner=r["owner"]["login"],
                name=r["name"],
                full_name=r["full_name"],
                visibility=r.get("visibility") or ("private" if r.get("private") else "public"),
                description=r.get("description"),
                language=r.get("language"),
                html_url=r["html_url"],
            )
        )
    return available


async def connect_repository(
    session: AsyncSession, user_id: uuid.UUID, github_repo_id: int
) -> RepositoryResponse:
    repo_repo = RepositoriesRepository(session)

    # Idempotency check: if already active, just return it
    existing = await repo_repo.get_by_github_id(user_id, github_repo_id)
    if existing and existing.is_active:
        return RepositoryResponse.model_validate(existing)

    token = await _get_decrypted_token(session, user_id)
    try:
        repo_data = await fetch_repository_by_id(token, github_repo_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not fetch repository from GitHub. Verify permissions.",
        )

    # Disconnect active repository
    await repo_repo.disconnect_active(user_id)

    # If the user previously connected this repo, reactivate it
    if existing:
        existing.is_active = True
        existing.sync_status = "never_synced"
        existing.disconnected_at = None

        # update metadata in case it changed
        existing.name = repo_data["name"]
        existing.full_name = repo_data["full_name"]
        existing.owner = repo_data["owner"]["login"]
        existing.visibility = repo_data.get("visibility") or (
            "private" if repo_data.get("private") else "public"
        )
        existing.description = repo_data.get("description")
        existing.language = repo_data.get("language")
        existing.html_url = repo_data["html_url"]
        existing.default_branch = repo_data.get("default_branch", "main")

        await repo_repo.update(existing)
        await session.commit()
        await session.refresh(existing)
        return RepositoryResponse.model_validate(existing)

    # Create new user repository
    new_repo = UserRepository(
        user_id=user_id,  # type: ignore
        github_repo_id=repo_data["id"],
        owner=repo_data["owner"]["login"],
        name=repo_data["name"],
        full_name=repo_data["full_name"],
        visibility=repo_data.get("visibility")
        or ("private" if repo_data.get("private") else "public"),
        description=repo_data.get("description"),
        language=repo_data.get("language"),
        html_url=repo_data["html_url"],
        default_branch=repo_data.get("default_branch", "main"),
        sync_status="never_synced",
        is_active=True,
    )

    await repo_repo.create(new_repo)
    await session.commit()
    await session.refresh(new_repo)
    return RepositoryResponse.model_validate(new_repo)


async def get_connected_repositories(
    session: AsyncSession, user_id: uuid.UUID
) -> List[RepositoryResponse]:
    repo_repo = RepositoriesRepository(session)
    repos = await repo_repo.get_all_by_user_id(user_id)
    return [RepositoryResponse.model_validate(r) for r in repos]


async def get_current_repository(
    session: AsyncSession, user_id: uuid.UUID
) -> RepositoryResponse | None:
    repo_repo = RepositoriesRepository(session)
    repo = await repo_repo.get_active_by_user_id(user_id)
    if repo:
        return RepositoryResponse.model_validate(repo)
    return None
