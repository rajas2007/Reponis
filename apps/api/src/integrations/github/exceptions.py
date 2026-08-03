from datetime import datetime
from typing import Optional


class GitHubAPIException(Exception):
    """Base exception for GitHub API errors."""
    pass


class GitHubRateLimitException(GitHubAPIException):
    """Raised when GitHub API rate limit is exceeded."""
    
    def __init__(self, message: str, reset_at: Optional[datetime] = None):
        super().__init__(message)
        self.reset_at = reset_at
