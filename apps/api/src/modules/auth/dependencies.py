from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.core.database import get_db
from src.core.security import decode_access_token
from src.modules.users.models import User


async def get_current_user_from_cookie(
    session: Annotated[str | None, Cookie()] = None, db: AsyncSession = Depends(get_db)
) -> User:
    """Extracts the JWT from the HttpOnly session cookie and returns the User."""

    auth_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "unauthorized", "message": "Invalid or expired session"}},
    )

    if not session:
        raise auth_exception

    try:
        payload = decode_access_token(session)
        user_id_str = str(payload.get("sub"))
        if not payload.get("sub"):
            raise auth_exception
    except jwt.PyJWTError:
        raise auth_exception

    result = await db.execute(select(User).where(User.id == user_id_str))
    user = result.scalar_one_or_none()

    if user is None:
        raise auth_exception

    return user


CurrentUser = Annotated[User, Depends(get_current_user_from_cookie)]
