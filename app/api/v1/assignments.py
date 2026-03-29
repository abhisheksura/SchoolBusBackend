from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.assignments import service as assignment_service
from app.assignments.schemas import (
    PaginatedAssignmentResponse,
    StudentRouteAssignmentCreate,
    StudentRouteAssignmentResponse,
)
from app.core.config import settings
from app.core.db import get_db
from app.core.enums import RoleName, TripType
from app.api.v1.dependencies import AnyAuthenticated, CurrentUser, require_roles

router = APIRouter(prefix = "/assignments")

AssignmentAdminRequired = Depends(
    require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN)
)


@router.post(
    "/",
    response_model=StudentRouteAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign student to route",
    description=(
        "Assign a student to a route + boarding stop for a trip_type. "
        "A separate assignment is required for PICKUP and DROPOFF. "
        "BRANCH_ADMIN or above required."
    ),
)
async def assign_student_to_route(
    payload: StudentRouteAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AssignmentAdminRequired,
) -> StudentRouteAssignmentResponse:
    return await assignment_service.assign_student_to_route(db=db, payload=payload)


@router.get(
    "/student/{student_id}",
    response_model=list[StudentRouteAssignmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get student route assignments",
    description="List all route assignments for a student (PICKUP + DROPOFF).",
)
async def get_student_assignments(
    student_id : int,
    school_id  : int  = Query(...),
    branch_id  : int  = Query(...),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> list[StudentRouteAssignmentResponse]:
    return await assignment_service.get_student_assignments(
        db=db,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
        active_only=active_only,
    )


@router.get(
    "/route/{route_id}",
    response_model=PaginatedAssignmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get route student assignments",
    description="List all students assigned to a route. Optionally filter by trip_type.",
)
async def get_route_assignments(
    route_id       : int,
    school_id      : int             = Query(...),
    branch_id      : int             = Query(...),
    page           : int             = Query(default=1, ge=1),
    page_size      : int             = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    assignment_type: TripType | None = Query(default=None, description="Filter by PICKUP or DROPOFF."),
    active_only    : bool            = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedAssignmentResponse:
    return await assignment_service.get_route_assignments(
        db=db,
        route_id=route_id,
        school_id=school_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
        assignment_type=assignment_type,
        active_only=active_only,
    )


@router.delete(
    "/{assignment_id}",
    response_model=StudentRouteAssignmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate student route assignment",
    description="Soft-delete a student route assignment. BRANCH_ADMIN or above required.",
)
async def deactivate_assignment(
    assignment_id: int,
    school_id    : int = Query(...),
    branch_id    : int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AssignmentAdminRequired,
) -> StudentRouteAssignmentResponse:
    return await assignment_service.deactivate_assignment(
        db=db,
        assignment_id=assignment_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )