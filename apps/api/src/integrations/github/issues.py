from datetime import datetime
from typing import Any, Dict, List

from src.integrations.github.client import GitHubClient


async def fetch_repository_issues(
    token: str, full_name: str, since_date: datetime | None = None, page: int = 1, per_page: int = 100
) -> List[Dict[str, Any]]:
    """
    Fetches raw issues for a repository.
    Handles rate limiting automatically.
    """
    params: Dict[str, Any] = {
        "per_page": per_page, 
        "page": page,
        "state": "all",
        "sort": "updated",
        "direction": "asc"
    }
    
    if since_date:
        params["since"] = since_date.isoformat()
    
    async with GitHubClient.get_async_client(token) as client:
        response = await client.get(
            f"{GitHubClient.BASE_API_URL}/repos/{full_name}/issues",
            params=params,
        )
        
        GitHubClient.check_rate_limit(response)
        response.raise_for_status()
        
        return response.json()
