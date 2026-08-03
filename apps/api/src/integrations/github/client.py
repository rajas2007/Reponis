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

    @staticmethod
    def check_rate_limit(response: httpx.Response, threshold: int = 50) -> None:
        """
        Checks rate limit headers and raises GitHubRateLimitException if budget is below threshold.
        """
        from datetime import datetime, timezone
        from src.integrations.github.exceptions import GitHubRateLimitException

        remaining = response.headers.get("X-RateLimit-Remaining")
        reset_time = response.headers.get("X-RateLimit-Reset")

        if remaining is not None and int(remaining) <= threshold:
            reset_at = None
            if reset_time:
                reset_at = datetime.fromtimestamp(int(reset_time), tz=timezone.utc)
            
            raise GitHubRateLimitException(
                message=f"GitHub rate limit reached (Remaining: {remaining}).",
                reset_at=reset_at
            )
