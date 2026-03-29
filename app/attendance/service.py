from sqlalchemy.ext.asyncio import AsyncSession

from app.attendance import repository as attendance_repo
from app.attendance.schemas import (
    AttendanceMarkRequest,
    AttendanceResponse,
    AttendanceUpdateRequest,
    PaginatedAttendanceResponse,
)
from app.trips.repository import get_trip_by_trip_id
from app.core.config import settings
from app.core.enums import TripStatus, TripType
from app.core.exceptions import (
    DuplicateEntryError,
    ForbiddenError,
    TripNotFoundError,
)
from app.core.schemas import paginate, pagination_params


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
        1. Scope check BEFORE DB hit
        2. Trip must be IN_PROGRESS
        3. No duplicate for this student + trip + assignment_type
    Role check (DRIVER+) enforced at router.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise TripNotFoundError(identifier=trip_id)

    trip = await get_trip_by_trip_id(db, trip_id, school_id, branch_id)
    if trip.trip_status != TripStatus.IN_PROGRESS.value:
        raise ForbiddenError(
            detail=f"Cannot mark attendance on a {trip.trip_status} trip. Trip must be IN_PROGRESS."
        )

    existing = await attendance_repo.get_attendance_by_student_and_trip(
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

    record = await attendance_repo.create_attendance_record(
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
    """Fetch paginated attendance records for a trip. Scope check BEFORE DB hit."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise TripNotFoundError(identifier=trip_id)

    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)
    records, total = await attendance_repo.get_all_attendance_by_trip(
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
    """Fetch attendance history for a student across all trips. Scope check BEFORE DB hit."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise TripNotFoundError(identifier=student_id)

    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)
    records, total = await attendance_repo.get_all_attendance_by_student(
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
    """Correct an attendance record. Only status can change. Scope check BEFORE DB hit."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise TripNotFoundError(identifier=trip_id)

    record = await attendance_repo.update_attendance_status(
        db=db,
        attendance_id=attendance_id,
        trip_id=trip_id,
        school_id=school_id,
        new_status=payload.attendance_status,
    )
    return AttendanceResponse.model_validate(record)