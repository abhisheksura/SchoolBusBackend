import hashlib
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import repository as auth_repo
from app.drivers import repository as driver_repo
from app.auth.models import UserRole
from app.auth.schemas import LogoutAllResponse, MeResponse, RoleResponse, TokenResponse, UserResponse
from app.core.config import settings
from app.core.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    RefreshTokenRevokedError,
    TokenExpiredError,
    UnauthorizedError,
)
from app.core.enums import PLATFORM_ROLES, RoleName
from app.core.utils import utcnow
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    extract_user_id,
    verify_password,
)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _hash_token(raw_token: str) -> str:
    """
    SHA-256 hash a raw JWT string.
    Used before storing or looking up refresh tokens in the DB.
    Never store the raw token — only ever store this hash.
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _build_roles_payload(
    user_roles: list[UserRole],
    driver_id: int | None = None,
) -> list[dict]:
    """
    Convert UserRole ORM instances into the dict format
    embedded in the JWT access token payload.

    driver_id is passed for DRIVER role logins so the token carries
    the driver PK. Enables trip ownership checks without a DB lookup.
    None for all non-DRIVER roles.

    Args:
        user_roles : list of active UserRole ORM instances
        driver_id  : PK from drivers table — set for DRIVER role only

    Returns:
        List of dicts with role_name, school_id, branch_id, driver_id
    """
    return [
        {
            "role_name": role.role_name.value,
            "school_id": role.school_id,
            "branch_id": role.branch_id,
            "driver_id": driver_id,
        }
        for role in user_roles
    ]


def _compute_refresh_token_expiry() -> datetime:
    """
    Compute the refresh token expiry datetime in UTC.
    Uses utcnow() from core.utils — returns timezone-aware datetime.
    Compatible with PostgreSQL TIMESTAMPTZ columns.
    """
    return utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)


# -----------------------------------------------------------------------------
# Service Functions
# -----------------------------------------------------------------------------

async def login(
    db: AsyncSession,
    user_name: str,
    password: str,
    platform: str,
    role: RoleName,
    device_info: str | None = None,
) -> TokenResponse:
    """
    Authenticate a user and issue access + refresh tokens.

    Steps:
        1. Fetch user by username
        2. Verify password
        3. Check user is active
        4. Check user holds the exact declared role (active)
        5. Build roles payload — embed only the declared role's assignments
        6. Create JWT access token
        7. Create JWT refresh token
        8. Hash raw refresh token and persist to DB
        9. Return TokenResponse

    The platform + role combination is pre-validated by LoginRequest at the
    Pydantic layer (422 if role is not permitted on platform). This step only
    checks whether the user actually holds that role in the DB.

    All credential errors raise InvalidCredentialsError — never reveal
    which specific check failed.

    Args:
        db          : active async database session
        user_name   : username submitted in the login request
        password    : plain-text password submitted in the login request
        platform    : "web" or "mobile"
        role        : the exact RoleName the user is logging in as
        device_info : optional device label or user-agent string

    Returns:
        TokenResponse with access_token, refresh_token, token_type, expires_in

    Raises:
        InvalidCredentialsError : if user not found, inactive, password wrong,
                                  or user does not hold the declared role
    """
    # -- Step 1: Fetch user with roles in one efficient round-trip -------------
    try:
        user = await auth_repo.get_user_with_roles_by_user_name(db, user_name)
    except Exception:
        raise InvalidCredentialsError()

    # -- Step 2: Verify password ----------------------------------------------
    password_valid = await verify_password(password, user.password_hash)
    if not password_valid:
        raise InvalidCredentialsError()

    # -- Step 3: Check user is active -----------------------------------------
    if not user.is_active:
        raise InvalidCredentialsError()

    # -- Step 4: Exact role check ---------------------------------------------
    # The user must hold the declared role (active). This catches:
    #   - SUPER_ADMIN logging in as SCHOOL_ADMIN (doesn't hold that role)
    #   - SCHOOL_ADMIN logging in as SUPER_ADMIN (doesn't hold that role)
    #   - Any user claiming a role they were never assigned
    matching_roles = [
        r for r in user.user_roles
        if r.is_active and RoleName(r.role_name) == role
    ]
    if not matching_roles:
        raise InvalidCredentialsError(
            detail="This account does not have the specified role."
        )

    # -- Step 5: Build roles payload — only the declared role's assignments ---
    # A user with multiple roles (e.g. SCHOOL_ADMIN in two schools) gets all
    # assignments for the declared role embedded in the token. Assignments for
    # other roles are excluded.
    #
    # For DRIVER role: look up driver_id so the token carries the driver PK.
    # This lets downstream trip endpoints verify ownership (start/end/cancel)
    # without an extra DB round-trip on every action.
    driver_id: int | None = None
    if role == RoleName.DRIVER:
        driver = await driver_repo.get_driver_by_user_id_or_none(db, user.user_id)
        driver_id = driver.driver_id if driver else None

    roles_payload = _build_roles_payload(matching_roles, driver_id=driver_id)

    # -- Step 6: Create access token ------------------------------------------
    access_token = create_access_token(
        user_id=user.user_id,
        user_name=user.user_name,
        roles=roles_payload,
    )

    # -- Step 7: Create refresh token -----------------------------------------
    raw_refresh_token = create_refresh_token(user_id=user.user_id)

    # -- Step 8: Hash and persist refresh token -------------------------------
    token_hash = _hash_token(raw_refresh_token)
    expires_at = _compute_refresh_token_expiry()

    await auth_repo.create_refresh_token(
        db=db,
        user_id=user.user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        device_info=device_info,
    )

    # -- Step 9: Return token response ----------------------------------------
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
    )


async def refresh(
    db: AsyncSession,
    raw_refresh_token: str,
) -> TokenResponse:
    """
    Validate a refresh token and issue a new access token.

    Steps:
        1. Decode and validate the JWT refresh token
        2. Extract user_id from payload
        3. Hash raw token and look up in DB
        4. Check token is not revoked
        5. Check token is not expired
        6. Fetch user and verify still active
        7. Load fresh roles
        8. Issue new access token
        9. Return TokenResponse with same refresh token (no rotation for now)

    Args:
        db                : active async database session
        raw_refresh_token : raw JWT refresh token from the client

    Returns:
        TokenResponse with new access_token and same refresh_token

    Raises:
        InvalidTokenError       : if token is malformed or not found in DB
        TokenExpiredError       : if token has passed expiry
        RefreshTokenRevokedError: if token has been revoked
        UnauthorizedError       : if associated user is inactive
    """
    # -- Step 1 & 2: Decode JWT and extract user_id ---------------------------
    try:
        payload = decode_refresh_token(raw_refresh_token)
        user_id = extract_user_id(payload)
    except (InvalidTokenError, TokenExpiredError):
        raise

    # -- Step 3: Look up token in DB ------------------------------------------
    token_hash = _hash_token(raw_refresh_token)
    db_token = await auth_repo.get_refresh_token_by_token_hash(db, token_hash)

    # -- Step 4: Check not revoked --------------------------------------------
    if not db_token.is_active:
        raise RefreshTokenRevokedError()

    # -- Step 5: Check not expired --------------------------------------------
    if db_token.is_expired:
        raise TokenExpiredError()

    # -- Step 6: Fetch user and verify active ---------------------------------
    user = await auth_repo.get_user_by_user_id(db, user_id)
    if not user.is_active:
        raise UnauthorizedError(detail="User account is inactive.")

    # -- Step 7: Load fresh roles ---------------------------------------------
    user_roles = await auth_repo.get_all_active_roles_by_user_id(db, user_id)
    roles_payload = _build_roles_payload(user_roles)

    # -- Step 8: Issue new access token ---------------------------------------
    new_access_token = create_access_token(
        user_id=user.user_id,
        user_name=user.user_name,
        roles=roles_payload,
    )

    # -- Step 9: Return with same refresh token (no rotation) -----------------
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=raw_refresh_token,
    )


async def logout(
    db: AsyncSession,
    raw_refresh_token: str,
    user_id: int,
) -> None:
    """
    Revoke a single refresh token (logout current device/session).

    Verifies the token belongs to the requesting user before revoking.
    Silently succeeds if the token is not found or does not belong to
    this user — idempotent by design, client can always safely call logout.

    Args:
        db                : active async database session
        raw_refresh_token : raw JWT refresh token to revoke
        user_id           : user_id from the JWT access token —
                            used to verify token ownership before revoking

    Returns:
        None
    """
    token_hash = _hash_token(raw_refresh_token)

    try:
        token = await auth_repo.get_refresh_token_by_token_hash(db, token_hash)

        # Ownership check — only revoke if the token belongs to this user.
        # Silently ignore if it belongs to someone else rather than raising
        # an error — avoids leaking whether the token exists for another user.
        if token.user_id != user_id:
            return

        await auth_repo.revoke_refresh_token_by_token_hash(db, token_hash)

    except InvalidTokenError:
        # Token not found — treat as already logged out, no error
        pass


async def logout_all(
    db: AsyncSession,
    user_id: int,
) -> LogoutAllResponse:
    """
    Revoke all active refresh tokens for a user (logout all devices).

    Args:
        db      : active async database session
        user_id : primary key of the user to log out everywhere

    Returns:
        LogoutAllResponse with count of revoked tokens
    """
    revoked_count = await auth_repo.revoke_all_refresh_tokens_by_user_id(
        db, user_id
    )
    return LogoutAllResponse(revoked_count=revoked_count)


async def get_me(
    db: AsyncSession,
    user_id: int,
) -> MeResponse:
    """
    Fetch the authenticated user's profile along with their active roles.
    Uses get_user_with_roles_by_user_id — loads user + roles in one
    efficient two-query round-trip (select user + selectinload roles).

    Args:
        db      : active async database session
        user_id : primary key extracted from the JWT access token

    Returns:
        MeResponse with user details and full list of active role assignments

    Raises:
        UserNotFoundError : if no user exists with the given user_id
    """
    user = await auth_repo.get_user_with_roles_by_user_id(db, user_id)

    return MeResponse(
        user_id=user.user_id,
        user_name=user.user_name,
        email=user.email,
        phone=user.phone,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[
            RoleResponse(
                role_id=role.role_id,
                role_name=role.role_name,
                school_id=role.school_id,
                branch_id=role.branch_id,
                is_active=role.is_active,
                assigned_at=role.assigned_at,
            )
            for role in user.user_roles
        ],
    )