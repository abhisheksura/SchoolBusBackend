from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.fleet.models import Bus, BusDeviceAssignment, Driver, GPSDevice
from app.core.exceptions import (
    BusNotFoundError,
    DeviceNotFoundError,
    DriverNotFoundError,
    DeviceAlreadyAssignedError,
    BusAlreadyHasDeviceError,
)
from app.core.utils import utcnow


# =============================================================================
# Driver Queries
# =============================================================================

async def get_driver_by_driver_id(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
) -> Driver:
    """Fetch a driver scoped to branch. Raises DriverNotFoundError if not found."""
    result = await db.execute(
        select(Driver).where(
            Driver.driver_id == driver_id,
            Driver.school_id == school_id,
            Driver.branch_id == branch_id,
        )
    )
    driver = result.scalar_one_or_none()
    if not driver:
        raise DriverNotFoundError(identifier=driver_id)
    return driver


async def get_driver_by_driver_id_or_none(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
) -> Driver | None:
    """Fetch a driver scoped to branch. Returns None if not found."""
    result = await db.execute(
        select(Driver).where(
            Driver.driver_id == driver_id,
            Driver.school_id == school_id,
            Driver.branch_id == branch_id,
        )
    )
    return result.scalar_one_or_none()


async def get_all_drivers_by_branch(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Driver], int]:
    """Fetch all drivers for a branch with pagination."""
    query = select(Driver).where(
        Driver.school_id == school_id,
        Driver.branch_id == branch_id,
    )
    if active_only:
        query = query.where(Driver.is_active == True)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(Driver.first_name).limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0


async def get_drivers_by_branch_ids(
    db: AsyncSession,
    school_id: int,
    branch_ids: list[int],
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Driver], int]:
    """Fetch drivers filtered to a list of branch_ids within a school."""
    query = select(Driver).where(
        Driver.school_id == school_id,
        Driver.branch_id.in_(branch_ids),
    )
    if active_only:
        query = query.where(Driver.is_active == True)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(Driver.first_name).limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0


async def create_driver(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    first_name: str,
    last_name: str | None = None,
    phone: str | None = None,
    license_number: str | None = None,
    user_id: int | None = None,
) -> Driver:
    """Insert a new driver record."""
    driver = Driver(
        user_id=user_id,
        school_id=school_id,
        branch_id=branch_id,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        license_number=license_number,
    )
    db.add(driver)
    await db.flush()
    await db.refresh(driver)
    return driver


async def update_driver_by_driver_id(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
    **kwargs,
) -> Driver:
    """Update driver fields. Uses RETURNING — single round-trip."""
    values = dict(kwargs)
    values["updated_at"] = func.now()

    result = await db.execute(
        update(Driver)
        .where(
            Driver.driver_id == driver_id,
            Driver.school_id == school_id,
            Driver.branch_id == branch_id,
        )
        .values(**values)
        .returning(Driver)
    )
    await db.flush()
    driver = result.scalar_one_or_none()
    if not driver:
        raise DriverNotFoundError(identifier=driver_id)
    return driver


async def deactivate_driver_by_driver_id(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
) -> Driver:
    """Soft-delete a driver. Uses RETURNING — single round-trip."""
    result = await db.execute(
        update(Driver)
        .where(
            Driver.driver_id == driver_id,
            Driver.school_id == school_id,
            Driver.branch_id == branch_id,
        )
        .values(is_active=False, updated_at=func.now())
        .returning(Driver)
    )
    await db.flush()
    driver = result.scalar_one_or_none()
    if not driver:
        raise DriverNotFoundError(identifier=driver_id)
    return driver


# =============================================================================
# Bus Queries
# =============================================================================

async def get_bus_by_bus_id(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
) -> Bus:
    """Fetch a bus scoped to branch. Raises BusNotFoundError if not found."""
    result = await db.execute(
        select(Bus).where(
            Bus.bus_id == bus_id,
            Bus.school_id == school_id,
            Bus.branch_id == branch_id,
        )
    )
    bus = result.scalar_one_or_none()
    if not bus:
        raise BusNotFoundError(identifier=bus_id)
    return bus


async def get_bus_by_bus_id_or_none(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
) -> Bus | None:
    """Fetch a bus scoped to branch. Returns None if not found."""
    result = await db.execute(
        select(Bus).where(
            Bus.bus_id == bus_id,
            Bus.school_id == school_id,
            Bus.branch_id == branch_id,
        )
    )
    return result.scalar_one_or_none()


