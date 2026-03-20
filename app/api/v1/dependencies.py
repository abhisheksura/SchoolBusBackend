from typing import Any
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token, extract_user_id
from app.core.enums import RoleName, BRANCH_SCOPED_ROLES, SCHOOL_SCOPED_ROLES
from app.core.exceptions import (
    UnauthorizedError,
    InsufficientRoleError,
    BranchScopeError,
    SchoolScopeError,
)


# -----------------------------------------------------------------------------
# HTTP Bearer Scheme
# Extracts the Bearer token from the Authorization header.
# auto_error=False — we raise our own UnauthorizedError (401) instead of
# FastAPI's default 403, giving consistent error responses across the app.
# -----------------------------------------------------------------------------
bearer_scheme = HTTPBearer(auto_error=False)


# -----------------------------------------------------------------------------
# CurrentUser
# A lightweight class populated entirely from the JWT payload.
# No DB round-trip — everything needed for authorization lives in the token.
# -----------------------------------------------------------------------------
class CurrentUser:
    def __init__(self, payload: dict[str, Any]):
        self.user_id: int = extract_user_id(payload)
        self.user_name: str = payload.get("user_name", "")
        self.roles: list[dict[str, Any]] = payload.get("roles", [])

    # -------------------------------------------------------------------------
    # Role checks
    # -------------------------------------------------------------------------
    def has_role(self, role_name: RoleName) -> bool:
        """Return True if the user holds the given role (any scope)."""
        return any(r["role_name"] == role_name.value for r in self.roles)

    def has_any_role(self, *role_names: RoleName) -> bool:
        """Return True if the user holds at least one of the given roles."""
        role_values = {r.value for r in role_names}
        return any(r["role_name"] in role_values for r in self.roles)

    # -------------------------------------------------------------------------
    # Scope checks
    # Mirrors the CHECK constraint logic in user_roles:
    #   SUPER_ADMIN  → no scope restriction
    #   SCHOOL_ADMIN → school-level scope, all branches within
    #   others       → must match both school_id AND branch_id
    # -------------------------------------------------------------------------
    def has_school_access(self, school_id: int) -> bool:
        """
        Return True if the user has access to the given school.
        SUPER_ADMIN passes automatically.
        """
        if self.has_role(RoleName.SUPER_ADMIN):
            return True
        return any(r.get("school_id") == school_id for r in self.roles)

    def has_branch_access(self, school_id: int, branch_id: int) -> bool:
        """
        Return True if the user has access to the given branch.
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

    # -------------------------------------------------------------------------
    # Scope accessors
    # Used by services to build tenant-filtered queries.
    # None means "all" — used for SUPER_ADMIN / SCHOOL_ADMIN.
    # -------------------------------------------------------------------------
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
            if r.get("school_id") == school_id
            and r.get("branch_id") is not None
        })

    def __repr__(self) -> str:
        return (
            f"<CurrentUser user_id={self.user_id} user_name={self.user_name}>"
        )


# -----------------------------------------------------------------------------
# Core Auth Dependency
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


# -----------------------------------------------------------------------------
# Role Guard Factory
# Returns a FastAPI dependency that enforces role-based access.
#
# Usage:
#   # as a route dependency (no access to current_user in handler)
#   @router.delete("/{id}", dependencies=[Depends(require_roles(RoleName.SUPER_ADMIN))])
#
#   # as a typed parameter (access to current_user in handler)
#   async def create_bus(
#       current_user: CurrentUser = Depends(require_roles(RoleName.BRANCH_ADMIN))
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
# Scope Guard Helpers
# Used inside route handlers to enforce tenant isolation after
# the role check has passed.
#
# Usage in route handler:
#   async def get_branch(
#       school_id: int,
#       branch_id: int,
#       current_user: CurrentUser = Depends(get_current_user),
#   ):
#       if not current_user.has_branch_access(school_id, branch_id):
#           raise BranchScopeError()
# -----------------------------------------------------------------------------
def check_school_access(current_user: CurrentUser, school_id: int) -> None:
    """Raise SchoolScopeError if user has no access to the given school."""
    if not current_user.has_school_access(school_id):
        raise SchoolScopeError()


def check_branch_access(
    current_user: CurrentUser,
    school_id: int,
    branch_id: int,
) -> None:
    """Raise BranchScopeError if user has no access to the given branch."""
    if not current_user.has_branch_access(school_id, branch_id):
        raise BranchScopeError()


# -----------------------------------------------------------------------------
# Pre-built convenience dependencies
# Import and use directly in router files.
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

# Any authenticated user (valid token, any role)
AnyAuthenticated = Depends(get_current_user)
