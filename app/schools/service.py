from sqlalchemy.ext.asyncio import AsyncSession

from app.schools import repository as school_repo
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
from app.core.exceptions import (
    BranchNotFoundError,
    SchoolNotFoundError,
)
from app.core.schemas import paginate, pagination_params


# =============================================================================
# School Services
# =============================================================================

async def create_school(
    db: AsyncSession,
    school_name: str,
) -> SchoolResponse:
    """
    Create a new school.
    Role check (SUPER_ADMIN) is enforced at the router via require_roles().

    Args:
        db          : active async database session
        school_name : name of the new school

    Returns:
        SchoolResponse of the newly created school
    """
    school = await school_repo.create_school(
        db=db,
        school_name=school_name,
    )
    return SchoolResponse.model_validate(school)


async def get_school(
    db: AsyncSession,
    school_id: int,
    accessible_school_ids: list[int] | None,
) -> SchoolResponse:
    """
    Fetch a single school by ID.
    Scope check runs BEFORE the DB query — avoids leaking existence
    of schools outside the caller's tenant via a DB hit.
    Returns 404 on both not-found and out-of-scope cases.

    Args:
        db                   : active async database session
        school_id            : primary key of the school
        accessible_school_ids: None = SUPER_ADMIN (all), list = filtered

    Returns:
        SchoolResponse

    Raises:
        SchoolNotFoundError : if not found or outside caller's scope
    """
    # Scope check FIRST — no DB hit if unauthorized
    if accessible_school_ids is not None and school_id not in accessible_school_ids:
        raise SchoolNotFoundError(identifier=school_id)

    # Now safe to hit the DB
    school = await school_repo.get_school_by_school_id(db, school_id)
    return SchoolResponse.model_validate(school)


async def get_all_schools(
    db: AsyncSession,
    page: int,
    page_size: int,
    accessible_school_ids: list[int] | None,
    active_only: bool = True,
) -> PaginatedSchoolResponse:
    """
    Fetch paginated list of schools.
    None accessible_school_ids = SUPER_ADMIN, returns all schools.
    A list filters to only accessible schools.

    Args:
        db                   : active async database session
        page                 : page number (1-indexed)
        page_size            : number of items per page
        accessible_school_ids: None = all schools, list = filtered
        active_only          : if True, only return active schools

    Returns:
        PaginatedSchoolResponse
    """
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)

    if accessible_school_ids is None:
        schools, total = await school_repo.get_all_schools(
            db=db,
            limit=limit,
            offset=offset,
            active_only=active_only,
        )
    else:
        schools, total = await school_repo.get_schools_by_school_ids(
            db=db,
            school_ids=accessible_school_ids,
            limit=limit,
            offset=offset,
            active_only=active_only,
        )

    return paginate(
        items=[SchoolResponse.model_validate(s) for s in schools],
        total=total,
        page=page,
        page_size=page_size,
    )


async def update_school(
    db: AsyncSession,
    school_id: int,
    payload: SchoolUpdate,
) -> SchoolResponse:
    """
    Partially update a school.
    Role check (SUPER_ADMIN) is enforced at the router via require_roles().

    Args:
        db        : active async database session
        school_id : primary key of the school to update
        payload   : SchoolUpdate with fields to change

    Returns:
        Updated SchoolResponse

    Raises:
        SchoolNotFoundError : if school does not exist
    """
    school = await school_repo.update_school_by_school_id(
        db=db,
        school_id=school_id,
        **payload.model_dump(exclude_unset=True),
    )
    return SchoolResponse.model_validate(school)


async def deactivate_school(
    db: AsyncSession,
    school_id: int,
) -> SchoolResponse:
    """
    Soft-delete a school by setting is_active = False.
    Role check (SUPER_ADMIN) is enforced at the router via require_roles().

    Args:
        db        : active async database session
        school_id : primary key of the school to deactivate

    Returns:
        Deactivated SchoolResponse

    Raises:
        SchoolNotFoundError : if school does not exist
    """
    school = await school_repo.deactivate_school_by_school_id(db, school_id)
    return SchoolResponse.model_validate(school)


# =============================================================================
# Branch Services
# =============================================================================

async def create_branch(
    db: AsyncSession,
    school_id: int,
    payload: BranchCreate,
) -> BranchResponse:
    """
    Create a new branch under a school.
    Role check (SUPER_ADMIN / SCHOOL_ADMIN) enforced at router.
    School scope check enforced at router.

    Uses get_active_school_by_school_id — single atomic query that
    verifies school exists AND is active, eliminating the race condition
    between checking is_active and calling create_branch.

    Args:
        db        : active async database session
        school_id : primary key of the parent school
        payload   : BranchCreate request payload

    Returns:
        BranchResponse of the newly created branch

    Raises:
        SchoolNotFoundError : if school does not exist or is inactive
    """
    # Atomic check — school must exist AND be active in one query
    await school_repo.get_active_school_by_school_id(db, school_id)

    branch = await school_repo.create_branch(
        db=db,
        school_id=school_id,
        branch_name=payload.branch_name,
        branch_address=payload.branch_address,
        branch_phone=payload.branch_phone,
        branch_email=payload.branch_email,
    )
    return BranchResponse.model_validate(branch)