async def get_all_buses_by_branch(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Bus], int]:
    """Fetch all buses for a branch with pagination."""
    query = select(Bus).where(
        Bus.school_id == school_id,
        Bus.branch_id == branch_id,
    )
    if active_only:
        query = query.where(Bus.is_active == True)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(Bus.bus_number).limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0


async def get_buses_by_branch_ids(
    db: AsyncSession,
    school_id: int,
    branch_ids: list[int],
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Bus], int]:
    """Fetch buses filtered to a list of branch_ids within a school."""
    query = select(Bus).where(
        Bus.school_id == school_id,
        Bus.branch_id.in_(branch_ids),
    )
    if active_only:
        query = query.where(Bus.is_active == True)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(Bus.bus_number).limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0


async def create_bus(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    bus_number: str,
    capacity: int,
) -> Bus:
    """Insert a new bus record."""
    bus = Bus(
        school_id=school_id,
        branch_id=branch_id,
        bus_number=bus_number,
        capacity=capacity,
    )
    db.add(bus)
    await db.flush()
    await db.refresh(bus)
    return bus


async def update_bus_by_bus_id(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
    **kwargs,
) -> Bus:
    """Update bus fields. Uses RETURNING — single round-trip."""
    values = dict(kwargs)
    values["updated_at"] = func.now()

    result = await db.execute(
        update(Bus)
        .where(
            Bus.bus_id == bus_id,
            Bus.school_id == school_id,
            Bus.branch_id == branch_id,
        )
        .values(**values)
        .returning(Bus)
    )
    await db.flush()
    bus = result.scalar_one_or_none()
    if not bus:
        raise BusNotFoundError(identifier=bus_id)
    return bus


async def deactivate_bus_by_bus_id(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
) -> Bus:
    """Soft-delete a bus. Uses RETURNING — single round-trip."""
    result = await db.execute(
        update(Bus)
        .where(
            Bus.bus_id == bus_id,
            Bus.school_id == school_id,
            Bus.branch_id == branch_id,
        )
        .values(is_active=False, updated_at=func.now())
        .returning(Bus)
    )
    await db.flush()
    bus = result.scalar_one_or_none()
    if not bus:
        raise BusNotFoundError(identifier=bus_id)
    return bus


# =============================================================================
# GPS Device Queries
# =============================================================================

