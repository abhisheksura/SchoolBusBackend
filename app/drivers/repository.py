from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.drivers.models import Driver
from app.core.exceptions import DriverNotFoundError


async def get_driver_by_driver_id(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
) -> Driver:
    result = await db.execute(
        select(Driver)
        .where(
            Driver.driver_id == driver_id,
            Driver.school_id == school_id,
            Driver.branch_id == branch_id
        )
    )
    driver = result.scalar_one_or_none()
    if not driver:
        raise DriverNotFoundError(identifier=driver_id)
    return driver


async def get_all_drivers(
    db: AsyncSession,
    school_id: int | None,
    branch_id: int | None,
    limit: int,
    offset: int,
    active_only: bool = False,
) -> tuple[list[Driver], int]:

    filters = []
    if school_id is not None:
        filters.append(Driver.school_id == school_id)
    if branch_id is not None:
        filters.append(Driver.branch_id == branch_id)
    if active_only:
        filters.append(Driver.is_active == True)

    # 2. Optimized direct Count (No subqueries, no string joins evaluated)
    total = await db.scalar(
        select(func.count(Driver.driver_id)).where(and_(*filters))
    ) or 0

    if total == 0:
        return [], 0

    # 3. Clean query fetching ONLY what this module owns
    query = select(Driver).where(and_(*filters))

    result = await db.execute(
        query.order_by(Driver.is_active.desc(), Driver.driver_id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total

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
    return await get_driver_by_driver_id(
        db=db,
        driver_id=driver.driver_id,
        school_id=school_id,
        branch_id=branch_id,
    )

async def update_driver_by_driver_id(
    db: AsyncSession,
    driver_id: int,
    **kwargs,
) -> Driver:
    values = dict(kwargs)
    values["updated_at"] = func.now()

    result = await db.execute(
        update(Driver)
        .where(
            Driver.driver_id == driver_id,
        )
        .values(**values)
    )

    await db.flush()

    if result.rowcount == 0:
        raise DriverNotFoundError(identifier=driver_id)

    return await get_driver_by_driver_id(
        db=db,
        driver_id=driver_id,
    )


async def deactivate_driver_by_driver_id(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
) -> Driver:
    result = await db.execute(
        update(Driver)
        .where(
            Driver.driver_id == driver_id,
            Driver.school_id == school_id,
            Driver.branch_id == branch_id,
        )
        .values(
            is_active=False,
            updated_at=func.now(),
        )
    )

    await db.flush()

    if result.rowcount == 0:
        raise DriverNotFoundError(identifier=driver_id)

    return await get_driver_by_driver_id(
        db=db,
        driver_id=driver_id,
        school_id=school_id,
        branch_id=branch_id,
    )


async def reactivate_driver_by_driver_id(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
) -> Driver:
    result = await db.execute(
        update(Driver)
        .where(
            Driver.driver_id == driver_id,
            Driver.school_id == school_id,
            Driver.branch_id == branch_id,
        )
        .values(
            is_active=True,
            updated_at=func.now(),
        )
    )

    await db.flush()

    if result.rowcount == 0:
        raise DriverNotFoundError(identifier=driver_id)

    return await get_driver_by_driver_id(
        db=db,
        driver_id=driver_id,
        school_id=school_id,
        branch_id=branch_id,
    )


async def get_driver_by_user_id_or_none(
    db: AsyncSession,
    user_id: int,
) -> Driver | None:
    """
    Fetch a driver by their linked user account.
    Used during login to embed driver_id in the JWT.
    Returns None if no driver record is linked to this user.
    """
    result = await db.execute(
        select(Driver).where(Driver.user_id == user_id, Driver.is_active == True)
    )
    return result.scalar_one_or_none()