from typing import Any, Dict, List

from src.integrations.github.client import GitHubClient


async def fetch_repository_commits(
    token: str, full_name: str, since_sha: str | None = None, page: int = 1, per_page: int = 100
) -> List[Dict[str, Any]]:
    """
    Fetches raw commits for a repository.
    Handles rate limiting automatically by raising GitHubRateLimitException if threshold is hit.
    """
    params: Dict[str, Any] = {"per_page": per_page, "page": page}
    # Note: GitHub doesn't have a strict 'since_sha' parameter for commit history pagination 
    # except `since` (timestamp) or `sha` (branch/commit).
    # For MVP, we might fetch from default branch and stop when we see `last_commit_sha`.
    
    async with GitHubClient.get_async_client(token) as client:
        response = await client.get(
            f"{GitHubClient.BASE_API_URL}/repos/{full_name}/commits",
            params=params,
        )
        
        GitHubClient.check_rate_limit(response)
        response.raise_for_status()
        
        return response.json()