async def get_device_by_device_id(
    db: AsyncSession,
    device_id: int,
    school_id: int,
    branch_id: int,
) -> GPSDevice:
    """Fetch a GPS device scoped to branch. Raises DeviceNotFoundError if not found."""
    result = await db.execute(
        select(GPSDevice).where(
            GPSDevice.device_id == device_id,
            GPSDevice.school_id == school_id,
            GPSDevice.branch_id == branch_id,
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise DeviceNotFoundError(identifier=device_id)
    return device


async def get_device_by_device_id_or_none(
    db: AsyncSession,
    device_id: int,
    school_id: int,
    branch_id: int,
) -> GPSDevice | None:
    """Fetch a GPS device scoped to branch. Returns None if not found."""
    result = await db.execute(
        select(GPSDevice).where(
            GPSDevice.device_id == device_id,
            GPSDevice.school_id == school_id,
            GPSDevice.branch_id == branch_id,
        )
    )
    return result.scalar_one_or_none()


async def get_device_by_device_imei_or_none(
    db: AsyncSession,
    device_imei: str,
) -> GPSDevice | None:
    """Fetch a GPS device by IMEI globally. Returns None if not found."""
    result = await db.execute(
        select(GPSDevice).where(GPSDevice.device_imei == device_imei)
    )
    return result.scalar_one_or_none()


async def get_all_devices_by_branch(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[GPSDevice], int]:
    """Fetch all GPS devices for a branch with pagination."""
    query = select(GPSDevice).where(
        GPSDevice.school_id == school_id,
        GPSDevice.branch_id == branch_id,
    )
    if active_only:
        query = query.where(GPSDevice.is_active == True)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(GPSDevice.device_imei).limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0


async def get_devices_by_branch_ids(
    db: AsyncSession,
    school_id: int,
    branch_ids: list[int],
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[GPSDevice], int]:
    """Fetch devices filtered to a list of branch_ids within a school."""
    query = select(GPSDevice).where(
        GPSDevice.school_id == school_id,
        GPSDevice.branch_id.in_(branch_ids),
    )
    if active_only:
        query = query.where(GPSDevice.is_active == True)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(GPSDevice.device_imei).limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0


async def create_device(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    device_imei: str,
) -> GPSDevice:
    """Insert a new GPS device record."""
    device = GPSDevice(
        school_id=school_id,
        branch_id=branch_id,
        device_imei=device_imei,
    )
    db.add(device)
    await db.flush()
    await db.refresh(device)
    return device


async def update_device_by_device_id(
    db: AsyncSession,
    device_id: int,
    school_id: int,
    branch_id: int,
    **kwargs,
) -> GPSDevice:
    """Update GPS device fields. Uses RETURNING — single round-trip."""
    values = dict(kwargs)
    values["updated_at"] = func.now()

    result = await db.execute(
        update(GPSDevice)
        .where(
            GPSDevice.device_id == device_id,
            GPSDevice.school_id == school_id,
            GPSDevice.branch_id == branch_id,
        )
        .values(**values)
        .returning(GPSDevice)
    )
    await db.flush()
    device = result.scalar_one_or_none()
    if not device:
        raise DeviceNotFoundError(identifier=device_id)
    return device


async def deactivate_device_by_device_id(
    db: AsyncSession,
    device_id: int,
    school_id: int,
    branch_id: int,
) -> GPSDevice:
    """Soft-delete a GPS device. Uses RETURNING — single round-trip."""
    result = await db.execute(
        update(GPSDevice)
        .where(
            GPSDevice.device_id == device_id,
            GPSDevice.school_id == school_id,
            GPSDevice.branch_id == branch_id,
        )
        .values(is_active=False, updated_at=func.now())
        .returning(GPSDevice)
    )
    await db.flush()
    device = result.scalar_one_or_none()
    if not device:
        raise DeviceNotFoundError(identifier=device_id)
    return device


# =============================================================================
# Bus Device Assignment Queries
# =============================================================================

async def get_active_assignment_by_bus_id(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
) -> BusDeviceAssignment | None:
    """
    Fetch the currently active device assignment for a bus.
    Returns None if no active assignment exists.
    Active = unassigned_at IS NULL.
    """
    result = await db.execute(
        select(BusDeviceAssignment).where(
            BusDeviceAssignment.bus_id == bus_id,
            BusDeviceAssignment.school_id == school_id,
            BusDeviceAssignment.branch_id == branch_id,
            BusDeviceAssignment.unassigned_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def get_active_assignment_by_device_id(
    db: AsyncSession,
    device_id: int,
    school_id: int,
    branch_id: int,
) -> BusDeviceAssignment | None:
    """
    Fetch the currently active bus assignment for a device.
    Returns None if no active assignment exists.
    """
    result = await db.execute(
        select(BusDeviceAssignment).where(
            BusDeviceAssignment.device_id == device_id,
            BusDeviceAssignment.school_id == school_id,
            BusDeviceAssignment.branch_id == branch_id,
            BusDeviceAssignment.unassigned_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def get_all_assignments_by_bus_id(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
) -> list[BusDeviceAssignment]:
    """Fetch full assignment history for a bus (active + historical)."""
    result = await db.execute(
        select(BusDeviceAssignment)
        .where(
            BusDeviceAssignment.bus_id == bus_id,
            BusDeviceAssignment.school_id == school_id,
            BusDeviceAssignment.branch_id == branch_id,
        )
        .order_by(BusDeviceAssignment.assigned_at.desc())
    )
    return list(result.scalars().all())


async def create_bus_device_assignment(
    db: AsyncSession,
    bus_id: int,
    device_id: int,
    school_id: int,
    branch_id: int,
) -> BusDeviceAssignment:
    """
    Create a new active assignment between a bus and a GPS device.
    Caller must verify no active assignment exists for bus or device
    before calling this — DB partial unique index is the final guard.
    """
    assignment = BusDeviceAssignment(
        bus_id=bus_id,
        device_id=device_id,
        school_id=school_id,
        branch_id=branch_id,
    )
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    return assignment


async def close_assignment_by_bus_device_id(
    db: AsyncSession,
    bus_device_id: int,
) -> BusDeviceAssignment:
    """
    Close an active assignment by setting unassigned_at = now().
    Uses RETURNING — single round-trip.
    """
    result = await db.execute(
        update(BusDeviceAssignment)
        .where(BusDeviceAssignment.bus_device_id == bus_device_id)
        .values(unassigned_at=utcnow())
        .returning(BusDeviceAssignment)
    )
    await db.flush()
    return result.scalar_one()