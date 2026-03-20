from typing import Any
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_access_token, extract_user_id
from app.core.enums import RoleName, BRANCH_SCOPED_ROLES, SCHOOL_SCOPED_ROLES
from app.core.exceptions import (
    InvalidTokenError,
    UnauthorizedError,
    ForbiddenError,
    InsufficientRoleError,
    BranchScopeError,
    SchoolScopeError,
)


# -----------------------------------------------------------------------------
# HTTP Bearer Scheme
# Extracts the Bearer token from the Authorization header.
# auto_error=False — we raise our own exceptions instead of FastAPI's default
# 403, giving consistent error responses across the app.
# -----------------------------------------------------------------------------
bearer_scheme = HTTPBearer(auto_error=False)


# -----------------------------------------------------------------------------
# Current User Model
# A lightweight dataclass — not an ORM model — that carries everything
# downstream route handlers and services need about the authenticated user.
# Avoids a DB round-trip on every request.
# -----------------------------------------------------------------------------
class CurrentUser:
    def __init__(self, payload: dict[str, Any]):
        self.user_id: int = extract_user_id(payload)
        self.user_name: str = payload.get("user_name", "")
        self.roles: list[dict[str, Any]] = payload.get("roles", [])

    def has_role(self, role_name: RoleName) -> bool:
        """Return True if the user holds the given role (any scope)."""
        return any(r["role_name"] == role_name.value for r in self.roles)

    def has_any_role(self, *role_names: RoleName) -> bool:
        """Return True if the user holds at least one of the given roles."""
        role_values = {r.value for r in role_names}
        return any(r["role_name"] in role_values for r in self.roles)

    def has_school_access(self, school_id: int) -> bool:
        """
        Return True if the user has any role scoped to the given school.
        SUPER_ADMIN passes automatically (no school scope needed).
        """
        if self.has_role(RoleName.SUPER_ADMIN):
            return True
        return any(r.get("school_id") == school_id for r in self.roles)

    def has_branch_access(self, school_id: int, branch_id: int) -> bool:
        """
        Return True if the user has any role scoped to the given branch.
        SUPER_ADMIN and SCHOOL_ADMIN (for their school) pass automatically.
        """
        if self.has_role(RoleName.SUPER_ADMIN):
            return True
        if any(
            r["role_name"] == RoleName.SCHOOL_ADMIN.value
            and r.get("school_id") == school_id
            for r in self.roles
        ):
            return True
        return any(
            r.get("school_id") == school_id and r.get("branch_id") == branch_id
            for r in self.roles
        )

    def get_accessible_school_ids(self) -> list[int] | None:
        """
        Return list of school_ids the user can access.
        Returns None for SUPER_ADMIN (meaning all schools).
        """
        if self.has_role(RoleName.SUPER_ADMIN):
            return None
        return list({
            r["school_id"]
            for r in self.roles
            if r.get("school_id") is not None
        })

    def get_accessible_branch_ids(self, school_id: int) -> list[int] | None:
        """
        Return list of branch_ids the user can access within a school.
        Returns None for SUPER_ADMIN and SCHOOL_ADMIN (meaning all branches).
        """
        if self.has_role(RoleName.SUPER_ADMIN):
            return None
        if any(
            r["role_name"] == RoleName.SCHOOL_ADMIN.value
            and r.get("school_id") == school_id
            for r in self.roles
        ):
            return None
        return list({
            r["branch_id"]
            for r in self.roles
            if r.get("school_id") == school_id and r.get("branch_id") is not None
        })

    def __repr__(self) -> str:
        return f"<CurrentUser user_id={self.user_id} user_name={self.user_name}>"


# -----------------------------------------------------------------------------
# Core Dependencies
# -----------------------------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """
    Extract and validate the Bearer token from the Authorization header.
    Returns a CurrentUser instance populated from the token payload.

    Raises:
        UnauthorizedError : if no token is provided
        InvalidTokenError : if the token is malformed or expired
    """
    if credentials is None:
        raise UnauthorizedError(detail="Authorization header is missing.")

    payload = decode_access_token(credentials.credentials)
    return CurrentUser(payload)


async def get_current_active_user(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Extends get_current_user — placeholder for is_active checks.
    The is_active flag lives on the DB user record. If you need to
    enforce it on every request, add a DB lookup here.
    For most routes, the token's existence is sufficient.
    """
    return current_user


# -----------------------------------------------------------------------------
# Role Guard Factory
# Returns a FastAPI dependency that enforces role-based access.
#
# Usage:
#   @router.get("/admin")
#   async def admin_route(
#       current_user: CurrentUser = Depends(require_roles(RoleName.SUPER_ADMIN))
#   ):
# -----------------------------------------------------------------------------
def require_roles(*required_roles: RoleName):
    """
    Dependency factory — enforces that the current user holds
    at least one of the required roles.

    Args:
        *required_roles : one or more RoleName values

    Returns:
        A FastAPI dependency that yields CurrentUser or raises ForbiddenError
    """
    async def dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if not current_user.has_any_role(*required_roles):
            role_names = ", ".join(r.value for r in required_roles)
            raise InsufficientRoleError(required_role=role_names)
        return current_user

    return dependency


# -----------------------------------------------------------------------------
# Scope Guard Factory
# Enforces school/branch-level tenant isolation on top of role checks.
#
# Usage in routes that have school_id / branch_id path params:
#   @router.get("/{school_id}/branches/{branch_id}")
#   async def get_branch(
#       school_id: int,
#       branch_id: int,
#       current_user: CurrentUser = Depends(require_branch_access()),
#   ):
#       if not current_user.has_branch_access(school_id, branch_id):
#           raise BranchScopeError()
# -----------------------------------------------------------------------------
def require_school_access():
    """
    Dependency that ensures the current user is authenticated.
    Actual school_id scope check is done in the route or service
    using current_user.has_school_access(school_id).
    """
    async def dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        return current_user

    return dependency


def require_branch_access():
    """
    Dependency that ensures the current user is authenticated.
    Actual branch scope check is done in the route or service
    using current_user.has_branch_access(school_id, branch_id).
    """
    async def dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        return current_user

    return dependency


# -----------------------------------------------------------------------------
# Convenience — pre-built role dependencies for common patterns
# -----------------------------------------------------------------------------

# Only SUPER_ADMIN
SuperAdminRequired = Depends(require_roles(RoleName.SUPER_ADMIN))

# SUPER_ADMIN or SCHOOL_ADMIN
SchoolAdminRequired = Depends(
    require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN)
)

# SUPER_ADMIN, SCHOOL_ADMIN, or BRANCH_ADMIN
BranchAdminRequired = Depends(
    require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN)
)

# Any authenticated user (just needs a valid token)
AnyAuthenticated = Depends(get_current_user)
