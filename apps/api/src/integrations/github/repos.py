from typing import Any, Dict, List, Optional, cast

import httpx

from src.integrations.github.client import GitHubClient


async def fetch_user_repositories(
    token: str, max_pages: int = 3, client: Optional[httpx.AsyncClient] = None
) -> List[Dict[str, Any]]:
    """
    Fetches repositories for the authenticated user, up to `max_pages`.
    Only keeps repositories where the user has pull access.
    """
    repos: List[Dict[str, Any]] = []

    for page in range(1, max_pages + 1):
        response = await GitHubClient.request_with_retry(
            method="GET",
            url=f"{GitHubClient.BASE_API_URL}/user/repos",
            token=token,
            params={"per_page": 30, "sort": "updated", "page": page},
            client=client,
        )

        page_data = response.json()
        if not page_data:
            break

        for repo in page_data:
            permissions = repo.get("permissions", {})
            if permissions.get("pull", False):
                repos.append(repo)

        # Check if there's a next page from the Link header
        link_header = response.headers.get("Link", "")
        if 'rel="next"' not in link_header:
            break

    return repos


async def fetch_repository_by_id(
    token: str, repository_id: int, client: Optional[httpx.AsyncClient] = None
) -> Dict[str, Any]:
    """
    Fetches details of a specific repository by its GitHub ID.
    """
    response = await GitHubClient.request_with_retry(
        method="GET",
        url=f"{GitHubClient.BASE_API_URL}/repositories/{repository_id}",
        token=token,
        client=client,
    )
    return cast(Dict[str, Any], response.json())


async def fetch_branch_head(
    token: str,
    full_name: str,
    branch: str = "main",
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Fetches the latest commit SHA and branch metadata for a given repository branch.

    URL: GET /repos/{owner}/{repo}/branches/{branch}

    Parameters:
        token: GitHub OAuth or personal access token.
        full_name: Repository in 'owner/repo' format.
        branch: Name of the branch (default 'main').
        client: Optional shared httpx.AsyncClient instance.

    Returns:
        Dict containing branch metadata with 'commit' object:
        {'name': branch, 'commit': {'sha': '...', ...}, ...}

    Raises:
        GitHubNotFoundException: If the specified branch or repository is not found.
    """
    response = await GitHubClient.request_with_retry(
        method="GET",
        url=f"{GitHubClient.BASE_API_URL}/repos/{full_name}/branches/{branch}",
        token=token,
        client=client,
    )
    return cast(Dict[str, Any], response.json())
