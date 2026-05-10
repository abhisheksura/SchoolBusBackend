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
    """
    Lightweight auth context populated entirely from the JWT payload.
    No DB round-trip — everything needed for authorization lives in the token.

    Primary claims (top-level in JWT):
        role      — the single role the user logged in as (from LoginRequest.role)
        school_id — None for SUPER_ADMIN, set for all others
        branch_id — None for SUPER_ADMIN + SCHOOL_ADMIN, set for branch-scoped roles

    These are also used by get_tenant_db() to set PostgreSQL RLS session variables.
    """

    def __init__(self, payload: dict[str, Any]):
        self.user_id   : int             = extract_user_id(payload)
        self.user_name : str             = payload.get("user_name", "")
        self.role      : str             = payload.get("role", "")
        self.school_id : int | None      = payload.get("school_id")     # None = SUPER_ADMIN
        self.branch_id : int | None      = payload.get("branch_id")     # None = SUPER/SCHOOL ADMIN
        self.driver_id : int | None      = payload.get("driver_id")     # Set only for DRIVER role
        self.roles     : list[dict[str, Any]] = payload.get("roles", [])

    # -------------------------------------------------------------------------
    # Role checks — uses primary role (single declared login role)
    # -------------------------------------------------------------------------
    def has_role(self, role_name: RoleName) -> bool:
        """Return True if the user's primary login role matches."""
        return self.role == role_name.value

    def has_any_role(self, *role_names: RoleName) -> bool:
        """Return True if the primary login role is one of the given roles."""
        return self.role in {r.value for r in role_names}

    # -------------------------------------------------------------------------
    # Scope checks — derived from primary JWT claims
    # -------------------------------------------------------------------------
    def has_school_access(self, school_id: int) -> bool:
        """
        Return True if the user has access to the given school.
        SUPER_ADMIN (school_id=None in JWT) always passes.
        """
        if self.school_id is None:           # SUPER_ADMIN
            return True
        return self.school_id == school_id

    def has_branch_access(self, school_id: int, branch_id: int) -> bool:
        """
        Return True if the user has access to the given branch.
        SUPER_ADMIN and SCHOOL_ADMIN (branch_id=None in JWT) always pass
        for any branch within their school.
        """
        if self.school_id is None:           # SUPER_ADMIN
            return True
        if self.school_id != school_id:
            return False
        if self.branch_id is None:           # SCHOOL_ADMIN — all branches
            return True
        return self.branch_id == branch_id

    # -------------------------------------------------------------------------
    # Scope accessors — used by services to build tenant-filtered queries
    # None means "all" — no filter applied (SUPER_ADMIN / SCHOOL_ADMIN)
    # -------------------------------------------------------------------------
    def get_accessible_school_ids(self) -> list[int] | None:
        """
        None → SUPER_ADMIN, access all schools.
        [school_id] → everyone else, access only their school.
        """
        if self.school_id is None:           # SUPER_ADMIN
            return None
        return [self.school_id]

    def get_accessible_branch_ids(self, school_id: int) -> list[int] | None:
        """
        None → SUPER_ADMIN or SCHOOL_ADMIN, access all branches in school.
        [branch_id] → branch-scoped roles, access only their branch.
        [] → user has no access to this school at all.
        """
        if self.school_id is None:           # SUPER_ADMIN
            return None
        if self.school_id != school_id:      # wrong school entirely
            return []
        if self.branch_id is None:           # SCHOOL_ADMIN — all branches
            return None
        return [self.branch_id]

    def __repr__(self) -> str:
        return (
            f"<CurrentUser user_id={self.user_id} role={self.role} "
            f"school_id={self.school_id} branch_id={self.branch_id} driver_id={self.driver_id}>"
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