import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.core.encryption import encrypt
from src.core.security import create_access_token
from src.integrations.github.oauth import exchange_code_for_token
from src.integrations.github.users import get_current_user, get_primary_email
from src.modules.users.models import GitHubConnection, User


def generate_state_token() -> str:
    """Generate a random state token for CSRF protection."""
    return secrets.token_urlsafe(32)


async def handle_github_callback(session: AsyncSession, code: str) -> tuple[str, User]:
    """
    Exchanges the code for a GitHub token, fetches the user profile,
    upserts the user and connection in the DB, and returns a session JWT and User object.
    """
    # 1. Exchange code for GitHub token
    token_data = await exchange_code_for_token(code)
    access_token = token_data["access_token"]
    scopes = token_data.get("scope", "")
    token_type = token_data.get("token_type", "bearer")

    # 1. Fetch Profile
    github_user = await get_current_user(access_token)
    github_id = int(github_user["id"])
    username = str(github_user["login"])
    avatar_url = str(github_user.get("avatar_url")) if github_user.get("avatar_url") else None

    # Email might be private, so fetch it separately if needed
    email = github_user.get("email")
    if not email:
        email = await get_primary_email(access_token)

    # 3. Upsert User
    result = await session.execute(select(User).where(User.github_id == github_id))
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if user:
        user.username = username
        user.email = email
        user.avatar_url = avatar_url
        user.last_login_at = now
    else:
        user = User(
            id=uuid.uuid4(),  # type: ignore
            github_id=github_id,
            username=username,
            email=email,
            avatar_url=avatar_url,
            created_at=now,
            updated_at=now,
            last_login_at=now,
        )
        session.add(user)

    await session.flush()  # Ensure user.id is available

    # 4. Upsert GitHub Connection
    encrypted_token = encrypt(access_token)
    conn_result = await session.execute(
        select(GitHubConnection).where(GitHubConnection.user_id == user.id)
    )
    connection = conn_result.scalar_one_or_none()

    if connection:
        connection.encrypted_access_token = encrypted_token
        connection.scopes = scopes
        connection.token_type = token_type
        connection.last_verified_at = now
    else:
        connection = GitHubConnection(
            user_id=user.id,
            encrypted_access_token=encrypted_token,
            scopes=scopes,
            token_type=token_type,
            connected_at=now,
            last_verified_at=now,
        )
        session.add(connection)

    await session.commit()
    await session.refresh(user)

    # 5. Generate Session JWT
    jwt_token = create_access_token(subject=str(user.id))

    return jwt_token, user
