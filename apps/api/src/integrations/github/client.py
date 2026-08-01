import httpx


class GitHubClient:
    """Base client for interacting with GitHub APIs."""

    BASE_API_URL = "https://api.github.com"
    BASE_URL = "https://github.com"

    @staticmethod
    def get_async_client(access_token: str | None = None) -> httpx.AsyncClient:
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if access_token:
            headers["Authorization"] = f"token {access_token}"

        return httpx.AsyncClient(
            headers=headers,
            timeout=10.0,
        )
