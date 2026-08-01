from typing import Any, Dict

from src.core.config import settings
from src.integrations.github.client import GitHubClient


async def exchange_code_for_token(code: str) -> Dict[str, Any]:
    """Exchanges an OAuth code for a GitHub access token."""
    url = f"{GitHubClient.BASE_URL}/login/oauth/access_token"

    data = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "client_secret": settings.GITHUB_CLIENT_SECRET,
        "code": code,
    }

    async with GitHubClient.get_async_client() as client:
        # GitHub requires Accept header to return JSON for this endpoint
        client.headers.update({"Accept": "application/json"})
        response = await client.post(url, data=data)
        response.raise_for_status()

        result = response.json()
        if "error" in result:
            raise ValueError(
                f"GitHub OAuth error: {result.get('error_description', result['error'])}"
            )

        return dict(result)  # type: ignore
