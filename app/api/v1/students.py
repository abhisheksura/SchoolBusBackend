from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.students import service as student_service
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
from app.core.db import get_db
from app.core.enums import LeaveRequestStatus, RoleName
from app.api.v1.dependencies import (
    AnyAuthenticated,
    CurrentUser,
    require_roles,
)

router = APIRouter()

# Convenience alias — BRANCH_ADMIN, SCHOOL_ADMIN, SUPER_ADMIN
StudentAdminRequired = Depends(
    require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN)
)


# =============================================================================
# Student Routes
# =============================================================================

@router.post(
    "/students/",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create student",
    description="Create a new student. BRANCH_ADMIN or above required.",
)
async def create_student(
    payload: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = StudentAdminRequired,
) -> StudentResponse:
    return await student_service.create_student(db=db, payload=payload)


@router.get(
    "/students/",
    response_model=PaginatedStudentResponse,
    status_code=status.HTTP_200_OK,
    summary="List students",
    description="Fetch paginated students filtered by caller's branch scope.",
)
async def get_all_students(
    school_id  : int  = Query(...),
    branch_id  : int  = Query(...),
    page       : int  = Query(default=1, ge=1),
    page_size  : int  = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedStudentResponse:
    if not current_user.has_any_role(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN):
        active_only = True
    return await student_service.get_all_students(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        active_only=active_only,
    )


@router.get(
    "/students/{student_id}",
    response_model=StudentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get student",
    description="Fetch a single student. Returns 404 if outside caller's scope.",
)
async def get_student(
    student_id: int,
    school_id : int = Query(...),
    branch_id : int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> StudentResponse:
    return await student_service.get_student(
        db=db,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.patch(
    "/students/{student_id}",
    response_model=StudentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update student",
    description="Partially update a student. BRANCH_ADMIN or above required.",
)
async def update_student(
    student_id: int,
    payload   : StudentUpdate,
    school_id : int = Query(...),
    branch_id : int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = StudentAdminRequired,
) -> StudentResponse:
    return await student_service.update_student(
        db=db,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
    )


@router.delete(
    "/students/{student_id}",
    response_model=StudentResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate student",
    description="Soft-delete a student. BRANCH_ADMIN or above required.",
)
async def deactivate_student(
    student_id: int,
    school_id : int = Query(...),
    branch_id : int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = StudentAdminRequired,
) -> StudentResponse:
    return await student_service.deactivate_student(
        db=db,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
    )


# =============================================================================
# Parent Routes
# =============================================================================

@router.post(
    "/parents/",
    response_model=ParentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create parent",
    description="Create a new parent account. BRANCH_ADMIN or above required.",
)
async def create_parent(
    payload: ParentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = StudentAdminRequired,
) -> ParentResponse:
    return await student_service.create_parent(db=db, payload=payload)


@router.get(
    "/parents/",
    response_model=PaginatedParentResponse,
    status_code=status.HTTP_200_OK,
    summary="List parents",
    description="Fetch paginated parents for a school.",
)
async def get_all_parents(
    school_id  : int  = Query(...),
    page       : int  = Query(default=1, ge=1),
    page_size  : int  = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedParentResponse:
    if not current_user.has_any_role(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN):
        active_only = True
    return await student_service.get_all_parents(
        db=db,
        school_id=school_id,
        page=page,
        page_size=page_size,
        accessible_school_ids=current_user.get_accessible_school_ids(),
        active_only=active_only,
    )


@router.get(
    "/parents/{parent_id}",
    response_model=ParentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get parent",
    description="Fetch a single parent. Returns 404 if outside caller's scope.",
)
async def get_parent(
    parent_id: int,
    school_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> ParentResponse:
    return await student_service.get_parent(
        db=db,
        parent_id=parent_id,
        school_id=school_id,
        accessible_school_ids=current_user.get_accessible_school_ids(),
    )


@router.patch(
    "/parents/{parent_id}",
    response_model=ParentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update parent",
    description="Partially update a parent. BRANCH_ADMIN or above required.",
)
async def update_parent(
    parent_id: int,
    payload  : ParentUpdate,
    school_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = StudentAdminRequired,
) -> ParentResponse:
    return await student_service.update_parent(
        db=db,
        parent_id=parent_id,
        school_id=school_id,
        payload=payload,
    )


@router.delete(
    "/parents/{parent_id}",
    response_model=ParentResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate parent",
    description="Soft-delete a parent. BRANCH_ADMIN or above required.",
)
async def deactivate_parent(
    parent_id: int,
    school_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = StudentAdminRequired,
) -> ParentResponse:
    return await student_service.deactivate_parent(
        db=db,
        parent_id=parent_id,
        school_id=school_id,
    )


# =============================================================================
# Student-Parent Link Routes
# =============================================================================

@router.post(
    "/students/{student_id}/parents",
    response_model=StudentParentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Link parent to student",
    description="Link an existing parent to a student. BRANCH_ADMIN or above required.",
)
async def link_parent_to_student(
    student_id: int,
    payload   : StudentParentCreate,
    school_id : int = Query(...),
    branch_id : int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = StudentAdminRequired,
) -> StudentParentResponse:
    return await student_service.link_parent_to_student(
        db=db,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.get(
    "/students/{student_id}/parents",
    response_model=list[StudentParentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get student parents",
    description="List all parents linked to a student.",
)
async def get_student_parents(
    student_id: int,
    school_id : int = Query(...),
    branch_id : int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> list[StudentParentResponse]:
    return await student_service.get_student_parents(
        db=db,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.patch(
    "/students/{student_id}/parents/{student_parent_id}",
    response_model=StudentParentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update student-parent link",
    description="Update relationship label or primary flag. BRANCH_ADMIN or above required.",
)
async def update_student_parent_link(
    student_id       : int,
    student_parent_id: int,
    payload          : StudentParentUpdate,
    school_id        : int = Query(...),
    branch_id        : int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = StudentAdminRequired,
) -> StudentParentResponse:
    return await student_service.update_student_parent_link(
        db=db,
        student_parent_id=student_parent_id,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.delete(
    "/students/{student_id}/parents/{student_parent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlink parent from student",
    description="Remove student-parent relationship. BRANCH_ADMIN or above required.",
)
async def unlink_parent_from_student(
    student_id       : int,
    student_parent_id: int,
    school_id        : int = Query(...),
    branch_id        : int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = StudentAdminRequired,
) -> None:
    await student_service.unlink_parent_from_student(
        db=db,
        student_parent_id=student_parent_id,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


# =============================================================================
# Leave Request Routes
# =============================================================================

@router.post(
    "/students/{student_id}/leave-requests",
    response_model=LeaveRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit leave request",
    description="Submit a leave request for a student. Any authenticated user with branch access.",
)
async def create_leave_request(
    student_id: int,
    payload   : LeaveRequestCreate,
    school_id : int = Query(...),
    branch_id : int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> LeaveRequestResponse:
    return await student_service.create_leave_request(
        db=db,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
        requested_by_user_id=current_user.user_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.get(
    "/students/{student_id}/leave-requests",
    response_model=PaginatedLeaveRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="List leave requests",
    description="Fetch paginated leave requests for a student. Optionally filter by status.",
)
async def get_leave_requests(
    student_id   : int,
    school_id    : int = Query(...),
    branch_id    : int = Query(...),
    page         : int = Query(default=1, ge=1),
    page_size    : int = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    status_filter: LeaveRequestStatus | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedLeaveRequestResponse:
    return await student_service.get_leave_requests(
        db=db,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
        status_filter=status_filter,
    )


@router.patch(
    "/students/{student_id}/leave-requests/{leave_id}",
    response_model=LeaveRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve or reject leave request",
    description=(
        "Update the status of a leave request. "
        "Valid transitions: PENDING → APPROVED | REJECTED. "
        "BRANCH_ADMIN or above required."
    ),
)
async def update_leave_request_status(
    student_id: int,
    leave_id  : int,
    payload   : LeaveRequestUpdateStatus,
    school_id : int = Query(...),
    branch_id : int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = StudentAdminRequired,
) -> LeaveRequestResponse:
    return await student_service.update_leave_request_status(
        db=db,
        leave_id=leave_id,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )