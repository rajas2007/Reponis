from datetime import datetime
from typing import Optional


class GitHubAPIException(Exception):
    """Base exception for GitHub API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class GitHubRateLimitException(GitHubAPIException):
    """Raised when GitHub API rate limit is exceeded or budget falls below safety threshold."""

    def __init__(
        self,
        message: str,
        reset_at: Optional[datetime] = None,
        retry_after: Optional[int] = None,
        remaining: Optional[int] = None,
        status_code: int = 403,
    ):
        super().__init__(message, status_code=status_code)
        self.reset_at = reset_at
        self.retry_after = retry_after
        self.remaining = remaining


class GitHubNotFoundException(GitHubAPIException):
    """Raised when a requested GitHub resource (repo, branch, commit, PR, review) is not found (HTTP 404)."""

    def __init__(self, message: str = "GitHub resource not found.", response_body: Optional[str] = None):
        super().__init__(message, status_code=404, response_body=response_body)


# Alias for explicit design document references
GitHubHTTP404Exception = GitHubNotFoundException
GitHubResourceNotFoundError = GitHubNotFoundException


class GitHubAuthenticationException(GitHubAPIException):
    """Raised on authentication failure or insufficient permissions (HTTP 401 or non-rate-limit 403)."""

    def __init__(self, message: str = "GitHub authentication failed.", status_code: int = 401, response_body: Optional[str] = None):
        super().__init__(message, status_code=status_code, response_body=response_body)


class GitHubConflictException(GitHubAPIException):
    """Raised on state conflict (HTTP 409), such as an empty git repository with no commits."""

    def __init__(self, message: str = "GitHub state conflict or empty repository.", response_body: Optional[str] = None):
        super().__init__(message, status_code=409, response_body=response_body)


class GitHubServerException(GitHubAPIException):
    """Raised when GitHub returns a 5xx transient server error after retry attempts have been exhausted."""

    def __init__(self, message: str = "GitHub internal server error.", status_code: int = 500, response_body: Optional[str] = None):
        super().__init__(message, status_code=status_code, response_body=response_body)


class GitHubTimeoutException(GitHubAPIException):
    """Raised when an HTTP connection or read times out after retry attempts have been exhausted."""

    def __init__(self, message: str = "GitHub request timed out."):
        super().__init__(message, status_code=None, response_body=None)
