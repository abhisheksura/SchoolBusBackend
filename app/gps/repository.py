from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.gps.models import BusDeviceAssignment, GPSDevice
from app.core.exceptions import BusAlreadyHasDeviceError, DeviceAlreadyAssignedError, DeviceNotFoundError
from app.core.utils import utcnow


# =============================================================================
# GPSDevice Queries
# =============================================================================

async def get_device_by_device_id(
    db: AsyncSession,
    device_id: int,
    school_id: int,
    branch_id: int,
) -> GPSDevice:
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


async def get_device_by_imei_or_none(
    db: AsyncSession,
    device_imei: str,
) -> GPSDevice | None:
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
    device = GPSDevice(school_id=school_id, branch_id=branch_id, device_imei=device_imei)
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
    values = dict(kwargs)
    values["updated_at"] = func.now()
    result = await db.execute(
        update(GPSDevice)
        .where(GPSDevice.device_id == device_id, GPSDevice.school_id == school_id, GPSDevice.branch_id == branch_id)
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
    result = await db.execute(
        update(GPSDevice)
        .where(GPSDevice.device_id == device_id, GPSDevice.school_id == school_id, GPSDevice.branch_id == branch_id)
        .values(is_active=False, updated_at=func.now())
        .returning(GPSDevice)
    )
    await db.flush()
    device = result.scalar_one_or_none()
    if not device:
        raise DeviceNotFoundError(identifier=device_id)
    return device


# =============================================================================
# BusDeviceAssignment Queries
# =============================================================================

async def get_active_assignment_by_bus_id(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
) -> BusDeviceAssignment | None:
    """Fetch the currently active device assignment for a bus. None if unassigned."""
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
    """Fetch the currently active bus assignment for a device. None if unassigned."""
    result = await db.execute(
        select(BusDeviceAssignment).where(
            BusDeviceAssignment.device_id == device_id,
            BusDeviceAssignment.school_id == school_id,
            BusDeviceAssignment.branch_id == branch_id,
            BusDeviceAssignment.unassigned_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def create_bus_device_assignment(
    db: AsyncSession,
    bus_id: int,
    device_id: int,
    school_id: int,
    branch_id: int,
) -> BusDeviceAssignment:
    """Create a new active assignment. Caller must verify no conflicts exist."""
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


async def close_assignment_by_id(
    db: AsyncSession,
    bus_device_id: int,
) -> BusDeviceAssignment:
    """Close an active assignment by setting unassigned_at = now(). Uses RETURNING."""
    result = await db.execute(
        update(BusDeviceAssignment)
        .where(BusDeviceAssignment.bus_device_id == bus_device_id)
        .values(unassigned_at=utcnow())
        .returning(BusDeviceAssignment)
    )
    await db.flush()
    return result.scalar_one()