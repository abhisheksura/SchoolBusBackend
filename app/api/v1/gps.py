from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.gps import service as gps_service
from app.gps.schemas import (
    AssignDeviceRequest,
    BusDeviceAssignmentResponse,
    GPSDeviceCreate,
    GPSDeviceResponse,
    GPSDeviceUpdate,
    PaginatedGPSDeviceResponse,
)
from app.core.config import settings
from app.core.db import get_db
from app.core.enums import RoleName
from app.api.v1.dependencies import AnyAuthenticated, CurrentUser, require_roles

router = APIRouter()

GPSAdminRequired = Depends(
    require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN)
)


# =============================================================================
# GPS Device Routes — /gps/devices/
# =============================================================================

@router.post(
    "/devices/",
    response_model=GPSDeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register GPS device",
    description="Register a new GPS device by IMEI. BRANCH_ADMIN or above required.",
)
async def create_device(
    payload: GPSDeviceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = GPSAdminRequired,
) -> GPSDeviceResponse:
    return await gps_service.create_device(db=db, payload=payload)


@router.get(
    "/devices/",
    response_model=PaginatedGPSDeviceResponse,
    status_code=status.HTTP_200_OK,
    summary="List GPS devices",
    description="Fetch paginated GPS devices filtered by caller's branch scope.",
)
async def get_all_devices(
    school_id  : int  = Query(...),
    branch_id  : int  = Query(...),
    page       : int  = Query(default=1, ge=1),
    page_size  : int  = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedGPSDeviceResponse:
    if not current_user.has_any_role(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN):
        active_only = True
    return await gps_service.get_all_devices(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
        active_only=active_only,
    )


@router.get(
    "/devices/{device_id}",
    response_model=GPSDeviceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get GPS device",
    description="Fetch a single GPS device. Returns 404 if outside caller's scope.",
)
async def get_device(
    device_id: int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> GPSDeviceResponse:
    return await gps_service.get_device(
        db=db,
        device_id=device_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.patch(
    "/devices/{device_id}",
    response_model=GPSDeviceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update GPS device",
    description="Update a GPS device (is_active only — IMEI is immutable). BRANCH_ADMIN or above required.",
)
async def update_device(
    device_id: int,
    payload  : GPSDeviceUpdate,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = GPSAdminRequired,
) -> GPSDeviceResponse:
    return await gps_service.update_device(
        db=db, device_id=device_id, school_id=school_id, branch_id=branch_id, payload=payload,
    )


@router.delete(
    "/devices/{device_id}",
    response_model=GPSDeviceResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate GPS device",
    description="Soft-delete a GPS device. BRANCH_ADMIN or above required.",
)
async def deactivate_device(
    device_id: int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = GPSAdminRequired,
) -> GPSDeviceResponse:
    return await gps_service.deactivate_device(
        db=db, device_id=device_id, school_id=school_id, branch_id=branch_id,
    )


# =============================================================================
# Bus-Device Assignment Routes
# =============================================================================

@router.post(
    "/devices/{device_id}/assign",
    response_model=BusDeviceAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign GPS device to bus",
    description=(
        "Assign this GPS device to a bus. "
        "Fails if device or bus already has an active assignment. "
        "BRANCH_ADMIN or above required."
    ),
)
async def assign_device_to_bus(
    device_id: int,
    payload  : AssignDeviceRequest,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = GPSAdminRequired,
) -> BusDeviceAssignmentResponse:
    return await gps_service.assign_device_to_bus(
        db=db, device_id=device_id, school_id=school_id, branch_id=branch_id, payload=payload,
    )


@router.post(
    "/devices/{device_id}/unassign",
    response_model=BusDeviceAssignmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Unassign GPS device from bus",
    description=(
        "Close the active bus assignment for this GPS device. "
        "Returns 404 if the device has no active assignment. "
        "BRANCH_ADMIN or above required."
    ),
)
async def unassign_device_from_bus(
    device_id: int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = GPSAdminRequired,
) -> BusDeviceAssignmentResponse:
    return await gps_service.unassign_device_from_bus(
        db=db, device_id=device_id, school_id=school_id, branch_id=branch_id,
    )


@router.get(
    "/buses/{bus_id}/device",
    response_model=BusDeviceAssignmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get active GPS device for bus",
    description=(
        "Get the currently active GPS device assignment for a bus. "
        "Returns 404 if bus has no active device or outside caller's scope."
    ),
)
async def get_active_device_for_bus(
    bus_id   : int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> BusDeviceAssignmentResponse:
    return await gps_service.get_active_device_for_bus(
        db=db,
        bus_id=bus_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )