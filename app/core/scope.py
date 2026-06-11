# src/core/security/scope.py

from fastapi import HTTPException, status

from app.api.v1.dependencies import CurrentUser
from app.core.enums import RoleName

def validate_scope_access(
    current_user: CurrentUser,
    school_id: int | None = None,
    branch_id: int | None = None,
) -> None:
    """
    Validate that the authenticated user is allowed to access
    the requested school/branch scope.

    Rules:
    - SUPER_ADMIN:
        Can access any school and branch.
    - SCHOOL_ADMIN:
        Can access only their school and branches assigned to them.
    - BRANCH_ADMIN:
        Can access only their school and current branch.
    """

    # ---------------------------------------------------------
    # SUPER ADMIN
    # ---------------------------------------------------------
    if current_user.has_role(RoleName.SUPER_ADMIN):
        return

    # ---------------------------------------------------------
    # SCHOOL VALIDATION
    # ---------------------------------------------------------
    if school_id is not None:
        if school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to the requested school.",
            )

    # ---------------------------------------------------------
    # BRANCH VALIDATION
    # ---------------------------------------------------------
    if branch_id is None:
        return

    # ---------------------------------------------------------
    # SCHOOL ADMIN
    # ---------------------------------------------------------
    if current_user.has_role(RoleName.SCHOOL_ADMIN):

        accessible_branch_ids = (
            current_user.get_accessible_branch_ids(
                current_user.school_id
            )
        )

        if branch_id not in accessible_branch_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to the requested branch.",
            )

        return

    # ---------------------------------------------------------
    # BRANCH ADMIN
    # ---------------------------------------------------------
    if current_user.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to the requested branch.",
        )