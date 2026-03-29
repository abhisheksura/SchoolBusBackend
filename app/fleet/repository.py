from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.fleet.models import Bus
from app.core.exceptions import BusNotFoundError


async def get_bus_by_bus_id(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
) -> Bus:
    result = await db.execute(
        select(Bus).where(Bus.bus_id == bus_id, Bus.school_id == school_id, Bus.branch_id == branch_id)
    )
    bus = result.scalar_one_or_none()
    if not bus:
        raise BusNotFoundError(identifier=bus_id)
    return bus


async def get_all_buses_by_branch(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Bus], int]:
    query = select(Bus).where(Bus.school_id == school_id, Bus.branch_id == branch_id)
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
    query = select(Bus).where(Bus.school_id == school_id, Bus.branch_id.in_(branch_ids))
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
    bus = Bus(school_id=school_id, branch_id=branch_id, bus_number=bus_number, capacity=capacity)
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
    values = dict(kwargs)
    values["updated_at"] = func.now()
    result = await db.execute(
        update(Bus)
        .where(Bus.bus_id == bus_id, Bus.school_id == school_id, Bus.branch_id == branch_id)
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
    result = await db.execute(
        update(Bus)
        .where(Bus.bus_id == bus_id, Bus.school_id == school_id, Bus.branch_id == branch_id)
        .values(is_active=False, updated_at=func.now())
        .returning(Bus)
    )
    await db.flush()
    bus = result.scalar_one_or_none()
    if not bus:
        raise BusNotFoundError(identifier=bus_id)
    return bus