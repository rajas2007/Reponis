from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import httpx

from src.integrations.github.client import GitHubClient


async def fetch_repository_pull_requests(
    token: str,
    full_name: str,
    state: str = "all",
    sort: str = "updated",
    direction: str = "desc",
    page: int = 1,
    per_page: int = 100,
    since_date: Optional[datetime] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> List[Dict[str, Any]]:
    """
    Fetches raw pull requests for a repository with pagination and sort order.

    CRITICAL (V6.2 Specification): GitHub's /pulls endpoint does NOT support a 'since' parameter.
    PR traversal must paginate using sort='updated' and direction='desc' or 'asc' and filter
    client-side against watermarks.

    Parameters:
        token: GitHub OAuth or personal access token.
        full_name: Repository in 'owner/repo' format.
        state: PR state filter ('open', 'closed', or 'all'). Default 'all'.
        sort: Sort field ('updated', 'created', 'popularity', 'long-running'). Default 'updated'.
        direction: Sort direction ('desc' or 'asc'). Default 'desc'.
        page: Page number (1-indexed).
        per_page: Results per page (clamped between 1 and 100).
        since_date: Legacy parameter preserved for backwards compatibility (ignored in API call).
        client: Optional shared httpx.AsyncClient instance.
    """
    clamped_per_page = min(max(1, per_page), 100)
    clamped_page = max(1, page)

    params: Dict[str, Any] = {
        "per_page": clamped_per_page,
        "page": clamped_page,
        "state": state,
        "sort": sort,
        "direction": direction,
    }

    url = f"{GitHubClient.BASE_API_URL}/repos/{full_name}/pulls"

    response = await GitHubClient.request_with_retry(
        method="GET",
        url=url,
        token=token,
        params=params,
        client=client,
    )
    return cast(List[Dict[str, Any]], response.json())


async def fetch_pull_request_reviews(
    token: str,
    full_name: str,
    pull_number: int,
    page: int = 1,
    per_page: int = 100,
    client: Optional[httpx.AsyncClient] = None,
) -> List[Dict[str, Any]]:
    """
    Fetches raw reviews for a specific pull request with pagination.

    Parameters:
        token: GitHub OAuth or personal access token.
        full_name: Repository in 'owner/repo' format.
        pull_number: The number of the pull request.
        page: Page number (1-indexed).
        per_page: Results per page (clamped between 1 and 100).
        client: Optional shared httpx.AsyncClient instance.
    """
    clamped_per_page = min(max(1, per_page), 100)
    clamped_page = max(1, page)

    params: Dict[str, Any] = {
        "per_page": clamped_per_page,
        "page": clamped_page,
    }

    url = f"{GitHubClient.BASE_API_URL}/repos/{full_name}/pulls/{pull_number}/reviews"

    response = await GitHubClient.request_with_retry(
        method="GET",
        url=url,
        token=token,
        params=params,
        client=client,
    )
    reviews_data = cast(List[Dict[str, Any]], response.json())

    # Ensure structured consistency and safety on missing or null review IDs
    normalized_reviews: List[Dict[str, Any]] = []
    for r in reviews_data:
        raw_id = r.get("id")
        normalized_reviews.append({
            **r,
            "id": raw_id,
            "github_review_id": str(raw_id) if raw_id is not None else None,
        })

    return normalized_reviews
