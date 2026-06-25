from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.students import repository as student_repo
from app.students.schemas import (
    LeaveRequestCreate,
    LeaveRequestResponse,
    LeaveRequestUpdateStatus,
    PaginatedLeaveRequestResponse,
    PaginatedParentResponse,
    PaginatedStudentResponse,
    ParentCreate,
    ParentResponse,
    ParentUpdate,
    StudentCreate,
    StudentParentCreate,
    StudentParentResponse,
    StudentParentUpdate,
    StudentResponse,
    StudentUpdate,
)
from app.core.config import settings
from app.core.enums import LeaveRequestStatus, LEAVE_STATUS_TRANSITIONS
from app.core.exceptions import (
    DuplicateEntryError,
    ForbiddenError,
    InvalidStatusTransitionError,
    LeaveRequestNotFoundError,
    ParentNotFoundError,
    StudentNotFoundError,
)
from app.core.schemas import paginate, pagination_params
from app.core.utils import get_tenant_names, to_tenant_response


# =============================================================================
# Student Services
# =============================================================================

async def create_student(
    db: AsyncSession,
    payload: StudentCreate,
) -> StudentResponse:
    """
    Create a new student.
    Checks user_id is not already linked to another student.
    Role check (BRANCH_ADMIN+) enforced at router.
    """
    try:
        student = await student_repo.create_student(
            db=db,
            school_id=payload.school_id,
            branch_id=payload.branch_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            admission_number=payload.admission_number,
            grade=payload.grade,
            section=payload.section,
        )
    except IntegrityError:
        raise DuplicateEntryError(field="student identity", value=f"{payload.first_name} {payload.last_name} in grade {payload.grade} section {payload.section}")
    return StudentResponse.model_validate(student)


async def get_student(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> StudentResponse:
    """Fetch a single student. Scope check BEFORE DB hit."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise StudentNotFoundError(identifier=student_id)

    student = await student_repo.get_student_by_student_id(db, student_id, school_id, branch_id)
    return StudentResponse.model_validate(student)


async def get_all_students(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    page: int,
    page_size: int,
    # accessible_branch_ids: list[int] | None,
    active_only: bool = False,
) -> PaginatedStudentResponse:
    """
    Fetch paginated students with zero DB join overhead.
    Tenant details are injected via an optimized, cached mapper layer.
    """
    # 1. Calculate pagination windows
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)

    # 2. Fetch data and row counts seamlessly from the optimized repo
    students, total = await student_repo.get_all_students(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        limit=limit,
        offset=offset,
        active_only=active_only,
    )

    # 3. Short-circuit: skip cache parsing entirely if page is empty
    if not students:
        return paginate(
            items=[],
            total=total,
            page=page,
            page_size=page_size,
        )

    # 4. Fetch the tenant names *once* per request block (0ms response if cached)
    school_name, branch_name = await get_tenant_names(db, school_id, branch_id)

    # 5. Map rows efficiently into Pydantic passing string references
    mapped_items = [
        to_tenant_response(
            s,
            StudentResponse,
            school_name=school_name,
            branch_name=branch_name
        )
        for s in students
    ]

    # 6. Return standard paginated payload structure
    return paginate(
        items=mapped_items,
        total=total,
        page=page,
        page_size=page_size,
    )


async def update_student(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
    payload: StudentUpdate,
) -> StudentResponse:
    """Update a student. Role check enforced at router."""
    try:
        student = await student_repo.update_student_by_student_id(
            db=db,
            student_id=student_id,
            school_id=school_id,
            branch_id=branch_id,
            **payload.model_dump(exclude_unset=True),
        )
    except IntegrityError:
        raise DuplicateEntryError(field="student identity", value="duplicate name/grade/section combination")
    return StudentResponse.model_validate(student)


async def deactivate_student(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
) -> StudentResponse:
    """Soft-delete a student. Role check enforced at router."""
    student = await student_repo.deactivate_student_by_student_id(
        db, student_id, school_id, branch_id
    )
    return StudentResponse.model_validate(student)


async def reactivate_student(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
) -> StudentResponse:
    student = await student_repo.reactivate_student_by_student_id(db, student_id, school_id, branch_id)
    return StudentResponse.model_validate(student)

# =============================================================================
# Parent Services
# =============================================================================

async def create_parent(
    db: AsyncSession,
    payload: ParentCreate,
) -> ParentResponse:
    """
    Create a new parent.
    Checks user_id is not already linked to another parent.
    Role check (BRANCH_ADMIN+) enforced at router.
    """
    existing = await student_repo.get_parent_by_user_id_or_none(db, payload.user_id)
    if existing:
        raise DuplicateEntryError(field="user_id", value=str(payload.user_id))

    parent = await student_repo.create_parent(
        db=db,
        school_id=payload.school_id,
        user_id=payload.user_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        alternate_phone=payload.alternate_phone,
        email=str(payload.email) if payload.email else None,
        address=payload.address,
    )
    return ParentResponse.model_validate(parent)


async def get_parent(
    db: AsyncSession,
    parent_id: int,
    school_id: int,
    accessible_school_ids: list[int] | None,
) -> ParentResponse:
    """
    Fetch a single parent.
    Parents are school-scoped — scope check uses school_ids.
    Scope check BEFORE DB hit.
    """
    if accessible_school_ids is not None and school_id not in accessible_school_ids:
        raise ParentNotFoundError(identifier=parent_id)

    parent = await student_repo.get_parent_by_parent_id(db, parent_id, school_id)
    return ParentResponse.model_validate(parent)


async def get_all_parents(
    db: AsyncSession,
    school_id: int,
    page: int,
    page_size: int,
    accessible_school_ids: list[int] | None,
    active_only: bool = True,
) -> PaginatedParentResponse:
    """Fetch paginated parents for a school, filtered by caller's school scope."""
    if accessible_school_ids is not None and school_id not in accessible_school_ids:
        raise ParentNotFoundError()

    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)
    parents, total = await student_repo.get_all_parents_by_school(
        db=db, school_id=school_id, limit=limit, offset=offset, active_only=active_only,
    )

    return paginate(
        items=[ParentResponse.model_validate(p) for p in parents],
        total=total, page=page, page_size=page_size,
    )


