import asyncio
import contextvars
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx

from src.integrations.github.exceptions import (
    GitHubAPIException,
    GitHubAuthenticationException,
    GitHubConflictException,
    GitHubNotFoundException,
    GitHubRateLimitException,
    GitHubServerException,
    GitHubTimeoutException,
)

_last_rate_limit: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "last_rate_limit", default=None
)


class GitHubClient:
    """Base client for interacting with GitHub APIs with robust rate-limiting and error handling."""

    BASE_API_URL = "https://api.github.com"
    BASE_URL = "https://github.com"

    @staticmethod
    def get_async_client(access_token: Optional[str] = None) -> httpx.AsyncClient:
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if access_token:
            headers["Authorization"] = f"token {access_token}"

        return httpx.AsyncClient(
            headers=headers,
            timeout=15.0,
        )

    @classmethod
    def parse_rate_limit_headers(cls, response: httpx.Response) -> Dict[str, Any]:
        """Extracts and normalizes rate-limit headers from an HTTP response."""
        remaining_str = response.headers.get("X-RateLimit-Remaining")
        reset_time_str = response.headers.get("X-RateLimit-Reset")
        retry_after_str = response.headers.get("Retry-After")

        remaining = int(remaining_str) if remaining_str and remaining_str.isdigit() else None
        retry_after = int(retry_after_str) if retry_after_str and retry_after_str.isdigit() else None

        reset_at: Optional[datetime] = None
        if reset_time_str and reset_time_str.isdigit():
            reset_at = datetime.fromtimestamp(int(reset_time_str), tz=timezone.utc)
        elif retry_after:
            reset_at = datetime.now(timezone.utc) + timedelta(seconds=retry_after)

        return {
            "remaining": remaining,
            "reset_at": reset_at,
            "retry_after": retry_after,
        }

    @classmethod
    def get_last_rate_limit(cls) -> Optional[Dict[str, Any]]:
        """Returns rate-limit metadata from the most recent HTTP request in this async context."""
        return _last_rate_limit.get()

    @classmethod
    def is_last_request_low_budget(cls, threshold: int = 10) -> bool:
        """Checks if the most recent HTTP request left rate-limit remaining at or below threshold."""
        meta = _last_rate_limit.get()
        if not meta:
            return False
        remaining = meta.get("remaining")
        return remaining is not None and remaining <= threshold

    @classmethod
    def check_rate_limit(
        cls,
        response: httpx.Response,
        threshold: int = 10,
        raise_on_low_budget: bool = False,
    ) -> bool:
        """
        Parses rate-limit headers, records metadata on response and async context.
        Raises GitHubRateLimitException on actual exhaustion (HTTP 429, HTTP 403 rate limit, or remaining <= 0).
        Preserves successful response payloads on 2xx responses (does not raise solely for remaining <= threshold
        unless raise_on_low_budget=True).

        Returns:
            bool: True if budget is low (remaining <= threshold), False otherwise.
        """
        meta = cls.parse_rate_limit_headers(response)
        remaining = meta["remaining"]
        reset_at = meta["reset_at"]
        retry_after = meta["retry_after"]
        is_low = remaining is not None and remaining <= threshold

        # Record metadata on response object
        response.rate_limit_remaining = remaining  # type: ignore[attr-defined]
        response.rate_limit_reset_at = reset_at  # type: ignore[attr-defined]
        response.rate_limit_retry_after = retry_after  # type: ignore[attr-defined]
        response.is_low_budget = is_low  # type: ignore[attr-defined]

        # Record metadata on contextvar
        _last_rate_limit.set({
            "remaining": remaining,
            "reset_at": reset_at,
            "retry_after": retry_after,
            "is_low_budget": is_low,
            "status_code": response.status_code,
        })

        # 1. Explicit 429 Too Many Requests
        if response.status_code == 429:
            msg = "GitHub primary or secondary rate limit exceeded (HTTP 429)."
            raise GitHubRateLimitException(
                message=msg,
                reset_at=reset_at,
                retry_after=retry_after,
                remaining=remaining,
                status_code=429,
            )

        # 2. HTTP 403 Rate Limit Exceeded
        if response.status_code == 403:
            resp_text = response.text.lower()
            if "rate limit" in resp_text or "secondary rate" in resp_text or (remaining is not None and remaining <= 0):
                msg = f"GitHub rate limit exceeded (Remaining: {remaining})."
                raise GitHubRateLimitException(
                    message=msg,
                    reset_at=reset_at,
                    retry_after=retry_after,
                    remaining=remaining,
                    status_code=403,
                )

        # 3. Low budget assertion if caller explicitly demands raising
        if raise_on_low_budget and is_low:
            msg = f"GitHub rate limit budget below threshold (Remaining: {remaining} <= {threshold})."
            raise GitHubRateLimitException(
                message=msg,
                reset_at=reset_at,
                retry_after=retry_after,
                remaining=remaining,
                status_code=response.status_code,
            )

        return is_low

    @classmethod
    def check_response(cls, response: httpx.Response, rate_limit_threshold: int = 10) -> None:
        """
        Validates GitHub HTTP response, recording rate-limit metadata without discarding 2xx responses.
        Surfaces actual rate limits (403/429), auth errors (401), not founds (404), conflicts (409), and 5xx.
        """
        # Parse and record rate limits without raising on 2xx
        cls.check_rate_limit(response, threshold=rate_limit_threshold, raise_on_low_budget=False)

        status = response.status_code

        if 200 <= status < 300:
            return

        body = response.text

        if status == 401:
            raise GitHubAuthenticationException(
                message="GitHub authentication failed: bad credentials or expired token.",
                status_code=401,
                response_body=body,
            )
        if status == 403:
            raise GitHubAuthenticationException(
                message="GitHub permission denied: integration lacks required scope or repository access.",
                status_code=403,
                response_body=body,
            )
        if status == 404:
            raise GitHubNotFoundException(
                message=f"GitHub resource not found ({response.request.url}).",
                response_body=body,
            )
        if status == 409:
            raise GitHubConflictException(
                message="GitHub state conflict or Git repository is empty.",
                response_body=body,
            )
        if status in (500, 502, 503, 504):
            raise GitHubServerException(
                message=f"GitHub server error (HTTP {status}).",
                status_code=status,
                response_body=body,
            )

        raise GitHubAPIException(
            message=f"GitHub API error (HTTP {status}): {body}",
            status_code=status,
            response_body=body,
        )

    @classmethod
    async def request_with_retry(
        cls,
        method: str,
        url: str,
        token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        max_retries: int = 3,
        base_delay: float = 0.5,
        client: Optional[httpx.AsyncClient] = None,
        rate_limit_threshold: int = 10,
    ) -> httpx.Response:
        """
        Executes HTTP request with bounded exponential backoff for transient server errors (5xx/timeouts).
        Rate limits (403/429), auth failures (401), not founds (404), and conflicts (409) fail fast without retrying.
        """
        owns_client = client is None
        http_client = client or cls.get_async_client(token)

        try:
            for attempt in range(1, max_retries + 1):
                try:
                    response = await http_client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json_data,
                    )
                    cls.check_response(response, rate_limit_threshold=rate_limit_threshold)
                    return response

                except GitHubServerException as e:
                    if attempt >= max_retries:
                        raise e
                    # Exponential backoff with jitter
                    jitter = random.uniform(0.05, 0.25)
                    delay = (base_delay * (2 ** (attempt - 1))) + jitter
                    await asyncio.sleep(delay)

                except (httpx.TimeoutException, httpx.NetworkError) as e:
                    if attempt >= max_retries:
                        raise GitHubTimeoutException(
                            f"GitHub request timed out or network error occurred after {max_retries} attempts."
                        ) from e
                    jitter = random.uniform(0.05, 0.25)
                    delay = (base_delay * (2 ** (attempt - 1))) + jitter
                    await asyncio.sleep(delay)

            # Fallback if loop completes without return
            raise GitHubServerException("GitHub request failed: max retries exceeded.")
        finally:
            if owns_client:
                await http_client.aclose()

    @staticmethod
    def parse_link_header(link_header: Optional[str]) -> Dict[str, str]:
        """
        Parses GitHub's RFC 5988 Link header into a dict mapping relation name ('next', 'last', 'prev') to URL.
        Example: '<https://api.github.com/...page=2>; rel="next"' -> {'next': 'https://api.github.com/...page=2'}
        """
        if not link_header:
            return {}

        links: Dict[str, str] = {}
        pattern = re.compile(r'<([^>]+)>;\s*rel="([^"]+)"')
        for match in pattern.finditer(link_header):
            url, rel = match.group(1), match.group(2)
            links[rel] = url
        return links

    @classmethod
    def get_next_page_from_link(cls, link_header: Optional[str]) -> Optional[int]:
        """
        Extracts the next page number from a Link header, or None if no 'next' relation exists.
        """
        links = cls.parse_link_header(link_header)
        next_url = links.get("next")
        if not next_url:
            return None

        # Look for page parameter in query string
        match = re.search(r'[?&]page=(\d+)', next_url)
        if match:
            return int(match.group(1))
        return None
