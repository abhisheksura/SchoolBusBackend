from datetime import datetime

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken, Role, User, UserRole
from app.core.exceptions import (
    InvalidTokenError,
    UserNotFoundError,
)


# =============================================================================
# User Queries
# =============================================================================

async def get_user_by_user_name(db: AsyncSession, user_name: str) -> User:
    """
    Fetch a user by their unique username.

    Args:
        db        : active async database session
        user_name : unique username to look up

    Returns:
        User ORM instance

    Raises:
        UserNotFoundError : if no user exists with the given username
    """
    result = await db.execute(
        select(User).where(User.user_name == user_name)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise UserNotFoundError(identifier=user_name)
    return user


async def get_user_by_user_id(db: AsyncSession, user_id: int) -> User:
    """
    Fetch a user by their primary key.

    Args:
        db      : active async database session
        user_id : primary key of the user

    Returns:
        User ORM instance

    Raises:
        UserNotFoundError : if no user exists with the given user_id
    """
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise UserNotFoundError(identifier=user_id)
    return user


async def get_user_by_email_or_none(
    db: AsyncSession,
    email: str,
) -> User | None:
    """
    Fetch a user by email address.
    Returns None if not found — caller decides whether to raise.

    Args:
        db    : active async database session
        email : email address to look up

    Returns:
        User ORM instance or None
    """
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def get_user_by_phone_or_none(
    db: AsyncSession,
    phone: str,
) -> User | None:
    """
    Fetch a user by phone number.
    Returns None if not found — caller decides whether to raise.

    Args:
        db    : active async database session
        phone : phone number to look up

    Returns:
        User ORM instance or None
    """
    result = await db.execute(
        select(User).where(User.phone == phone)
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    user_name: str,
    password_hash: str,
    email: str | None = None,
    phone: str | None = None,
) -> User:
    """
    Insert a new user record.

    Args:
        db            : active async database session
        user_name     : unique username
        password_hash : bcrypt hash of the plain-text password
        email         : optional email address
        phone         : optional phone number

    Returns:
        Newly created User ORM instance
    """
    user = User(
        user_name=user_name,
        password_hash=password_hash,
        email=email,
        phone=phone,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user_password_by_user_id(
    db: AsyncSession,
    user_id: int,
    new_password_hash: str,
) -> User:
    """
    Update the password hash for a user.

    Args:
        db                : active async database session
        user_id           : primary key of the user
        new_password_hash : bcrypt hash of the new password

    Returns:
        Updated User ORM instance

    Raises:
        UserNotFoundError : if no user exists with the given user_id
    """
    await db.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(
            password_hash=new_password_hash,
            updated_at=func.now(),
        )
    )
    await db.flush()
    return await get_user_by_user_id(db, user_id)


async def deactivate_user_by_user_id(
    db: AsyncSession,
    user_id: int,
) -> User:
    """
    Soft-delete a user by setting is_active = False.
    Never hard-deletes — preserves all related records.

    Args:
        db      : active async database session
        user_id : primary key of the user to deactivate

    Returns:
        Updated User ORM instance

    Raises:
        UserNotFoundError : if no user exists with the given user_id
    """
    await db.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(is_active=False, updated_at=func.now())
    )
    await db.flush()
    return await get_user_by_user_id(db, user_id)


# =============================================================================
# Role Queries
# =============================================================================

async def get_all_active_roles_by_user_id(
    db: AsyncSession,
    user_id: int,
) -> list[UserRole]:
    """
    Fetch all active role assignments for a user.
    Used to build the roles payload embedded in the JWT access token.

    Args:
        db      : active async database session
        user_id : primary key of the user

    Returns:
        List of active UserRole ORM instances (empty list if none)
    """
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.is_active == True,
        )
    )
    return list(result.scalars().all())


async def get_user_role_by_user_role_id(
    db: AsyncSession,
    user_role_id: int,
) -> UserRole:
    """
    Fetch a single role assignment by its primary key.

    Args:
        db           : active async database session
        user_role_id : primary key of the user_role record

    Returns:
        UserRole ORM instance

    Raises:
        UserNotFoundError : if no user_role exists with the given id
    """
    result = await db.execute(
        select(UserRole).where(UserRole.user_role_id == user_role_id)
    )
    user_role = result.scalar_one_or_none()
    if not user_role:
        raise UserNotFoundError(identifier=user_role_id)
    return user_role


