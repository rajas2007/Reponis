from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

from src.core.config import settings


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a new JWT access token."""
    assert settings.SECRET_KEY is not None, "SECRET_KEY must be set"
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default expiration is 7 days for web sessions
        expire = datetime.now(timezone.utc) + timedelta(days=7)

    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return str(encoded_jwt)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT access token. Raises jwt.PyJWTError on failure."""
    assert settings.SECRET_KEY is not None, "SECRET_KEY must be set"
    return dict(  # type: ignore
        jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    )
