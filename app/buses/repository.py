from sqlalchemy import select, update, func, delete, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import CursorResult
from app.buses.models import Bus
from app.core.enums import TripType
from app.core.exceptions import (
    BusNotFoundError,
    DuplicateEntryError,
    ConflictError,
)
from typing import cast


async def get_all_buses(
    db: AsyncSession,
    school_id: int | None,
    branch_id: int | None,
    limit: int,
    offset: int,
    active_only: bool = False,
) -> tuple[list[Bus], int]:

    # 1. Build common filter conditions
    filters = []
    if school_id is not None:
        filters.append(Bus.school_id == school_id)
    if branch_id is not None:
        filters.append(Bus.branch_id == branch_id)
    if active_only:
        filters.append(Bus.is_active == True)

    # 2. Optimized direct Count (No subqueries, no string joins evaluated)
    total = await db.scalar(
        select(func.count(Bus.bus_id)).where(and_(*filters))
    ) or 0

    if total == 0:
        return [], 0

    # 3. Clean query fetching ONLY what this module owns
    query = select(Bus).where(and_(*filters))

    result = await db.execute(
        query.order_by(Bus.is_active.desc(), Bus.bus_number)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def get_bus_by_bus_id(
    db: AsyncSession,
    bus_id: int,
    school_id: int | None,
    branch_id: int | None,
) -> Bus:
    """Fetch a bus scoped to school, branch. Raises RouteNotFoundError if not found."""
    # 1. Start with the base query and preload relationships
    query = select(Bus).options(
        selectinload(Bus.school),
        selectinload(Bus.branch),
    )
    # 2. Base condition is always the primary route identifier
    query = query.where(Bus.bus_id == bus_id)

    # 3. Apply optional multi-tenant filters dynamically to prevent 'IS NULL' errors
    if school_id is not None:
        query = query.where(Bus.school_id == school_id)

    if branch_id is not None:
        query = query.where(Bus.branch_id == branch_id)

    # 4. Execute the query
    result = await db.execute(query)
    bus = result.scalar_one_or_none()

    # 5. Handle missing record safely
    if not bus:
        raise BusNotFoundError(identifier=bus_id)
    return bus

async def create_bus(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    bus_number: str,
    capacity: int
) -> Bus:
    """Insert a new route record."""
    bus = Bus(
        school_id=school_id,
        branch_id=branch_id,
        bus_number=bus_number,
        capacity=capacity
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
    """Update bus fields."""
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
    route = result.scalar_one_or_none()
    if not route:
        raise BusNotFoundError(identifier=bus_id)
    return route


async def deactivate_bus_by_bus_id(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
) -> Bus:
    """Soft-delete a Bus. Uses RETURNING — single round-trip."""
    result = cast(
        CursorResult,
        await db.execute(
            update(Bus)
            .where(
                Bus.bus_id == bus_id,
                Bus.school_id == school_id,
                Bus.branch_id == branch_id,
            )
            .values(is_active=False, updated_at=func.now())
        ),
    )
    await db.flush()

    if result.rowcount == 0:
        raise BusNotFoundError(identifier=bus_id)

    return await get_bus_by_bus_id(
        db=db,
        bus_id=bus_id,
        school_id=school_id,
        branch_id=branch_id,
    )


async def reactivate_bus_by_bus_id(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
) -> Bus:
    result = cast(
        CursorResult, 
        await db.execute(
            update(Bus)
            .where(
                Bus.bus_id == bus_id,
                Bus.school_id == school_id,
                Bus.branch_id == branch_id,
            )
            .values(
                is_active=True,
                updated_at=func.now(),
            )
        ),
    )

    await db.flush()

    if result.rowcount == 0:
        raise BusNotFoundError(identifier=bus_id)

    return await get_bus_by_bus_id(
        db=db,
        bus_id=bus_id,
        school_id=school_id,
        branch_id=branch_id,
    )