async def assign_role_to_user(
    db: AsyncSession,
    user_id: int,
    role_id: int,
    role_name: str,
    school_id: int | None = None,
    branch_id: int | None = None,
) -> UserRole:
    """
    Assign a role to a user with the appropriate school/branch scope.
    Scoping rules:
        SUPER_ADMIN  → school_id=None, branch_id=None
        SCHOOL_ADMIN → school_id=int,  branch_id=None
        others       → school_id=int,  branch_id=int

    Args:
        db        : active async database session
        user_id   : primary key of the user
        role_id   : primary key of the role
        role_name : RoleName enum value
        school_id : school scope (None for SUPER_ADMIN)
        branch_id : branch scope (None for SUPER_ADMIN and SCHOOL_ADMIN)

    Returns:
        Newly created UserRole ORM instance
    """
    user_role = UserRole(
        user_id=user_id,
        role_id=role_id,
        role_name=role_name,
        school_id=school_id,
        branch_id=branch_id,
    )
    db.add(user_role)
    await db.flush()
    await db.refresh(user_role)
    return user_role


async def revoke_user_role_by_user_role_id(
    db: AsyncSession,
    user_role_id: int,
) -> UserRole:
    """
    Deactivate a role assignment by setting is_active = False.

    Args:
        db           : active async database session
        user_role_id : primary key of the user_role record to revoke

    Returns:
        Updated UserRole ORM instance

    Raises:
        UserNotFoundError : if no user_role exists with the given id
    """
    await db.execute(
        update(UserRole)
        .where(UserRole.user_role_id == user_role_id)
        .values(is_active=False, updated_at=func.now())
    )
    await db.flush()
    return await get_user_role_by_user_role_id(db, user_role_id)


# =============================================================================
# Refresh Token Queries
# =============================================================================

async def create_refresh_token(
    db: AsyncSession,
    user_id: int,
    token_hash: str,
    expires_at: datetime,
    device_info: str | None = None,
) -> RefreshToken:
    """
    Insert a new refresh token record.
    Always stores the SHA-256 hash — never the raw token.

    Args:
        db          : active async database session
        user_id     : primary key of the user this token belongs to
        token_hash  : SHA-256 hash of the raw JWT refresh token
        expires_at  : token expiry timestamp (UTC)
        device_info : optional user-agent or device label string

    Returns:
        Newly created RefreshToken ORM instance
    """
    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        device_info=device_info,
    )
    db.add(refresh_token)
    await db.flush()
    await db.refresh(refresh_token)
    return refresh_token


async def get_refresh_token_by_token_hash(
    db: AsyncSession,
    token_hash: str,
) -> RefreshToken:
    """
    Fetch a refresh token record by its SHA-256 hash.

    Args:
        db         : active async database session
        token_hash : SHA-256 hash of the raw JWT refresh token

    Returns:
        RefreshToken ORM instance

    Raises:
        InvalidTokenError : if no token record matches the given hash
    """
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()
    if not token:
        raise InvalidTokenError(detail="Refresh token not recognised.")
    return token


async def get_all_active_refresh_tokens_by_user_id(
    db: AsyncSession,
    user_id: int,
) -> list[RefreshToken]:
    """
    Fetch all non-revoked refresh tokens for a user.

    Args:
        db      : active async database session
        user_id : primary key of the user

    Returns:
        List of active RefreshToken ORM instances (empty list if none)
    """
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    return list(result.scalars().all())


async def revoke_refresh_token_by_token_hash(
    db: AsyncSession,
    token_hash: str,
) -> RefreshToken:
    """
    Revoke a single refresh token by setting revoked_at to now (UTC).

    Args:
        db         : active async database session
        token_hash : SHA-256 hash of the raw JWT refresh token

    Returns:
        Updated RefreshToken ORM instance

    Raises:
        InvalidTokenError : if no token record matches the given hash
    """
    now = datetime.utcnow()
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .values(revoked_at=now)
    )
    await db.flush()
    return await get_refresh_token_by_token_hash(db, token_hash)


async def revoke_all_refresh_tokens_by_user_id(
    db: AsyncSession,
    user_id: int,
) -> int:
    """
    Revoke all active refresh tokens for a user (logout all devices).
    Sets revoked_at = now on every non-revoked token for this user.

    Args:
        db      : active async database session
        user_id : primary key of the user

    Returns:
        Count of tokens that were revoked
    """
    # Fetch active tokens first to get the count
    active_tokens = await get_all_active_refresh_tokens_by_user_id(db, user_id)
    count = len(active_tokens)

    if count > 0:
        now = datetime.utcnow()
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await db.flush()

    return count