from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.drivers.models import Driver
from app.core.exceptions import DriverNotFoundError


async def get_driver_by_driver_id(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
) -> Driver:
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


async def get_all_drivers_by_branch(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Driver], int]:
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
    values = dict(kwargs)
    values["updated_at"] = func.now()
    result = await db.execute(
        update(Driver)
        .where(Driver.driver_id == driver_id, Driver.school_id == school_id, Driver.branch_id == branch_id)
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
    result = await db.execute(
        update(Driver)
        .where(Driver.driver_id == driver_id, Driver.school_id == school_id, Driver.branch_id == branch_id)
        .values(is_active=False, updated_at=func.now())
        .returning(Driver)
    )
    await db.flush()
    driver = result.scalar_one_or_none()
    if not driver:
        raise DriverNotFoundError(identifier=driver_id)
    return driver

 
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