async def update_parent(
    db: AsyncSession,
    parent_id: int,
    school_id: int,
    payload: ParentUpdate,
) -> ParentResponse:
    """Update a parent. Role check enforced at router."""
    parent = await student_repo.update_parent_by_parent_id(
        db=db,
        parent_id=parent_id,
        school_id=school_id,
        **payload.model_dump(exclude_unset=True),
    )
    return ParentResponse.model_validate(parent)


async def deactivate_parent(
    db: AsyncSession,
    parent_id: int,
    school_id: int,
) -> ParentResponse:
    """Soft-delete a parent. Role check enforced at router."""
    parent = await student_repo.deactivate_parent_by_parent_id(db, parent_id, school_id)
    return ParentResponse.model_validate(parent)


# =============================================================================
# StudentParent Services
# =============================================================================

async def link_parent_to_student(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
    payload: StudentParentCreate,
    accessible_branch_ids: list[int] | None,
) -> StudentParentResponse:
    """
    Link a parent to a student.
    Verifies:
        1. Caller has branch access
        2. Student exists in this branch
        3. Parent exists in this school
        4. Link doesn't already exist
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise StudentNotFoundError(identifier=student_id)

    # Verify student exists
    await student_repo.get_student_by_student_id(db, student_id, school_id, branch_id)

    # Verify parent exists in this school
    await student_repo.get_parent_by_parent_id(db, payload.parent_id, school_id)

    # Check link doesn't already exist
    existing = await student_repo.get_student_parent_by_student_and_parent(
        db, student_id, payload.parent_id
    )
    if existing:
        raise DuplicateEntryError(
            field="student_parent",
            value=f"student {student_id} and parent {payload.parent_id} already linked",
        )

    sp = await student_repo.create_student_parent(
        db=db,
        student_id=student_id,
        parent_id=payload.parent_id,
        relationship=payload.relationship,
        is_primary=payload.is_primary,
    )
    return StudentParentResponse.model_validate(sp)


async def get_student_parents(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> list[StudentParentResponse]:
    """Fetch all parents linked to a student. Scope check BEFORE DB hit."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise StudentNotFoundError(identifier=student_id)

    await student_repo.get_student_by_student_id(db, student_id, school_id, branch_id)
    links = await student_repo.get_parents_by_student_id(db, student_id)
    return [StudentParentResponse.model_validate(sp) for sp in links]


