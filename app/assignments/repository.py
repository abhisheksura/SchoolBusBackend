from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.assignments.models import StudentAttendance, StudentRouteAssignment
from app.core.enums import AttendanceStatus, TripType
from app.core.exceptions import (
    AttendanceNotFoundError,
    StudentAlreadyAssignedError,
    TripNotFoundError,
)


# =============================================================================
# StudentRouteAssignment Queries
# =============================================================================

async def get_assignment_by_id(
    db: AsyncSession,
    assignment_id: int,
    school_id: int,
    branch_id: int,
) -> StudentRouteAssignment:
    """Fetch a single assignment scoped to branch. Raises TripNotFoundError if not found."""
    result = await db.execute(
        select(StudentRouteAssignment).where(
            StudentRouteAssignment.assignment_id == assignment_id,
            StudentRouteAssignment.school_id == school_id,
            StudentRouteAssignment.branch_id == branch_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise TripNotFoundError(identifier=assignment_id)
    return assignment


async def get_active_assignment_by_student_and_type(
    db: AsyncSession,
    student_id: int,
    route_id: int,
    assignment_type: TripType,
    school_id: int,
    branch_id: int,
) -> StudentRouteAssignment | None:
    """Check if student already has an active assignment for this route + type."""
    result = await db.execute(
        select(StudentRouteAssignment).where(
            StudentRouteAssignment.student_id == student_id,
            StudentRouteAssignment.route_id == route_id,
            StudentRouteAssignment.assignment_type == assignment_type.value,
            StudentRouteAssignment.school_id == school_id,
            StudentRouteAssignment.branch_id == branch_id,
            StudentRouteAssignment.is_active == True,
        )
    )
    return result.scalar_one_or_none()


async def get_all_assignments_by_student(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
    active_only: bool = True,
) -> list[StudentRouteAssignment]:
    """Fetch all route assignments for a student."""
    query = select(StudentRouteAssignment).where(
        StudentRouteAssignment.student_id == student_id,
        StudentRouteAssignment.school_id == school_id,
        StudentRouteAssignment.branch_id == branch_id,
    )
    if active_only:
        query = query.where(StudentRouteAssignment.is_active == True)
    result = await db.execute(query.order_by(StudentRouteAssignment.assignment_type))
    return list(result.scalars().all())


async def get_all_assignments_by_route(
    db: AsyncSession,
    route_id: int,
    school_id: int,
    branch_id: int,
    limit: int,
    offset: int,
    assignment_type: TripType | None = None,
    active_only: bool = True,
) -> tuple[list[StudentRouteAssignment], int]:
    """Fetch all student assignments for a route with optional type filter."""
    query = select(StudentRouteAssignment).where(
        StudentRouteAssignment.route_id == route_id,
        StudentRouteAssignment.school_id == school_id,
        StudentRouteAssignment.branch_id == branch_id,
    )
    if assignment_type:
        query = query.where(StudentRouteAssignment.assignment_type == assignment_type.value)
    if active_only:
        query = query.where(StudentRouteAssignment.is_active == True)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(StudentRouteAssignment.assignment_type, StudentRouteAssignment.student_id)
        .limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def create_student_route_assignment(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    student_id: int,
    route_id: int,
    stop_id: int,
    assignment_type: TripType,
) -> StudentRouteAssignment:
    """Insert a new student route assignment. Caller must verify no duplicate exists."""
    assignment = StudentRouteAssignment(
        school_id=school_id,
        branch_id=branch_id,
        student_id=student_id,
        route_id=route_id,
        stop_id=stop_id,
        assignment_type=assignment_type.value,
    )
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    return assignment


async def deactivate_assignment_by_id(
    db: AsyncSession,
    assignment_id: int,
    school_id: int,
    branch_id: int,
) -> StudentRouteAssignment:
    """Soft-delete a student route assignment. Uses RETURNING — single round-trip."""
    result = await db.execute(
        update(StudentRouteAssignment)
        .where(
            StudentRouteAssignment.assignment_id == assignment_id,
            StudentRouteAssignment.school_id == school_id,
            StudentRouteAssignment.branch_id == branch_id,
        )
        .values(is_active=False, updated_at=func.now())
        .returning(StudentRouteAssignment)
    )
    await db.flush()
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise TripNotFoundError(identifier=assignment_id)
    return assignment


# =============================================================================
# StudentAttendance Queries
# =============================================================================

async def get_attendance_by_id(
    db: AsyncSession,
    attendance_id: int,
    trip_id: int,
    school_id: int,
) -> StudentAttendance:
    """Fetch an attendance record. Raises AttendanceNotFoundError if not found."""
    result = await db.execute(
        select(StudentAttendance).where(
            StudentAttendance.attendance_id == attendance_id,
            StudentAttendance.trip_id == trip_id,
            StudentAttendance.school_id == school_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise AttendanceNotFoundError(identifier=attendance_id)
    return record


async def get_attendance_by_student_and_trip(
    db: AsyncSession,
    student_id: int,
    trip_id: int,
    assignment_type: TripType,
    school_id: int,
    branch_id: int,
) -> StudentAttendance | None:
    """Check if attendance is already marked for this student + trip + type."""
    result = await db.execute(
        select(StudentAttendance).where(
            StudentAttendance.student_id == student_id,
            StudentAttendance.trip_id == trip_id,
            StudentAttendance.assignment_type == assignment_type.value,
            StudentAttendance.school_id == school_id,
            StudentAttendance.branch_id == branch_id,
        )
    )
    return result.scalar_one_or_none()


async def get_all_attendance_by_trip(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
    limit: int,
    offset: int,
    assignment_type: TripType | None = None,
) -> tuple[list[StudentAttendance], int]:
    """Fetch all attendance records for a trip with optional type filter."""
    query = select(StudentAttendance).where(
        StudentAttendance.trip_id == trip_id,
        StudentAttendance.school_id == school_id,
        StudentAttendance.branch_id == branch_id,
    )
    if assignment_type:
        query = query.where(StudentAttendance.assignment_type == assignment_type.value)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(StudentAttendance.marked_at).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def get_all_attendance_by_student(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
    limit: int,
    offset: int,
    trip_id: int | None = None,
) -> tuple[list[StudentAttendance], int]:
    """Fetch attendance history for a student with optional trip filter."""
    query = select(StudentAttendance).where(
        StudentAttendance.student_id == student_id,
        StudentAttendance.school_id == school_id,
        StudentAttendance.branch_id == branch_id,
    )
    if trip_id:
        query = query.where(StudentAttendance.trip_id == trip_id)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(StudentAttendance.marked_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def create_attendance_record(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    student_id: int,
    trip_id: int,
    assignment_type: TripType,
    attendance_status: AttendanceStatus,
    stop_id: int | None = None,
    marked_by_driver_id: int | None = None,
) -> StudentAttendance:
    """Create an attendance record. Caller must verify no duplicate exists."""
    record = StudentAttendance(
        school_id=school_id,
        branch_id=branch_id,
        student_id=student_id,
        trip_id=trip_id,
        assignment_type=assignment_type.value,
        attendance_status=attendance_status.value,
        stop_id=stop_id,
        marked_by_driver_id=marked_by_driver_id,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def update_attendance_status(
    db: AsyncSession,
    attendance_id: int,
    trip_id: int,
    school_id: int,
    new_status: AttendanceStatus,
) -> StudentAttendance:
    """Correct an attendance record status. Uses RETURNING — single round-trip."""
    result = await db.execute(
        update(StudentAttendance)
        .where(
            StudentAttendance.attendance_id == attendance_id,
            StudentAttendance.trip_id == trip_id,
            StudentAttendance.school_id == school_id,
        )
        .values(attendance_status=new_status.value)
        .returning(StudentAttendance)
    )
    await db.flush()
    record = result.scalar_one_or_none()
    if not record:
        raise AttendanceNotFoundError(identifier=attendance_id)
    return record