from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.assignments.models import StudentRouteAssignment
from app.core.enums import TripType
from app.core.exceptions import StudentAlreadyAssignedError, TripNotFoundError


async def get_assignment_by_id(
    db: AsyncSession,
    assignment_id: int,
    school_id: int,
    branch_id: int,
) -> StudentRouteAssignment:
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
    """Soft-delete. Uses RETURNING — single round-trip."""
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