async def update_student_parent_link(
    db: AsyncSession,
    student_parent_id: int,
    student_id: int,
    school_id: int,
    branch_id: int,
    payload: StudentParentUpdate,
    accessible_branch_ids: list[int] | None,
) -> StudentParentResponse:
    """Update a student-parent link (relationship label or primary flag)."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise StudentNotFoundError(identifier=student_id)

    sp = await student_repo.update_student_parent_by_id(
        db=db,
        student_parent_id=student_parent_id,
        student_id=student_id,
        **payload.model_dump(exclude_unset=True),
    )
    return StudentParentResponse.model_validate(sp)


async def unlink_parent_from_student(
    db: AsyncSession,
    student_parent_id: int,
    student_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> None:
    """Remove a student-parent link. Role check enforced at router."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise StudentNotFoundError(identifier=student_id)

    await student_repo.delete_student_parent_by_id(db, student_parent_id, student_id)


# =============================================================================
# Leave Request Services
# =============================================================================

async def create_leave_request(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
    payload: LeaveRequestCreate,
    requested_by_user_id: int,
    accessible_branch_ids: list[int] | None,
) -> LeaveRequestResponse:
    """
    Submit a leave request for a student.
    Any authenticated user with branch access can submit (parent, admin, driver).
    Scope check BEFORE DB hit.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise StudentNotFoundError(identifier=student_id)

    # Verify student exists and is active
    student = await student_repo.get_student_by_student_id(db, student_id, school_id, branch_id)
    if not student.is_active:
        raise StudentNotFoundError(identifier=student_id)

    leave = await student_repo.create_leave_request(
        db=db,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        requested_by=requested_by_user_id,
        reason=payload.reason,
    )
    return LeaveRequestResponse.model_validate(leave)


async def get_leave_requests(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
    page: int,
    page_size: int,
    accessible_branch_ids: list[int] | None,
    status_filter: LeaveRequestStatus | None = None,
) -> PaginatedLeaveRequestResponse:
    """Fetch paginated leave requests for a student."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise StudentNotFoundError(identifier=student_id)

    await student_repo.get_student_by_student_id(db, student_id, school_id, branch_id)

    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)
    leaves, total = await student_repo.get_all_leave_requests_by_student(
        db=db,
        student_id=student_id,
        school_id=school_id,
        limit=limit,
        offset=offset,
        status_filter=status_filter,
    )

    return paginate(
        items=[LeaveRequestResponse.model_validate(l) for l in leaves],
        total=total, page=page, page_size=page_size,
    )


async def update_leave_request_status(
    db: AsyncSession,
    leave_id: int,
    student_id: int,
    school_id: int,
    branch_id: int,
    payload: LeaveRequestUpdateStatus,
    accessible_branch_ids: list[int] | None,
) -> LeaveRequestResponse:
    """
    Update leave request status.
    Validates transition against LEAVE_STATUS_TRANSITIONS map.
    PENDING → APPROVED | REJECTED only.
    Role check (BRANCH_ADMIN+) enforced at router.
    Scope check BEFORE DB hit.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise LeaveRequestNotFoundError(identifier=leave_id)

    leave = await student_repo.get_leave_request_by_leave_id(
        db, leave_id, student_id, school_id
    )

    # Validate status transition
    current = LeaveRequestStatus(leave.status)
    allowed = LEAVE_STATUS_TRANSITIONS.get(current, set())
    if payload.status not in allowed:
        raise InvalidStatusTransitionError(
            current=current.value,
            requested=payload.status.value,
        )

    updated = await student_repo.update_leave_request_status(
        db=db,
        leave_id=leave_id,
        student_id=student_id,
        school_id=school_id,
        new_status=payload.status,
    )
    return LeaveRequestResponse.model_validate(updated)