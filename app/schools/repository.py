from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.schools.models import Branch, School
from app.core.exceptions import BranchNotFoundError, SchoolNotFoundError


# =============================================================================
# School Queries
# =============================================================================

async def get_school_by_school_id(
    db: AsyncSession,
    school_id: int,
) -> School:
    """
    Fetch a school by its primary key.

    Args:
        db        : active async database session
        school_id : primary key of the school

    Returns:
        School ORM instance

    Raises:
        SchoolNotFoundError : if no school exists with the given school_id
    """
    result = await db.execute(
        select(School).where(School.school_id == school_id)
    )
    school = result.scalar_one_or_none()
    if not school:
        raise SchoolNotFoundError(identifier=school_id)
    return school


async def get_school_with_branches_by_school_id(
    db: AsyncSession,
    school_id: int,
    active_branches_only: bool = True,
) -> School:
    """
    Fetch a school with its branches eagerly loaded via selectinload.
    Use this whenever SchoolDetailResponse is needed — never use
    get_school_by_school_id() with SchoolDetailResponse as the branches
    relationship is lazy="noload" and will return an empty list silently.

    Args:
        db                   : active async database session
        school_id            : primary key of the school
        active_branches_only : if True, only load is_active=True branches

    Returns:
        School ORM instance with branches populated

    Raises:
        SchoolNotFoundError : if no school exists with the given school_id
    """
    from sqlalchemy.orm import selectinload

    branch_condition = (
        selectinload(School.branches.and_(Branch.is_active == True))
        if active_branches_only
        else selectinload(School.branches)
    )

    result = await db.execute(
        select(School)
        .options(branch_condition)
        .where(School.school_id == school_id)
    )
    school = result.scalar_one_or_none()
    if not school:
        raise SchoolNotFoundError(identifier=school_id)
    return school


async def get_active_school_by_school_id(
    db: AsyncSession,
    school_id: int,
) -> School:
    """
    Fetch a school by its primary key only if it is active.
    Used in create_branch to atomically verify school exists AND is active —
    eliminates the check-then-act race condition.

    Args:
        db        : active async database session
        school_id : primary key of the school

    Returns:
        School ORM instance (guaranteed active)

    Raises:
        SchoolNotFoundError : if school does not exist or is inactive
    """
    result = await db.execute(
        select(School).where(
            School.school_id == school_id,
            School.is_active == True,
        )
    )
    school = result.scalar_one_or_none()
    if not school:
        raise SchoolNotFoundError(identifier=school_id)
    return school


async def get_school_by_school_id_or_none(
    db: AsyncSession,
    school_id: int,
) -> School | None:
    """
    Fetch a school by its primary key.
    Returns None if not found — caller decides whether to raise.

    Args:
        db        : active async database session
        school_id : primary key of the school

    Returns:
        School ORM instance or None
    """
    result = await db.execute(
        select(School).where(School.school_id == school_id)
    )
    return result.scalar_one_or_none()


