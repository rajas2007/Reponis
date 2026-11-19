from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import httpx

from src.integrations.github.client import GitHubClient
from src.integrations.github.exceptions import GitHubConflictException


async def fetch_repository_commits(
    token: str,
    full_name: str,
    sha: Optional[str] = None,
    since_sha: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    page: int = 1,
    per_page: int = 100,
    client: Optional[httpx.AsyncClient] = None,
) -> List[Dict[str, Any]]:
    """
    Fetches raw commits for a repository with pagination and anchor support.

    Parameters:
        token: GitHub OAuth or personal access token.
        full_name: Repository in 'owner/repo' format.
        sha: SHA or branch name to start listing commits from.
        since_sha: Legacy alias for sha parameter.
        since: Only commits after this datetime.
        until: Only commits before this datetime.
        page: Page number (1-indexed).
        per_page: Number of commits per page (clamped between 1 and 100).
        client: Optional shared httpx.AsyncClient instance.
    """
    target_sha = sha or since_sha
    clamped_per_page = min(max(1, per_page), 100)
    clamped_page = max(1, page)

    params: Dict[str, Any] = {
        "per_page": clamped_per_page,
        "page": clamped_page,
    }
    if target_sha:
        params["sha"] = target_sha
    if since:
        params["since"] = since.isoformat()
    if until:
        params["until"] = until.isoformat()

    url = f"{GitHubClient.BASE_API_URL}/repos/{full_name}/commits"

    try:
        response = await GitHubClient.request_with_retry(
            method="GET",
            url=url,
            token=token,
            params=params,
            client=client,
        )
        return cast(List[Dict[str, Any]], response.json())
    except GitHubConflictException:
        # HTTP 409 Git Repository is empty - returns empty list safely
        return []
