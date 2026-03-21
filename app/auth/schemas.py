from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import settings
from app.core.enums import RoleName


# =============================================================================
# Shared Field Definitions
# Reusable Annotated types — keeps field rules consistent across schemas.
# =============================================================================
UserNameField = Annotated[
    str,
    Field(
        min_length=3,
        max_length=50,
        description="Unique username — 3 to 50 characters.",
    ),
]

PasswordField = Annotated[
    str,
    Field(
        min_length=8,
        max_length=128,
        description="Password — minimum 8 characters.",
    ),
]

RefreshTokenField = Annotated[
    str,
    Field(min_length=1, description="Raw JWT refresh token."),
]

DeviceInfoField = Annotated[
    str | None,
    Field(
        default=None,
        max_length=512,
        description="Optional device label or user-agent string.",
    ),
]


# =============================================================================
# Request Schemas
# =============================================================================

class LoginRequest(BaseModel):
    """Payload for POST /auth/login."""

    model_config = ConfigDict(str_strip_whitespace=True)

    user_name: UserNameField
    password: PasswordField
    device_info: DeviceInfoField = None

    @field_validator("user_name", mode="before")
    @classmethod
    def lowercase_user_name(cls, v: str) -> str:
        """Normalize username to lowercase before validation."""
        return v.lower() if isinstance(v, str) else v


class RefreshTokenRequest(BaseModel):
    """Payload for POST /auth/refresh."""

    model_config = ConfigDict(str_strip_whitespace=True)

    refresh_token: RefreshTokenField


class LogoutRequest(BaseModel):
    """Payload for POST /auth/logout."""

    model_config = ConfigDict(str_strip_whitespace=True)

    refresh_token: RefreshTokenField


# =============================================================================
# Response Schemas
# All response schemas set from_attributes=True to allow direct construction
# from SQLAlchemy ORM model instances.
# =============================================================================

class RoleResponse(BaseModel):
    """Single role assignment with its school/branch scope."""

    model_config = ConfigDict(from_attributes=True)

    role_id: int
    role_name: RoleName
    school_id: int | None
    branch_id: int | None
    is_active: bool
    assigned_at: datetime


class UserResponse(BaseModel):
    """
    Public-safe user representation.
    Never includes password_hash or any internal fields.
    """

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    user_name: str
    email: str | None
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MeResponse(BaseModel):
    """
    Extended user response for GET /auth/me.
    Includes the full list of active role assignments.
    """

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    user_name: str
    email: str | None
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    roles: list[RoleResponse]


class TokenResponse(BaseModel):
    """
    Returned on successful login or token refresh.
    expires_in is computed from settings — always reflects actual expiry.
    """

    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60


class LogoutAllResponse(BaseModel):
    """Returned on POST /auth/logout-all — confirms how many tokens were revoked."""

    model_config = ConfigDict(from_attributes=True)

    revoked_count: int
    message: str = "All sessions have been logged out successfully."