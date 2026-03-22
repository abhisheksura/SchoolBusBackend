from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schools import service as school_service
from app.schools.schemas import (
    BranchCreate,
    BranchResponse,
    BranchUpdate,
    PaginatedBranchResponse,
    PaginatedSchoolResponse,
    SchoolCreate,
    SchoolResponse,
    SchoolUpdate,
)
from app.core.config import settings
from app.core.db import get_db
from app.core.enums import RoleName
from app.api.v1.dependencies import (
    AnyAuthenticated,
    CurrentUser,
    require_roles,
)

router = APIRouter()


# =============================================================================
# School Routes
# =============================================================================

@router.post(
    "/",
    response_model=SchoolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create school",
    description="Create a new school. Only SUPER_ADMIN can perform this action.",
)
async def create_school(
    payload: SchoolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(RoleName.SUPER_ADMIN)),
) -> SchoolResponse:
    """Create a new school. Role enforced by require_roles()."""
    return await school_service.create_school(
        db=db,
        school_name=payload.school_name,
    )


@router.get(
    "/",
    response_model=PaginatedSchoolResponse,
    status_code=status.HTTP_200_OK,
    summary="List schools",
    description=(
        "Fetch paginated list of schools. "
        "SUPER_ADMIN sees all. Others see only their own school. "
        "Pass active_only=false to include deactivated schools "
        "(SUPER_ADMIN and SCHOOL_ADMIN only)."
    ),
)
async def get_all_schools(
    page     : int  = Query(default=1, ge=1, description="Page number"),
    page_size: int  = Query(
        default=settings.DEFAULT_PAGE_SIZE,
        ge=1,
        le=settings.MAX_PAGE_SIZE,
        description="Items per page",
    ),
    active_only: bool = Query(default=True, description="Filter to active schools only"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedSchoolResponse:
    """Fetch paginated list of schools filtered by caller's scope."""
    # Non-admins always see active_only — ignore their active_only=false
    if not current_user.has_any_role(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN):
        active_only = True

    return await school_service.get_all_schools(
        db=db,
        page=page,
        page_size=page_size,
        accessible_school_ids=current_user.get_accessible_school_ids(),
        active_only=active_only,
    )


@router.get(
    "/{school_id}",
    response_model=SchoolResponse,
    status_code=status.HTTP_200_OK,
    summary="Get school",
    description=(
        "Fetch a single school by ID. "
        "Returns 404 if the school doesn't exist or is outside the caller's scope."
    ),
)
async def get_school(
    school_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> SchoolResponse:
    """Fetch a single school. Scope enforced in service (404 on violation)."""
    return await school_service.get_school(
        db=db,
        school_id=school_id,
        accessible_school_ids=current_user.get_accessible_school_ids(),
    )


@router.patch(
    "/{school_id}",
    response_model=SchoolResponse,
    status_code=status.HTTP_200_OK,
    summary="Update school",
    description="Partially update a school. Only SUPER_ADMIN can perform this action.",
)
async def update_school(
    school_id: int,
    payload  : SchoolUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(RoleName.SUPER_ADMIN)),
) -> SchoolResponse:
    """Partially update a school. Role enforced by require_roles()."""
    return await school_service.update_school(
        db=db,
        school_id=school_id,
        payload=payload,
    )


@router.delete(
    "/{school_id}",
    response_model=SchoolResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate school",
    description=(
        "Soft-delete a school by setting is_active=False. "
        "Only SUPER_ADMIN can perform this action. "
        "Returns the deactivated school object."
    ),
)
async def deactivate_school(
    school_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(RoleName.SUPER_ADMIN)),
) -> SchoolResponse:
    """Soft-delete a school. Role enforced by require_roles()."""
    return await school_service.deactivate_school(
        db=db,
        school_id=school_id,
    )


# =============================================================================
# Branch Routes (nested under /schools/{school_id}/branches)
# =============================================================================

@router.post(
    "/{school_id}/branches/",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create branch",
    description=(
        "Create a new branch under a school. "
        "SUPER_ADMIN or SCHOOL_ADMIN scoped to this school can perform this action."
    ),
)
async def create_branch(
    school_id: int,
    payload  : BranchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN)
    ),
) -> BranchResponse:
    """
    Create a branch. Role enforced by require_roles().
    School-level scope enforced here — SCHOOL_ADMIN must belong to this school.
    """
    # SCHOOL_ADMIN must be scoped to this specific school
    if (
        current_user.has_any_role(RoleName.SCHOOL_ADMIN)
        and not current_user.has_role(RoleName.SUPER_ADMIN)
    ):
        school_ids = current_user.get_accessible_school_ids() or []
        if school_id not in school_ids:
            from app.core.exceptions import ForbiddenError
            raise ForbiddenError(
                detail="You do not have access to this school."
            )

    return await school_service.create_branch(
        db=db,
        school_id=school_id,
        payload=payload,
    )


