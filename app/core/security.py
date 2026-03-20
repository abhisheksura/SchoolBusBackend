import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError


# -----------------------------------------------------------------------------
# Password Hashing
# bcrypt is CPU-bound — wrapping in run_in_executor prevents it from
# blocking the event loop during login / registration.
# -----------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using bcrypt (non-blocking)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, pwd_context.hash, plain_password
    )


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash (non-blocking)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, pwd_context.verify, plain_password, hashed_password
    )


# -----------------------------------------------------------------------------
# JWT Token Payload Structure
#
# Access token payload:
# {
#     "sub"        : "42",               # user_id as string
#     "user_name"  : "john_doe",
#     "roles"      : [                   # all active roles for the user
#         {
#             "role_name"  : "BRANCH_ADMIN",
#             "school_id"  : 1,
#             "branch_id"  : 3
#         }
#     ],
#     "type"       : "access",
#     "iat"        : 1710000000,         # issued at (UTC)
#     "exp"        : 1710001800,         # expires at (UTC)
# }
#
# Refresh token payload:
# {
#     "sub"  : "42",
#     "type" : "refresh",
#     "iat"  : 1710000000,
#     "exp"  : 1712592000,
# }
# -----------------------------------------------------------------------------

TokenPayload = dict[str, Any]


def _build_payload(
    data: dict[str, Any],
    expires_delta: timedelta,
    token_type: str,
) -> TokenPayload:
    """Build a JWT payload with expiry and token type."""
    now = datetime.now(timezone.utc)
    return {
        **data,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }


def create_access_token(
    user_id: int,
    user_name: str,
    roles: list[dict[str, Any]],
) -> str:
    """
    Create a short-lived JWT access token.

    Embeds user_id, user_name, and full role list (with school/branch scope)
    so every request can be authorized without a DB lookup.

    Args:
        user_id   : PK from users table
        user_name : unique username
        roles     : list of dicts with role_name, school_id, branch_id

    Returns:
        Encoded JWT string
    """
    payload = _build_payload(
        data={
            "sub": str(user_id),
            "user_name": user_name,
            "roles": roles,
        },
        expires_delta=timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        ),
        token_type="access",
    )
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: int) -> str:
    """
    Create a long-lived JWT refresh token.

    Contains only the user_id — no role data.
    The full access token is reissued on refresh via a DB lookup.

    Args:
        user_id : PK from users table

    Returns:
        Encoded JWT string
    """
    payload = _build_payload(
        data={"sub": str(user_id)},
        expires_delta=timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh",
    )
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str, expected_type: str) -> TokenPayload:
    """
    Decode and validate a JWT token.

    Validates:
      - Signature using JWT_SECRET_KEY
      - Expiry (raises TokenExpiredError if expired)
      - Token type matches expected_type (raises InvalidTokenError if not)

    Args:
        token         : raw JWT string from Authorization header
        expected_type : "access" or "refresh"

    Returns:
        Decoded payload dict

    Raises:
        TokenExpiredError  : if the token has expired
        InvalidTokenError  : if the token is malformed or wrong type
    """
    try:
        payload: TokenPayload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        # jose raises ExpiredSignatureError (subclass of JWTError) for expiry
        if "expired" in str(exc).lower():
            raise TokenExpiredError()
        raise InvalidTokenError()

    if payload.get("type") != expected_type:
        raise InvalidTokenError(
            detail=f"Expected '{expected_type}' token but received '{payload.get('type')}'."
        )

    return payload


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate an access token. Returns the full payload."""
    return decode_token(token, expected_type="access")


def decode_refresh_token(token: str) -> TokenPayload:
    """Decode and validate a refresh token. Returns the full payload."""
    return decode_token(token, expected_type="refresh")


def extract_user_id(payload: TokenPayload) -> int:
    """
    Extract and return user_id (int) from a decoded token payload.

    Raises:
        InvalidTokenError : if 'sub' is missing or not a valid integer
    """
    sub = payload.get("sub")
    if not sub:
        raise InvalidTokenError(detail="Token is missing subject claim.")
    try:
        return int(sub)
    except (ValueError, TypeError):
        raise InvalidTokenError(detail="Token subject claim is invalid.")
