from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.attendance.models import StudentAttendance
from app.core.enums import AttendanceStatus, TripType
from app.core.exceptions import AttendanceNotFoundError


async def get_attendance_by_id(
    db: AsyncSession,
    attendance_id: int,
    trip_id: int,
    school_id: int,
) -> StudentAttendance:
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
    """Check if attendance already marked for this student + trip + type."""
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
    query = select(StudentAttendance).where(
        StudentAttendance.trip_id == trip_id,
        StudentAttendance.school_id == school_id,
        StudentAttendance.branch_id == branch_id,
    )
    if assignment_type:
        query = query.where(StudentAttendance.assignment_type == assignment_type.value)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(StudentAttendance.marked_at).limit(limit).offset(offset))
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
    query = select(StudentAttendance).where(
        StudentAttendance.student_id == student_id,
        StudentAttendance.school_id == school_id,
        StudentAttendance.branch_id == branch_id,
    )
    if trip_id:
        query = query.where(StudentAttendance.trip_id == trip_id)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(StudentAttendance.marked_at.desc()).limit(limit).offset(offset))
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