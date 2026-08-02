from typing import Any, Dict, List, cast

from src.integrations.github.client import GitHubClient


async def fetch_user_repositories(token: str, max_pages: int = 3) -> List[Dict[str, Any]]:
    """
    Fetches repositories for the authenticated user, up to `max_pages`.
    Only keeps repositories where the user has pull access.
    """
    repos: List[Dict[str, Any]] = []

    async with GitHubClient.get_async_client(token) as client:
        for page in range(1, max_pages + 1):
            response = await client.get(
                f"{GitHubClient.BASE_API_URL}/user/repos",
                params={"per_page": 30, "sort": "updated", "page": page},
            )
            response.raise_for_status()

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


async def fetch_repository_by_id(token: str, repository_id: int) -> Dict[str, Any]:
    """
    Fetches details of a specific repository by its GitHub ID.
    """
    async with GitHubClient.get_async_client(token) as client:
        response = await client.get(f"{GitHubClient.BASE_API_URL}/repositories/{repository_id}")
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())
