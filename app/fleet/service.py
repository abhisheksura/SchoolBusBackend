from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.fleet import repository as fleet_repo
from app.fleet.schemas import (
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
from app.core.exceptions import (
    BusAlreadyHasDeviceError,
    BusNotFoundError,
    DeviceAlreadyAssignedError,
    DeviceNotFoundError,
    DriverNotFoundError,
    DuplicateEntryError,
)
from app.core.schemas import paginate, pagination_params


# =============================================================================
# Driver Services
# =============================================================================

async def create_driver(
    db: AsyncSession,
    payload: DriverCreate,
) -> DriverResponse:
    """
    Create a new driver.
    Role check (BRANCH_ADMIN+) enforced at router.
    Branch scope check enforced at router.
    """
    driver = await fleet_repo.create_driver(
        db=db,
        school_id=payload.school_id,
        branch_id=payload.branch_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        license_number=payload.license_number,
    )
    return DriverResponse.model_validate(driver)


async def get_driver(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> DriverResponse:
    """
    Fetch a single driver.
    Scope check BEFORE DB hit — 404 on violation.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise DriverNotFoundError(identifier=driver_id)

    driver = await fleet_repo.get_driver_by_driver_id(db, driver_id, school_id, branch_id)
    return DriverResponse.model_validate(driver)


async def get_all_drivers(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    page: int,
    page_size: int,
    accessible_branch_ids: list[int] | None,
    active_only: bool = True,
) -> PaginatedDriverResponse:
    """Fetch paginated drivers for a branch, filtered by caller's scope."""
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)

    if accessible_branch_ids is None:
        drivers, total = await fleet_repo.get_all_drivers_by_branch(
            db=db, school_id=school_id, branch_id=branch_id,
            limit=limit, offset=offset, active_only=active_only,
        )
    else:
        drivers, total = await fleet_repo.get_drivers_by_branch_ids(
            db=db, school_id=school_id, branch_ids=accessible_branch_ids,
            limit=limit, offset=offset, active_only=active_only,
        )

    return paginate(
        items=[DriverResponse.model_validate(d) for d in drivers],
        total=total, page=page, page_size=page_size,
    )


async def update_driver(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
    payload: DriverUpdate,
) -> DriverResponse:
    """Update a driver. Role check enforced at router."""
    driver = await fleet_repo.update_driver_by_driver_id(
        db=db,
        driver_id=driver_id,
        school_id=school_id,
        branch_id=branch_id,
        **payload.model_dump(exclude_unset=True),
    )
    return DriverResponse.model_validate(driver)


async def deactivate_driver(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
) -> DriverResponse:
    """Soft-delete a driver. Role check enforced at router."""
    driver = await fleet_repo.deactivate_driver_by_driver_id(
        db, driver_id, school_id, branch_id
    )
    return DriverResponse.model_validate(driver)


# =============================================================================
# Bus Services
# =============================================================================

async def create_bus(
    db: AsyncSession,
    payload: BusCreate,
) -> BusResponse:
    """
    Create a new bus.
    Role check (BRANCH_ADMIN+) enforced at router.
    """
    try:
        bus = await fleet_repo.create_bus(
            db=db,
            school_id=payload.school_id,
            branch_id=payload.branch_id,
            bus_number=payload.bus_number,
            capacity=payload.capacity,
        )
    except IntegrityError:
        raise DuplicateEntryError(field="bus_number", value=payload.bus_number)
    return BusResponse.model_validate(bus)


async def get_bus(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> BusResponse:
    """Fetch a single bus. Scope check BEFORE DB hit."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise BusNotFoundError(identifier=bus_id)

    bus = await fleet_repo.get_bus_by_bus_id(db, bus_id, school_id, branch_id)
    return BusResponse.model_validate(bus)


async def get_all_buses(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    page: int,
    page_size: int,
    accessible_branch_ids: list[int] | None,
    active_only: bool = True,
) -> PaginatedBusResponse:
    """Fetch paginated buses for a branch, filtered by caller's scope."""
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)

    if accessible_branch_ids is None:
        buses, total = await fleet_repo.get_all_buses_by_branch(
            db=db, school_id=school_id, branch_id=branch_id,
            limit=limit, offset=offset, active_only=active_only,
        )
    else:
        buses, total = await fleet_repo.get_buses_by_branch_ids(
            db=db, school_id=school_id, branch_ids=accessible_branch_ids,
            limit=limit, offset=offset, active_only=active_only,
        )

    return paginate(
        items=[BusResponse.model_validate(b) for b in buses],
        total=total, page=page, page_size=page_size,
    )


async def update_bus(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
    payload: BusUpdate,
) -> BusResponse:
    """Update a bus. Role check enforced at router."""
    try:
        bus = await fleet_repo.update_bus_by_bus_id(
            db=db,
            bus_id=bus_id,
            school_id=school_id,
            branch_id=branch_id,
            **payload.model_dump(exclude_unset=True),
        )
    except IntegrityError:
        raise DuplicateEntryError(field="bus_number", value=payload.bus_number or "")
    return BusResponse.model_validate(bus)


async def deactivate_bus(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
) -> BusResponse:
    """Soft-delete a bus. Role check enforced at router."""
    bus = await fleet_repo.deactivate_bus_by_bus_id(db, bus_id, school_id, branch_id)
    return BusResponse.model_validate(bus)


# =============================================================================
# GPS Device Services
# =============================================================================

async def create_device(
    db: AsyncSession,
    payload: GPSDeviceCreate,
) -> GPSDeviceResponse:
    """
    Create a new GPS device.
    Checks IMEI uniqueness before insert for a clean error message.
    Role check (BRANCH_ADMIN+) enforced at router.
    """
    existing = await fleet_repo.get_device_by_device_imei_or_none(db, payload.device_imei)
    if existing:
        raise DuplicateEntryError(field="device_imei", value=payload.device_imei)

    device = await fleet_repo.create_device(
        db=db,
        school_id=payload.school_id,
        branch_id=payload.branch_id,
        device_imei=payload.device_imei,
    )
    return GPSDeviceResponse.model_validate(device)


async def get_device(
    db: AsyncSession,
    device_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> GPSDeviceResponse:
    """Fetch a single GPS device. Scope check BEFORE DB hit."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise DeviceNotFoundError(identifier=device_id)

    device = await fleet_repo.get_device_by_device_id(db, device_id, school_id, branch_id)
    return GPSDeviceResponse.model_validate(device)


async def get_all_devices(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    page: int,
    page_size: int,
    accessible_branch_ids: list[int] | None,
    active_only: bool = True,
) -> PaginatedDeviceResponse:
    """Fetch paginated GPS devices for a branch, filtered by caller's scope."""
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)

    if accessible_branch_ids is None:
        devices, total = await fleet_repo.get_all_devices_by_branch(
            db=db, school_id=school_id, branch_id=branch_id,
            limit=limit, offset=offset, active_only=active_only,
        )
    else:
        devices, total = await fleet_repo.get_devices_by_branch_ids(
            db=db, school_id=school_id, branch_ids=accessible_branch_ids,
            limit=limit, offset=offset, active_only=active_only,
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
    """Update a GPS device. Role check enforced at router."""
    device = await fleet_repo.update_device_by_device_id(
        db=db,
        device_id=device_id,
        school_id=school_id,
        branch_id=branch_id,
        **payload.model_dump(exclude_unset=True),
    )
    return GPSDeviceResponse.model_validate(device)


async def deactivate_device(
    db: AsyncSession,
    device_id: int,
    school_id: int,
    branch_id: int,
) -> GPSDeviceResponse:
    """Soft-delete a GPS device. Role check enforced at router."""
    device = await fleet_repo.deactivate_device_by_device_id(
        db, device_id, school_id, branch_id
    )
    return GPSDeviceResponse.model_validate(device)


# =============================================================================
# Bus Device Assignment Services
# =============================================================================

async def assign_device_to_bus(
    db: AsyncSession,
    bus_id: int,
    device_id: int,
    school_id: int,
    branch_id: int,
) -> BusDeviceAssignmentResponse:
    """
    Assign a GPS device to a bus.

    Checks (in order — scope check first, no DB hits if unauthorized):
        1. Bus exists and is active in this branch
        2. Device exists and is active in this branch
        3. Bus has no active assignment already
        4. Device has no active assignment already

    The DB partial unique index is the final guard against race conditions.
    """
    # Verify bus and device exist in this branch
    bus = await fleet_repo.get_bus_by_bus_id(db, bus_id, school_id, branch_id)
    if not bus.is_active:
        raise BusNotFoundError(identifier=bus_id)

    device = await fleet_repo.get_device_by_device_id(db, device_id, school_id, branch_id)
    if not device.is_active:
        raise DeviceNotFoundError(identifier=device_id)

    # Check bus doesn't already have an active device
    existing_bus_assignment = await fleet_repo.get_active_assignment_by_bus_id(
        db, bus_id, school_id, branch_id
    )
    if existing_bus_assignment:
        raise BusAlreadyHasDeviceError()

    # Check device isn't already assigned to another bus
    existing_device_assignment = await fleet_repo.get_active_assignment_by_device_id(
        db, device_id, school_id, branch_id
    )
    if existing_device_assignment:
        raise DeviceAlreadyAssignedError()

    assignment = await fleet_repo.create_bus_device_assignment(
        db=db,
        bus_id=bus_id,
        device_id=device_id,
        school_id=school_id,
        branch_id=branch_id,
    )
    return BusDeviceAssignmentResponse.model_validate(assignment)


async def unassign_device_from_bus(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
) -> BusDeviceAssignmentResponse:
    """
    Unassign the active GPS device from a bus by closing the assignment.
    Raises BusNotFoundError if bus has no active device assignment.
    """
    assignment = await fleet_repo.get_active_assignment_by_bus_id(
        db, bus_id, school_id, branch_id
    )
    if not assignment:
        raise BusNotFoundError(identifier=bus_id)

    closed = await fleet_repo.close_assignment_by_bus_device_id(
        db, assignment.bus_device_id
    )
    return BusDeviceAssignmentResponse.model_validate(closed)


async def get_active_device_for_bus(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> BusDeviceAssignmentResponse:
    """
    Get the currently active GPS device assignment for a bus.
    Scope check BEFORE DB hit.
    Raises BusNotFoundError if no active assignment.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise BusNotFoundError(identifier=bus_id)

    assignment = await fleet_repo.get_active_assignment_by_bus_id(
        db, bus_id, school_id, branch_id
    )
    if not assignment:
        raise BusNotFoundError(identifier=bus_id)

    return BusDeviceAssignmentResponse.model_validate(assignment)