async def get_branch(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> BranchResponse:
    """
    Fetch a single branch by ID scoped to a school.
    Scope check runs BEFORE the DB query.
    Returns 404 on both not-found and out-of-scope cases.

    Args:
        db                    : active async database session
        school_id             : school the branch belongs to
        branch_id             : primary key of the branch
        accessible_branch_ids : None = all branches (SUPER_ADMIN / SCHOOL_ADMIN)
                                list = only these branch_ids

    Returns:
        BranchResponse

    Raises:
        BranchNotFoundError : if not found or outside caller's scope
    """
    # Scope check FIRST — no DB hit if unauthorized
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise BranchNotFoundError(identifier=branch_id)

    branch = await school_repo.get_branch_by_branch_id(db, branch_id, school_id)
    return BranchResponse.model_validate(branch)


async def get_all_branches(
    db: AsyncSession,
    school_id: int,
    page: int,
    page_size: int,
    accessible_school_ids: list[int] | None,
    accessible_branch_ids: list[int] | None,
    active_only: bool = True,
) -> PaginatedBranchResponse:
    """
    Fetch paginated list of branches for a school.

    Scope check order:
        1. School scope — checked BEFORE DB hit (404 if out of scope)
        2. Branch scope — filters the query results

    Note on accessible_branch_ids:
        None  → SUPER_ADMIN or SCHOOL_ADMIN for this school — see all branches
        []    → SCHOOL_ADMIN for a DIFFERENT school, or branch-scoped user
                with no branches in this school — returns empty, not 404
        [ids] → branch-scoped user — filtered to their branches

    Args:
        db                    : active async database session
        school_id             : school to fetch branches for
        page                  : page number (1-indexed)
        page_size             : number of items per page
        accessible_school_ids : None = all schools, list = filtered
        accessible_branch_ids : None = all branches, list = filtered
        active_only           : if True, only return active branches

    Returns:
        PaginatedBranchResponse

    Raises:
        SchoolNotFoundError : if school not found or outside caller's scope
    """
    # School scope check FIRST — no DB hit if unauthorized
    if accessible_school_ids is not None and school_id not in accessible_school_ids:
        raise SchoolNotFoundError(identifier=school_id)

    # Verify school actually exists (only reached if scope check passes)
    await school_repo.get_school_by_school_id(db, school_id)

    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)

    if accessible_branch_ids is None:
        # None = SUPER_ADMIN or SCHOOL_ADMIN scoped to this school
        branches, total = await school_repo.get_all_branches_by_school_id(
            db=db,
            school_id=school_id,
            limit=limit,
            offset=offset,
            active_only=active_only,
        )
    else:
        # Branch-scoped roles — or SCHOOL_ADMIN for a different school
        # (returns empty list, not an error)
        branches, total = await school_repo.get_branches_by_branch_ids(
            db=db,
            branch_ids=accessible_branch_ids,
            school_id=school_id,
            limit=limit,
            offset=offset,
            active_only=active_only,
        )

    return paginate(
        items=[BranchResponse.model_validate(b) for b in branches],
        total=total,
        page=page,
        page_size=page_size,
    )


async def update_branch(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    payload: BranchUpdate,
) -> BranchResponse:
    """
    Partially update a branch.
    Role check (SUPER_ADMIN / SCHOOL_ADMIN) enforced at router.

    Args:
        db        : active async database session
        school_id : school the branch belongs to
        branch_id : primary key of the branch to update
        payload   : BranchUpdate with fields to change

    Returns:
        Updated BranchResponse

    Raises:
        BranchNotFoundError : if branch does not exist
    """
    branch = await school_repo.update_branch_by_branch_id(
        db=db,
        branch_id=branch_id,
        school_id=school_id,
        **payload.model_dump(exclude_unset=True),
    )
    return BranchResponse.model_validate(branch)


async def deactivate_branch(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
) -> BranchResponse:
    """
    Soft-delete a branch by setting is_active = False.
    Role check (SUPER_ADMIN / SCHOOL_ADMIN) enforced at router.

    Args:
        db        : active async database session
        school_id : school the branch belongs to
        branch_id : primary key of the branch to deactivate

    Returns:
        Deactivated BranchResponse

    Raises:
        BranchNotFoundError : if branch does not exist
    """
    branch = await school_repo.deactivate_branch_by_branch_id(
        db, branch_id, school_id
    )
    return BranchResponse.model_validate(branch)