async def get_all_schools(
    db: AsyncSession,
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[School], int]:
    """
    Fetch all schools with pagination.
    Used for SUPER_ADMIN — no tenant filtering applied.

    Args:
        db          : active async database session
        limit       : max number of records to return
        offset      : number of records to skip
        active_only : if True, only return is_active=True schools

    Returns:
        Tuple of (list of School ORM instances, total count)
    """
    query = select(School)
    if active_only:
        query = query.where(School.is_active == True)

    total = await db.scalar(
        select(func.count()).select_from(query.subquery())
    )
    result = await db.execute(
        query.order_by(School.school_name).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def get_schools_by_school_ids(
    db: AsyncSession,
    school_ids: list[int],
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[School], int]:
    """
    Fetch schools filtered by a list of school_ids.
    Used for non-SUPER_ADMIN users — returns only their accessible schools.

    Args:
        db          : active async database session
        school_ids  : list of school_ids to filter by
        limit       : max number of records to return
        offset      : number of records to skip
        active_only : if True, only return is_active=True schools

    Returns:
        Tuple of (list of School ORM instances, total count)
    """
    query = select(School).where(School.school_id.in_(school_ids))
    if active_only:
        query = query.where(School.is_active == True)

    total = await db.scalar(
        select(func.count()).select_from(query.subquery())
    )
    result = await db.execute(
        query.order_by(School.school_name).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def create_school(
    db: AsyncSession,
    school_name: str,
) -> School:
    """
    Insert a new school record.

    Args:
        db          : active async database session
        school_name : name of the school

    Returns:
        Newly created School ORM instance
    """
    school = School(school_name=school_name)
    db.add(school)
    await db.flush()
    await db.refresh(school)
    return school


async def update_school_by_school_id(
    db: AsyncSession,
    school_id: int,
    **kwargs,
) -> School:
    """
    Update one or more fields on a school record.
    Uses PostgreSQL RETURNING clause — single round-trip, no stale data risk.

    Service uses exclude_unset=True — only explicitly set fields arrive here.
    None values are allowed through — they mean "clear this field" (e.g.
    a client explicitly sending null to clear a nullable column).

    Args:
        db        : active async database session
        school_id : primary key of the school to update
        **kwargs  : field=value pairs to update

    Returns:
        Updated School ORM instance — exact post-update DB state

    Raises:
        SchoolNotFoundError : if no school exists with the given school_id
    """
    values = dict(kwargs)
    values["updated_at"] = func.now()

    result = await db.execute(
        update(School)
        .where(School.school_id == school_id)
        .values(**values)
        .returning(School)
    )
    await db.flush()
    school = result.scalar_one_or_none()
    if not school:
        raise SchoolNotFoundError(identifier=school_id)
    return school


async def deactivate_school_by_school_id(
    db: AsyncSession,
    school_id: int,
) -> School:
    """
    Soft-delete a school by setting is_active = False.
    Uses PostgreSQL RETURNING clause — single round-trip, no stale data risk.

    Args:
        db        : active async database session
        school_id : primary key of the school to deactivate

    Returns:
        Updated School ORM instance — exact post-update DB state

    Raises:
        SchoolNotFoundError : if no school exists with the given school_id
    """
    result = await db.execute(
        update(School)
        .where(School.school_id == school_id)
        .values(is_active=False, updated_at=func.now())
        .returning(School)
    )
    await db.flush()
    school = result.scalar_one_or_none()
    if not school:
        raise SchoolNotFoundError(identifier=school_id)
    return school


# =============================================================================
# Branch Queries
# =============================================================================

async def get_branch_by_branch_id(
    db: AsyncSession,
    branch_id: int,
    school_id: int,
) -> Branch:
    """
    Fetch a branch by its primary key scoped to a school.
    Always requires school_id to enforce tenant isolation.

    Args:
        db        : active async database session
        branch_id : primary key of the branch
        school_id : school the branch belongs to

    Returns:
        Branch ORM instance

    Raises:
        BranchNotFoundError : if no branch exists with given branch_id + school_id
    """
    result = await db.execute(
        select(Branch).where(
            Branch.branch_id == branch_id,
            Branch.school_id == school_id,
        )
    )
    branch = result.scalar_one_or_none()
    if not branch:
        raise BranchNotFoundError(identifier=branch_id)
    return branch


async def get_branch_by_branch_id_or_none(
    db: AsyncSession,
    branch_id: int,
    school_id: int,
) -> Branch | None:
    """
    Fetch a branch by its primary key scoped to a school.
    Returns None if not found — caller decides whether to raise.

    Args:
        db        : active async database session
        branch_id : primary key of the branch
        school_id : school the branch belongs to

    Returns:
        Branch ORM instance or None
    """
    result = await db.execute(
        select(Branch).where(
            Branch.branch_id == branch_id,
            Branch.school_id == school_id,
        )
    )
    return result.scalar_one_or_none()


async def get_all_branches_by_school_id(
    db: AsyncSession,
    school_id: int,
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Branch], int]:
    """
    Fetch all branches for a school with pagination.
    Used for SUPER_ADMIN and SCHOOL_ADMIN — no branch-level filtering.

    Args:
        db          : active async database session
        school_id   : school to fetch branches for
        limit       : max number of records to return
        offset      : number of records to skip
        active_only : if True, only return is_active=True branches

    Returns:
        Tuple of (list of Branch ORM instances, total count)
    """
    query = select(Branch).where(Branch.school_id == school_id)
    if active_only:
        query = query.where(Branch.is_active == True)

    total = await db.scalar(
        select(func.count()).select_from(query.subquery())
    )
    result = await db.execute(
        query.order_by(Branch.branch_name).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def get_branches_by_branch_ids(
    db: AsyncSession,
    branch_ids: list[int],
    school_id: int,
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Branch], int]:
    """
    Fetch branches filtered by a list of branch_ids within a school.
    Used for BRANCH_ADMIN, DRIVER, PARENT, STUDENT — returns only
    their accessible branches.

    Args:
        db          : active async database session
        branch_ids  : list of branch_ids to filter by
        school_id   : school to scope the query to
        limit       : max number of records to return
        offset      : number of records to skip
        active_only : if True, only return is_active=True branches

    Returns:
        Tuple of (list of Branch ORM instances, total count)
    """
    query = select(Branch).where(
        Branch.branch_id.in_(branch_ids),
        Branch.school_id == school_id,
    )
    if active_only:
        query = query.where(Branch.is_active == True)

    total = await db.scalar(
        select(func.count()).select_from(query.subquery())
    )
    result = await db.execute(
        query.order_by(Branch.branch_name).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def create_branch(
    db: AsyncSession,
    school_id: int,
    branch_name: str,
    branch_address: str | None = None,
    branch_phone: str | None = None,
    branch_email: str | None = None,
) -> Branch:
    """
    Insert a new branch record under a school.

    Args:
        db             : active async database session
        school_id      : primary key of the parent school
        branch_name    : name of the branch
        branch_address : optional address
        branch_phone   : optional phone number
        branch_email   : optional email address

    Returns:
        Newly created Branch ORM instance
    """
    branch = Branch(
        school_id=school_id,
        branch_name=branch_name,
        branch_address=branch_address,
        branch_phone=branch_phone,
        branch_email=branch_email,
    )
    db.add(branch)
    await db.flush()
    await db.refresh(branch)
    return branch


async def update_branch_by_branch_id(
    db: AsyncSession,
    branch_id: int,
    school_id: int,
    **kwargs,
) -> Branch:
    """
    Update one or more fields on a branch record.
    Uses PostgreSQL RETURNING clause — single round-trip, no stale data risk.

    Service uses exclude_unset=True — only explicitly set fields arrive here.
    None values are allowed through — they mean "clear this field" (e.g.
    a client explicitly sending null to clear branch_address).

    Args:
        db        : active async database session
        branch_id : primary key of the branch to update
        school_id : school the branch belongs to (enforces tenant scope)
        **kwargs  : field=value pairs to update

    Returns:
        Updated Branch ORM instance — exact post-update DB state

    Raises:
        BranchNotFoundError : if no branch exists with given branch_id + school_id
    """
    values = dict(kwargs)
    values["updated_at"] = func.now()

    result = await db.execute(
        update(Branch)
        .where(
            Branch.branch_id == branch_id,
            Branch.school_id == school_id,
        )
        .values(**values)
        .returning(Branch)
    )
    await db.flush()
    branch = result.scalar_one_or_none()
    if not branch:
        raise BranchNotFoundError(identifier=branch_id)
    return branch


async def deactivate_branch_by_branch_id(
    db: AsyncSession,
    branch_id: int,
    school_id: int,
) -> Branch:
    """
    Soft-delete a branch by setting is_active = False.
    Uses PostgreSQL RETURNING clause — single round-trip, no stale data risk.

    Args:
        db        : active async database session
        branch_id : primary key of the branch to deactivate
        school_id : school the branch belongs to (enforces tenant scope)

    Returns:
        Updated Branch ORM instance — exact post-update DB state

    Raises:
        BranchNotFoundError : if no branch exists with given branch_id + school_id
    """
    result = await db.execute(
        update(Branch)
        .where(
            Branch.branch_id == branch_id,
            Branch.school_id == school_id,
        )
        .values(is_active=False, updated_at=func.now())
        .returning(Branch)
    )
    await db.flush()
    branch = result.scalar_one_or_none()
    if not branch:
        raise BranchNotFoundError(identifier=branch_id)
    return branch