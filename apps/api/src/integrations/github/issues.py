from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import httpx

from src.integrations.github.client import GitHubClient


async def fetch_repository_issues(
    token: str,
    full_name: str,
    since_date: Optional[datetime] = None,
    page: int = 1,
    per_page: int = 100,
    client: Optional[httpx.AsyncClient] = None,
) -> List[Dict[str, Any]]:
    """
    Fetches raw issues for a repository.
    Handles rate limiting and retries automatically.
    """
    clamped_per_page = min(max(1, per_page), 100)
    clamped_page = max(1, page)

    params: Dict[str, Any] = {
        "per_page": clamped_per_page,
        "page": clamped_page,
        "state": "all",
        "sort": "updated",
        "direction": "asc",
    }

    if since_date:
        params["since"] = since_date.isoformat()

    response = await GitHubClient.request_with_retry(
        method="GET",
        url=f"{GitHubClient.BASE_API_URL}/repos/{full_name}/issues",
        token=token,
        params=params,
        client=client,
    )
    return cast(List[Dict[str, Any]], response.json())
