from typing import Any, Dict, Optional, cast

import httpx

from src.integrations.github.client import GitHubClient


async def fetch_compare_commits(
    token: str,
    full_name: str,
    base: str,
    head: str,
    page: int = 1,
    per_page: int = 100,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Fetches the comparison diff between two commit SHAs or branch refs using GitHub's Compare API.

    URL: GET /repos/{owner}/{repo}/compare/{base}...{head}

    Parameters:
        token: GitHub OAuth or personal access token.
        full_name: Repository in 'owner/repo' format.
        base: The base commit SHA or branch name (anchored previous head).
        head: The target commit SHA or branch name (remote current head).
        page: Page number for paginating commits in the diff (1-indexed).
        per_page: Number of commits per page (clamped between 1 and 100).
        client: Optional shared httpx.AsyncClient instance.

    Returns:
        Structured dictionary containing:
        - status: Comparison status ('identical', 'ahead', 'behind', 'diverged').
        - ahead_by: Number of commits head is ahead of base.
        - behind_by: Number of commits head is behind base.
        - total_commits: Total count of commits returned.
        - base_commit: Dict metadata of the base commit.
        - merge_base_commit: Dict metadata of the common ancestor.
        - commits: List of normalized commit objects.
        - raw: The raw API response payload.

    Raises:
        GitHubNotFoundException: When base or head SHA does not exist (e.g. force push / pruned anchor).
        GitHubRateLimitException: When API rate limits are exhausted.
        GitHubAPIException: On non-retryable client errors.
    """
    clamped_per_page = min(max(1, per_page), 100)
    clamped_page = max(1, page)

    params: Dict[str, Any] = {
        "per_page": clamped_per_page,
        "page": clamped_page,
    }

    url = f"{GitHubClient.BASE_API_URL}/repos/{full_name}/compare/{base}...{head}"

    response = await GitHubClient.request_with_retry(
        method="GET",
        url=url,
        token=token,
        params=params,
        client=client,
    )
    data = cast(Dict[str, Any], response.json())

    return {
        "status": data.get("status"),
        "ahead_by": data.get("ahead_by", 0),
        "behind_by": data.get("behind_by", 0),
        "total_commits": data.get("total_commits", 0),
        "base_commit": data.get("base_commit"),
        "merge_base_commit": data.get("merge_base_commit"),
        "commits": data.get("commits", []),
        "permalink_url": data.get("permalink_url"),
        "html_url": data.get("html_url"),
        "raw": data,
    }
