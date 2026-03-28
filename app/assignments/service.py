from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.assignments import repository as assignment_repo
from app.assignments.schemas import (
    AttendanceMarkRequest,
    AttendanceResponse,
    AttendanceUpdateRequest,
    PaginatedAssignmentResponse,
    PaginatedAttendanceResponse,
    StudentRouteAssignmentCreate,
    StudentRouteAssignmentResponse,
)
from app.trips.repository import get_trip_by_trip_id
from app.core.config import settings
from app.core.enums import TripStatus, TripType
from app.core.exceptions import (
    DuplicateEntryError,
    ForbiddenError,
    StudentAlreadyAssignedError,
    TripNotFoundError,
)
from app.core.schemas import paginate, pagination_params


# =============================================================================
# StudentRouteAssignment Services
# =============================================================================

async def assign_student_to_route(
    db: AsyncSession,
    payload: StudentRouteAssignmentCreate,
) -> StudentRouteAssignmentResponse:
    """
    Assign a student to a route + boarding stop for a trip_type.
    Checks for existing active assignment before inserting.
    A student can have at most one active assignment per route + type.
    Role check (BRANCH_ADMIN+) enforced at router.
    """
    existing = await assignment_repo.get_active_assignment_by_student_and_type(
        db=db,
        student_id=payload.student_id,
        route_id=payload.route_id,
        assignment_type=payload.assignment_type,
        school_id=payload.school_id,
        branch_id=payload.branch_id,
    )
    if existing:
        raise StudentAlreadyAssignedError()

    try:
        assignment = await assignment_repo.create_student_route_assignment(
            db=db,
            school_id=payload.school_id,
            branch_id=payload.branch_id,
            student_id=payload.student_id,
            route_id=payload.route_id,
            stop_id=payload.stop_id,
            assignment_type=payload.assignment_type,
        )
    except IntegrityError:
        raise StudentAlreadyAssignedError()

    return StudentRouteAssignmentResponse.model_validate(assignment)


async def get_student_assignments(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
    active_only: bool = True,
) -> list[StudentRouteAssignmentResponse]:
    """
    Fetch all route assignments for a student.
    Scope check BEFORE DB hit.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise TripNotFoundError(identifier=student_id)

    assignments = await assignment_repo.get_all_assignments_by_student(
        db, student_id, school_id, branch_id, active_only=active_only
    )
    return [StudentRouteAssignmentResponse.model_validate(a) for a in assignments]


async def get_route_assignments(
    db: AsyncSession,
    route_id: int,
    school_id: int,
    branch_id: int,
    page: int,
    page_size: int,
    accessible_branch_ids: list[int] | None,
    assignment_type: TripType | None = None,
    active_only: bool = True,
) -> PaginatedAssignmentResponse:
    """
    Fetch all student assignments for a route.
    Scope check BEFORE DB hit.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise TripNotFoundError(identifier=route_id)

    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)
    assignments, total = await assignment_repo.get_all_assignments_by_route(
        db=db,
        route_id=route_id,
        school_id=school_id,
        branch_id=branch_id,
        limit=limit,
        offset=offset,
        assignment_type=assignment_type,
        active_only=active_only,
    )

    return paginate(
        items=[StudentRouteAssignmentResponse.model_validate(a) for a in assignments],
        total=total, page=page, page_size=page_size,
    )


async def deactivate_assignment(
    db: AsyncSession,
    assignment_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> StudentRouteAssignmentResponse:
    """
    Soft-delete a student route assignment.
    Scope check BEFORE DB hit.
    Role check (BRANCH_ADMIN+) enforced at router.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise TripNotFoundError(identifier=assignment_id)

    assignment = await assignment_repo.deactivate_assignment_by_id(
        db, assignment_id, school_id, branch_id
    )
    return StudentRouteAssignmentResponse.model_validate(assignment)


# =============================================================================
# StudentAttendance Services
# =============================================================================

async def mark_attendance(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
    payload: AttendanceMarkRequest,
    accessible_branch_ids: list[int] | None,
) -> AttendanceResponse:
    """
    Mark attendance for a student on a trip.
    Validates:
        1. Scope access
        2. Trip is IN_PROGRESS
        3. No duplicate for this student + trip + type
    Role check (DRIVER+) enforced at router.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise TripNotFoundError(identifier=trip_id)

    # Trip must be IN_PROGRESS
    trip = await get_trip_by_trip_id(db, trip_id, school_id, branch_id)
    if trip.trip_status != TripStatus.IN_PROGRESS.value:
        raise ForbiddenError(
            detail=f"Cannot mark attendance on a {trip.trip_status} trip. Trip must be IN_PROGRESS."
        )

    # Duplicate check
    existing = await assignment_repo.get_attendance_by_student_and_trip(
        db=db,
        student_id=payload.student_id,
        trip_id=trip_id,
        assignment_type=payload.assignment_type,
        school_id=school_id,
        branch_id=branch_id,
    )
    if existing:
        raise DuplicateEntryError(
            field="attendance",
            value=f"student {payload.student_id} already marked for trip {trip_id} ({payload.assignment_type.value})",
        )

    record = await assignment_repo.create_attendance_record(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        student_id=payload.student_id,
        trip_id=trip_id,
        assignment_type=payload.assignment_type,
        attendance_status=payload.attendance_status,
        stop_id=payload.stop_id,
        marked_by_driver_id=payload.marked_by_driver_id,
    )
    return AttendanceResponse.model_validate(record)


async def get_trip_attendance(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
    page: int,
    page_size: int,
    accessible_branch_ids: list[int] | None,
    assignment_type: TripType | None = None,
) -> PaginatedAttendanceResponse:
    """Fetch paginated attendance records for a trip."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise TripNotFoundError(identifier=trip_id)

    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)
    records, total = await assignment_repo.get_all_attendance_by_trip(
        db=db,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        limit=limit,
        offset=offset,
        assignment_type=assignment_type,
    )

    return paginate(
        items=[AttendanceResponse.model_validate(r) for r in records],
        total=total, page=page, page_size=page_size,
    )


async def get_student_attendance(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
    page: int,
    page_size: int,
    accessible_branch_ids: list[int] | None,
    trip_id: int | None = None,
) -> PaginatedAttendanceResponse:
    """Fetch attendance history for a student across trips."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise TripNotFoundError(identifier=student_id)

    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)
    records, total = await assignment_repo.get_all_attendance_by_student(
        db=db,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
        limit=limit,
        offset=offset,
        trip_id=trip_id,
    )

    return paginate(
        items=[AttendanceResponse.model_validate(r) for r in records],
        total=total, page=page, page_size=page_size,
    )


async def update_attendance(
    db: AsyncSession,
    attendance_id: int,
    trip_id: int,
    school_id: int,
    branch_id: int,
    payload: AttendanceUpdateRequest,
    accessible_branch_ids: list[int] | None,
) -> AttendanceResponse:
    """
    Correct an attendance record.
    Only status can be changed.
    Role check (BRANCH_ADMIN+) enforced at router.
    Scope check BEFORE DB hit.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise TripNotFoundError(identifier=trip_id)

    record = await assignment_repo.update_attendance_status(
        db=db,
        attendance_id=attendance_id,
        trip_id=trip_id,
        school_id=school_id,
        new_status=payload.attendance_status,
    )
    return AttendanceResponse.model_validate(record)