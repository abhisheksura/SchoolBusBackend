from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.attendance import service as attendance_service
from app.attendance.schemas import (
    AttendanceMarkRequest,
    AttendanceResponse,
    AttendanceUpdateRequest,
    PaginatedAttendanceResponse,
)
from app.core.config import settings
from app.core.db import get_db
from app.core.enums import RoleName, TripType
from app.api.v1.dependencies import AnyAuthenticated, CurrentUser, require_roles

router = APIRouter(prefix = "/attendance")

AttendanceAdminRequired = Depends(
    require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN)
)
DriverOrAdminRequired = Depends(
    require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN, RoleName.DRIVER)
)


@router.post(
    "/trips/{trip_id}",
    response_model=AttendanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mark student attendance",
    description=(
        "Mark attendance for a student on an IN_PROGRESS trip. "
        "Fails if attendance already marked for this student + trip + type. "
        "DRIVER or above required."
    ),
)
async def mark_attendance(
    trip_id  : int,
    payload  : AttendanceMarkRequest,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = DriverOrAdminRequired,
) -> AttendanceResponse:
    return await attendance_service.mark_attendance(
        db=db,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.get(
    "/trips/{trip_id}",
    response_model=PaginatedAttendanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get trip attendance",
    description="Fetch paginated attendance records for a trip. Optionally filter by trip_type.",
)
async def get_trip_attendance(
    trip_id        : int,
    school_id      : int             = Query(...),
    branch_id      : int             = Query(...),
    page           : int             = Query(default=1, ge=1),
    page_size      : int             = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    assignment_type: TripType | None = Query(default=None, description="Filter by PICKUP or DROPOFF."),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedAttendanceResponse:
    return await attendance_service.get_trip_attendance(
        db=db,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
        assignment_type=assignment_type,
    )


@router.get(
    "/students/{student_id}",
    response_model=PaginatedAttendanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get student attendance history",
    description="Fetch attendance history for a student across all trips. Optionally filter by trip_id.",
)
async def get_student_attendance(
    student_id: int,
    school_id : int          = Query(...),
    branch_id : int          = Query(...),
    page      : int          = Query(default=1, ge=1),
    page_size : int          = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    trip_id   : int | None   = Query(default=None, description="Filter by a specific trip."),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedAttendanceResponse:
    return await attendance_service.get_student_attendance(
        db=db,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
        trip_id=trip_id,
    )


@router.patch(
    "/trips/{trip_id}/{attendance_id}",
    response_model=AttendanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Correct attendance record",
    description=(
        "Update the status of an attendance record. "
        "Only attendance_status can be changed. "
        "BRANCH_ADMIN or above required."
    ),
)
async def update_attendance(
    trip_id      : int,
    attendance_id: int,
    payload      : AttendanceUpdateRequest,
    school_id    : int = Query(...),
    branch_id    : int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AttendanceAdminRequired,
) -> AttendanceResponse:
    return await attendance_service.update_attendance(
        db=db,
        attendance_id=attendance_id,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )