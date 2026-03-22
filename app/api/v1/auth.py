from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth_service
from app.auth.schemas import (
    LoginRequest,
    LogoutAllResponse,
    LogoutRequest,
    MeResponse,
    RefreshTokenRequest,
    TokenResponse,
)
from app.core.db import get_db
from app.api.v1.dependencies import AnyAuthenticated, CurrentUser

router = APIRouter()


# -----------------------------------------------------------------------------
# POST /auth/login
# -----------------------------------------------------------------------------
@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login",
    description=(
        "Authenticate with username and password. "
        "Returns a short-lived access token and a long-lived refresh token."
    ),
)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate a user and issue JWT tokens.
    device_info falls back to the User-Agent header if not provided in body.
    """
    device_info = payload.device_info or request.headers.get("user-agent")
    return await auth_service.login(
        db=db,
        user_name=payload.user_name,
        password=payload.password,
        device_info=device_info,
    )


# -----------------------------------------------------------------------------
# POST /auth/refresh
# -----------------------------------------------------------------------------
@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description=(
        "Exchange a valid refresh token for a new access token. "
        "The same refresh token is returned — token rotation is not yet implemented. "
        "When rotation is added, this endpoint will issue a new refresh token "
        "and revoke the old one on every call. "
        "Frontend clients should be built to handle a new refresh token being "
        "returned here, even if it is not changing today."
    ),
)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Issue a new access token using a valid refresh token."""
    return await auth_service.refresh(
        db=db,
        raw_refresh_token=payload.refresh_token,
    )


# -----------------------------------------------------------------------------
# POST /auth/logout
# -----------------------------------------------------------------------------
@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout current session",
    description=(
        "Revoke the provided refresh token. "
        "Only revokes tokens that belong to the authenticated user — "
        "silently ignores tokens that are not found or belong to another user. "
        "Idempotent — safe to call multiple times."
    ),
)
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> None:
    """
    Revoke a single refresh token (logout current device/session).
    Ownership is verified — only revokes tokens belonging to the current user.
    """
    await auth_service.logout(
        db=db,
        raw_refresh_token=payload.refresh_token,
        user_id=current_user.user_id,
    )


# -----------------------------------------------------------------------------
# POST /auth/logout-all
# -----------------------------------------------------------------------------
@router.post(
    "/logout-all",
    response_model=LogoutAllResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout all sessions",
    description=(
        "Revoke all active refresh tokens for the authenticated user. "
        "Effectively logs out from all devices."
    ),
)
async def logout_all(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> LogoutAllResponse:
    """Revoke all refresh tokens for the current user."""
    return await auth_service.logout_all(
        db=db,
        user_id=current_user.user_id,
    )


# -----------------------------------------------------------------------------
# GET /auth/me
# -----------------------------------------------------------------------------
@router.get(
    "/me",
    response_model=MeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description=(
        "Fetch the authenticated user's profile along with "
        "their full list of active role assignments."
    ),
)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> MeResponse:
    """Return the authenticated user's profile and roles."""
    return await auth_service.get_me(
        db=db,
        user_id=current_user.user_id,
    )