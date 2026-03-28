from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.fleet import service as fleet_service
from app.fleet.schemas import (
    AssignDeviceRequest,
    BusCreate,
    BusDeviceAssignmentResponse,
    BusResponse,
    BusUpdate,
    DriverCreate,
    DriverResponse,
    DriverUpdate,
    GPSDeviceCreate,
    GPSDeviceResponse,
    GPSDeviceUpdate,
    PaginatedBusResponse,
    PaginatedDeviceResponse,
    PaginatedDriverResponse,
)
from app.core.config import settings
from app.core.db import get_db
from app.core.enums import RoleName
from app.api.v1.dependencies import (
    AnyAuthenticated,
    CurrentUser,
    require_roles,
)

router = APIRouter()

# Convenience alias — BRANCH_ADMIN, SCHOOL_ADMIN, SUPER_ADMIN
FleetAdminRequired = Depends(
    require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN)
)


# =============================================================================
# Driver Routes
# =============================================================================

@router.post(
    "/drivers/",
    response_model=DriverResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create driver",
    description="Create a new driver. BRANCH_ADMIN or above required.",
)
async def create_driver(
    payload: DriverCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = FleetAdminRequired,
) -> DriverResponse:
    return await fleet_service.create_driver(db=db, payload=payload)


@router.get(
    "/drivers/",
    response_model=PaginatedDriverResponse,
    status_code=status.HTTP_200_OK,
    summary="List drivers",
    description="Fetch paginated drivers filtered by caller's branch scope.",
)
async def get_all_drivers(
    school_id  : int  = Query(..., description="School ID"),
    branch_id  : int  = Query(..., description="Branch ID"),
    page       : int  = Query(default=1, ge=1),
    page_size  : int  = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedDriverResponse:
    if not current_user.has_any_role(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN):
        active_only = True
    return await fleet_service.get_all_drivers(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
        active_only=active_only,
    )


@router.get(
    "/drivers/{driver_id}",
    response_model=DriverResponse,
    status_code=status.HTTP_200_OK,
    summary="Get driver",
    description="Fetch a single driver. Returns 404 if outside caller's scope.",
)
async def get_driver(
    driver_id: int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> DriverResponse:
    return await fleet_service.get_driver(
        db=db,
        driver_id=driver_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.patch(
    "/drivers/{driver_id}",
    response_model=DriverResponse,
    status_code=status.HTTP_200_OK,
    summary="Update driver",
    description="Partially update a driver. BRANCH_ADMIN or above required.",
)
async def update_driver(
    driver_id: int,
    payload  : DriverUpdate,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = FleetAdminRequired,
) -> DriverResponse:
    return await fleet_service.update_driver(
        db=db,
        driver_id=driver_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
    )


@router.delete(
    "/drivers/{driver_id}",
    response_model=DriverResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate driver",
    description="Soft-delete a driver. BRANCH_ADMIN or above required.",
)
async def deactivate_driver(
    driver_id: int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = FleetAdminRequired,
) -> DriverResponse:
    return await fleet_service.deactivate_driver(
        db=db,
        driver_id=driver_id,
        school_id=school_id,
        branch_id=branch_id,
    )


# =============================================================================
# Bus Routes
# =============================================================================

@router.post(
    "/buses/",
    response_model=BusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create bus",
    description="Create a new bus. BRANCH_ADMIN or above required.",
)
async def create_bus(
    payload: BusCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = FleetAdminRequired,
) -> BusResponse:
    return await fleet_service.create_bus(db=db, payload=payload)


@router.get(
    "/buses/",
    response_model=PaginatedBusResponse,
    status_code=status.HTTP_200_OK,
    summary="List buses",
    description="Fetch paginated buses filtered by caller's branch scope.",
)
async def get_all_buses(
    school_id  : int  = Query(...),
    branch_id  : int  = Query(...),
    page       : int  = Query(default=1, ge=1),
    page_size  : int  = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedBusResponse:
    if not current_user.has_any_role(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN):
        active_only = True
    return await fleet_service.get_all_buses(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
        active_only=active_only,
    )


@router.get(
    "/buses/{bus_id}",
    response_model=BusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get bus",
    description="Fetch a single bus. Returns 404 if outside caller's scope.",
)
async def get_bus(
    bus_id   : int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> BusResponse:
    return await fleet_service.get_bus(
        db=db,
        bus_id=bus_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.patch(
    "/buses/{bus_id}",
    response_model=BusResponse,
    status_code=status.HTTP_200_OK,
    summary="Update bus",
    description="Partially update a bus. BRANCH_ADMIN or above required.",
)
async def update_bus(
    bus_id   : int,
    payload  : BusUpdate,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = FleetAdminRequired,
) -> BusResponse:
    return await fleet_service.update_bus(
        db=db,
        bus_id=bus_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
    )


@router.delete(
    "/buses/{bus_id}",
    response_model=BusResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate bus",
    description="Soft-delete a bus. BRANCH_ADMIN or above required.",
)
async def deactivate_bus(
    bus_id   : int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = FleetAdminRequired,
) -> BusResponse:
    return await fleet_service.deactivate_bus(
        db=db,
        bus_id=bus_id,
        school_id=school_id,
        branch_id=branch_id,
    )


# =============================================================================
# GPS Device Routes
# =============================================================================

@router.post(
    "/devices/",
    response_model=GPSDeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create GPS device",
    description="Register a new GPS device. BRANCH_ADMIN or above required.",
)
async def create_device(
    payload: GPSDeviceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = FleetAdminRequired,
) -> GPSDeviceResponse:
    return await fleet_service.create_device(db=db, payload=payload)


@router.get(
    "/devices/",
    response_model=PaginatedDeviceResponse,
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
) -> PaginatedDeviceResponse:
    if not current_user.has_any_role(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN):
        active_only = True
    return await fleet_service.get_all_devices(
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
    return await fleet_service.get_device(
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
    description="Update a GPS device. BRANCH_ADMIN or above required.",
)
async def update_device(
    device_id: int,
    payload  : GPSDeviceUpdate,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = FleetAdminRequired,
) -> GPSDeviceResponse:
    return await fleet_service.update_device(
        db=db,
        device_id=device_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
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
    current_user: CurrentUser = FleetAdminRequired,
) -> GPSDeviceResponse:
    return await fleet_service.deactivate_device(
        db=db,
        device_id=device_id,
        school_id=school_id,
        branch_id=branch_id,
    )


# =============================================================================
# Bus Device Assignment Routes
# =============================================================================

@router.post(
    "/buses/{bus_id}/assign-device",
    response_model=BusDeviceAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign GPS device to bus",
    description=(
        "Assign an active GPS device to a bus. "
        "Fails if bus already has an active device or device is already assigned. "
        "BRANCH_ADMIN or above required."
    ),
)
async def assign_device_to_bus(
    bus_id   : int,
    payload  : AssignDeviceRequest,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = FleetAdminRequired,
) -> BusDeviceAssignmentResponse:
    return await fleet_service.assign_device_to_bus(
        db=db,
        bus_id=bus_id,
        device_id=payload.device_id,
        school_id=school_id,
        branch_id=branch_id,
    )


@router.post(
    "/buses/{bus_id}/unassign-device",
    response_model=BusDeviceAssignmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Unassign GPS device from bus",
    description=(
        "Close the active GPS device assignment for a bus. "
        "Returns 404 if bus has no active device assignment. "
        "BRANCH_ADMIN or above required."
    ),
)
async def unassign_device_from_bus(
    bus_id   : int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = FleetAdminRequired,
) -> BusDeviceAssignmentResponse:
    return await fleet_service.unassign_device_from_bus(
        db=db,
        bus_id=bus_id,
        school_id=school_id,
        branch_id=branch_id,
    )


@router.get(
    "/buses/{bus_id}/device",
    response_model=BusDeviceAssignmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get active device for bus",
    description=(
        "Get the currently active GPS device assignment for a bus. "
        "Returns 404 if no active assignment or outside caller's scope."
    ),
)
async def get_active_device_for_bus(
    bus_id   : int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> BusDeviceAssignmentResponse:
    return await fleet_service.get_active_device_for_bus(
        db=db,
        bus_id=bus_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )