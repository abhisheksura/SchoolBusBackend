from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.assignments import repository as assignment_repo
from app.assignments.schemas import (
    PaginatedAssignmentResponse,
    StudentRouteAssignmentCreate,
    StudentRouteAssignmentResponse,
)
from app.core.config import settings
from app.core.enums import TripType
from app.core.exceptions import StudentAlreadyAssignedError, TripNotFoundError
from app.core.schemas import paginate, pagination_params


async def assign_student_to_route(
    db: AsyncSession,
    payload: StudentRouteAssignmentCreate,
) -> StudentRouteAssignmentResponse:
    """
    Assign a student to a route + stop for a trip_type.
    One active assignment per student per route per type.
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
    """Scope check BEFORE DB hit."""
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
    """Scope check BEFORE DB hit."""
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
    """Scope check BEFORE DB hit. Role check enforced at router."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise TripNotFoundError(identifier=assignment_id)

    assignment = await assignment_repo.deactivate_assignment_by_id(
        db, assignment_id, school_id, branch_id
    )
    return StudentRouteAssignmentResponse.model_validate(assignment)