@router.get(
    "/{school_id}/branches/",
    response_model=PaginatedBranchResponse,
    status_code=status.HTTP_200_OK,
    summary="List branches",
    description=(
        "Fetch paginated list of branches for a school. "
        "SUPER_ADMIN and SCHOOL_ADMIN see all branches. "
        "Other roles see only their own branch. "
        "Pass active_only=false to include deactivated branches "
        "(SUPER_ADMIN and SCHOOL_ADMIN only)."
    ),
)
async def get_all_branches(
    school_id: int,
    page     : int  = Query(default=1, ge=1, description="Page number"),
    page_size: int  = Query(
        default=settings.DEFAULT_PAGE_SIZE,
        ge=1,
        le=settings.MAX_PAGE_SIZE,
        description="Items per page",
    ),
    active_only: bool = Query(default=True, description="Filter to active branches only"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedBranchResponse:
    """Fetch paginated branches filtered by caller's scope."""
    # Non-admins always see active_only — ignore their active_only=false
    if not current_user.has_any_role(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN):
        active_only = True

    return await school_service.get_all_branches(
        db=db,
        school_id=school_id,
        page=page,
        page_size=page_size,
        accessible_school_ids=current_user.get_accessible_school_ids(),
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
        active_only=active_only,
    )


@router.get(
    "/{school_id}/branches/{branch_id}",
    response_model=BranchResponse,
    status_code=status.HTTP_200_OK,
    summary="Get branch",
    description=(
        "Fetch a single branch by ID. "
        "Returns 404 if the branch doesn't exist or is outside the caller's scope."
    ),
)
async def get_branch(
    school_id: int,
    branch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> BranchResponse:
    """Fetch a single branch. Scope enforced in service (404 on violation)."""
    return await school_service.get_branch(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.patch(
    "/{school_id}/branches/{branch_id}",
    response_model=BranchResponse,
    status_code=status.HTTP_200_OK,
    summary="Update branch",
    description=(
        "Partially update a branch. "
        "SUPER_ADMIN or SCHOOL_ADMIN scoped to this school can perform this action."
    ),
)
async def update_branch(
    school_id: int,
    branch_id: int,
    payload  : BranchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN)
    ),
) -> BranchResponse:
    """Partially update a branch. Role enforced by require_roles()."""
    # SCHOOL_ADMIN must be scoped to this specific school
    if (
        current_user.has_any_role(RoleName.SCHOOL_ADMIN)
        and not current_user.has_role(RoleName.SUPER_ADMIN)
    ):
        school_ids = current_user.get_accessible_school_ids() or []
        if school_id not in school_ids:
            from app.core.exceptions import ForbiddenError
            raise ForbiddenError(
                detail="You do not have access to this school."
            )

    return await school_service.update_branch(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
    )


@router.delete(
    "/{school_id}/branches/{branch_id}",
    response_model=BranchResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate branch",
    description=(
        "Soft-delete a branch by setting is_active=False. "
        "SUPER_ADMIN or SCHOOL_ADMIN scoped to this school can perform this action. "
        "Returns the deactivated branch object."
    ),
)
async def deactivate_branch(
    school_id: int,
    branch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN)
    ),
) -> BranchResponse:
    """Soft-delete a branch. Role enforced by require_roles()."""
    # SCHOOL_ADMIN must be scoped to this specific school
    if (
        current_user.has_any_role(RoleName.SCHOOL_ADMIN)
        and not current_user.has_role(RoleName.SUPER_ADMIN)
    ):
        school_ids = current_user.get_accessible_school_ids() or []
        if school_id not in school_ids:
            from app.core.exceptions import ForbiddenError
            raise ForbiddenError(
                detail="You do not have access to this school."
            )

    return await school_service.deactivate_branch(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
    )