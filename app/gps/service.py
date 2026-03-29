from sqlalchemy.ext.asyncio import AsyncSession

from app.gps import repository as gps_repo
from app.gps.schemas import (
    AssignDeviceRequest,
    BusDeviceAssignmentResponse,
    GPSDeviceCreate,
    GPSDeviceResponse,
    GPSDeviceUpdate,
    PaginatedGPSDeviceResponse,
)
from app.core.config import settings
from app.core.exceptions import (
    BusAlreadyHasDeviceError,
    BusNotFoundError,
    DeviceAlreadyAssignedError,
    DeviceNotFoundError,
    DuplicateEntryError,
)
from app.core.schemas import paginate, pagination_params


# =============================================================================
# GPSDevice Services
# =============================================================================

async def create_device(db: AsyncSession, payload: GPSDeviceCreate) -> GPSDeviceResponse:
    """Role check (BRANCH_ADMIN+) enforced at router."""
    existing = await gps_repo.get_device_by_imei_or_none(db, payload.device_imei)
    if existing:
        raise DuplicateEntryError(field="device_imei", value=payload.device_imei)
    device = await gps_repo.create_device(
        db=db, school_id=payload.school_id, branch_id=payload.branch_id, device_imei=payload.device_imei,
    )
    return GPSDeviceResponse.model_validate(device)


async def get_device(
    db: AsyncSession,
    device_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> GPSDeviceResponse:
    """Scope check BEFORE DB hit."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise DeviceNotFoundError(identifier=device_id)
    device = await gps_repo.get_device_by_device_id(db, device_id, school_id, branch_id)
    return GPSDeviceResponse.model_validate(device)


async def get_all_devices(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    page: int,
    page_size: int,
    accessible_branch_ids: list[int] | None,
    active_only: bool = True,
) -> PaginatedGPSDeviceResponse:
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)
    if accessible_branch_ids is None:
        devices, total = await gps_repo.get_all_devices_by_branch(
            db, school_id, branch_id, limit, offset, active_only
        )
    else:
        devices, total = await gps_repo.get_devices_by_branch_ids(
            db, school_id, accessible_branch_ids, limit, offset, active_only
        )
    return paginate(
        items=[GPSDeviceResponse.model_validate(d) for d in devices],
        total=total, page=page, page_size=page_size,
    )


async def update_device(
    db: AsyncSession,
    device_id: int,
    school_id: int,
    branch_id: int,
    payload: GPSDeviceUpdate,
) -> GPSDeviceResponse:
    device = await gps_repo.update_device_by_device_id(
        db, device_id, school_id, branch_id,
        **payload.model_dump(exclude_unset=True),
    )
    return GPSDeviceResponse.model_validate(device)


async def deactivate_device(
    db: AsyncSession,
    device_id: int,
    school_id: int,
    branch_id: int,
) -> GPSDeviceResponse:
    device = await gps_repo.deactivate_device_by_device_id(db, device_id, school_id, branch_id)
    return GPSDeviceResponse.model_validate(device)


# =============================================================================
# BusDeviceAssignment Services
# =============================================================================

async def assign_device_to_bus(
    db: AsyncSession,
    device_id: int,
    school_id: int,
    branch_id: int,
    payload: AssignDeviceRequest,
) -> BusDeviceAssignmentResponse:
    """
    Assign a GPS device to a bus.
    Checks (scope first, no DB hits if unauthorized):
        1. Device exists and is active
        2. Bus has no existing active device
        3. Device is not already assigned to another bus
    DB partial unique index is the final race-condition guard.
    """
    device = await gps_repo.get_device_by_device_id(db, device_id, school_id, branch_id)
    if not device.is_active:
        raise DeviceNotFoundError(identifier=device_id)

    existing_bus_assignment = await gps_repo.get_active_assignment_by_bus_id(
        db, payload.bus_id, school_id, branch_id
    )
    if existing_bus_assignment:
        raise BusAlreadyHasDeviceError()

    existing_device_assignment = await gps_repo.get_active_assignment_by_device_id(
        db, device_id, school_id, branch_id
    )
    if existing_device_assignment:
        raise DeviceAlreadyAssignedError()

    assignment = await gps_repo.create_bus_device_assignment(
        db=db, bus_id=payload.bus_id, device_id=device_id, school_id=school_id, branch_id=branch_id,
    )
    return BusDeviceAssignmentResponse.model_validate(assignment)


async def unassign_device_from_bus(
    db: AsyncSession,
    device_id: int,
    school_id: int,
    branch_id: int,
) -> BusDeviceAssignmentResponse:
    """
    Unassign a GPS device from its current bus.
    Raises DeviceNotFoundError if device has no active assignment.
    """
    assignment = await gps_repo.get_active_assignment_by_device_id(
        db, device_id, school_id, branch_id
    )
    if not assignment:
        raise DeviceNotFoundError(identifier=device_id)

    closed = await gps_repo.close_assignment_by_id(db, assignment.bus_device_id)
    return BusDeviceAssignmentResponse.model_validate(closed)


async def get_active_device_for_bus(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> BusDeviceAssignmentResponse:
    """
    Get the currently active GPS device for a bus.
    Scope check BEFORE DB hit.
    Raises BusNotFoundError if no active assignment.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise BusNotFoundError(identifier=bus_id)

    assignment = await gps_repo.get_active_assignment_by_bus_id(db, bus_id, school_id, branch_id)
    if not assignment:
        raise BusNotFoundError(identifier=bus_id)

    return BusDeviceAssignmentResponse.model_validate(assignment)