from typing import Any, Dict

from src.integrations.github.client import GitHubClient


async def get_current_user(access_token: str) -> Dict[str, Any]:
    """Fetches the currently authenticated GitHub user's profile."""
    url = f"{GitHubClient.BASE_API_URL}/user"

    async with GitHubClient.get_async_client(access_token) as client:
        response = await client.get(url)
        response.raise_for_status()
        return dict(response.json())  # type: ignore


async def get_primary_email(access_token: str) -> str | None:
    """Fetches the user's primary email if not public in the profile."""
    url = f"{GitHubClient.BASE_API_URL}/user/emails"

    async with GitHubClient.get_async_client(access_token) as client:
        response = await client.get(url)
        response.raise_for_status()
        emails = response.json()

        for email_obj in emails:
            if email_obj.get("primary") and email_obj.get("verified"):
                return str(email_obj.get("email"))

        return None
