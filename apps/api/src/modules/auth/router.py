from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.modules.auth.dependencies import CurrentUser
from src.modules.auth.schemas import UserResponse
from src.modules.auth.service import generate_state_token, handle_github_callback

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/github/login")
async def github_login(response: Response) -> RedirectResponse:
    """Redirect to GitHub OAuth page and set state cookie."""
    state = generate_state_token()

    # Set the state cookie
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=True,  # Ensure HTTPS in production
        samesite="lax",
        max_age=600,  # 10 minutes
    )

    # For MVP we can just point redirect_uri directly to backend URL
    # Wait, if github redirects to backend, redirect_uri should be backend url.
    # We will assume a backend url like http://localhost:8000/api/v1/auth/github/callback
    # In production, we typically have a single domain. For now we will rely on default or construct it.

    # We'll omit redirect_uri to let GitHub use the one configured in the app, or explicitly pass it if needed.
    # It's usually safer to omit if perfectly matched in GitHub App settings.

    url = f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}&scope=repo%20read:user%20user:email&state={state}"
    return RedirectResponse(url=url, status_code=307)


@router.get("/github/callback")
async def github_callback(
    request: Request, response: Response, code: str, state: str, db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """Handle OAuth callback, validate state, and set session cookie."""
    cookie_state = request.cookies.get("oauth_state")

    dashboard_url = f"{settings.FRONTEND_URL}/dashboard"
    error_url = f"{settings.FRONTEND_URL}/login?error=invalid_state"

    if not cookie_state or cookie_state != state:
        return RedirectResponse(url=error_url, status_code=302)

    try:
        jwt_token, user = await handle_github_callback(db, code)
    except Exception:
        # Generic error fallback
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error=auth_failed", status_code=302
        )

    redirect = RedirectResponse(url=dashboard_url, status_code=302)

    # Clear the temporary state cookie
    redirect.delete_cookie("oauth_state")

    # Set the session cookie
    redirect.set_cookie(
        key="session",
        value=jwt_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days
    )

    return redirect


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser) -> UserResponse:
    """Get the currently authenticated user."""
    return UserResponse.model_validate(current_user, from_attributes=True)


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Log out by clearing the session cookie."""
    response.delete_cookie("session")
    return {"status": "ok"}
