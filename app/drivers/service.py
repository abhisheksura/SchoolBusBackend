from sqlalchemy.ext.asyncio import AsyncSession

from app.drivers import repository as driver_repo
from app.drivers.schemas import (
    DriverCreate,
    DriverResponse,
    DriverUpdate,
    PaginatedDriverResponse,
)
from app.core.config import settings
from app.core.exceptions import DriverNotFoundError
from app.core.schemas import paginate, pagination_params


async def create_driver(db: AsyncSession, payload: DriverCreate) -> DriverResponse:
    """Role check (BRANCH_ADMIN+) enforced at router."""
    driver = await driver_repo.create_driver(
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
    """Scope check BEFORE DB hit."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise DriverNotFoundError(identifier=driver_id)
    driver = await driver_repo.get_driver_by_driver_id(db, driver_id, school_id, branch_id)
    return DriverResponse.model_validate(driver)


async def get_all_drivers(
    db: AsyncSession,
    school_id: int | None,
    # branch_id: int,
    page: int,
    page_size: int,
    accessible_branch_ids: list[int] | None,
    active_only: bool = True,
) -> PaginatedDriverResponse:
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)
    drivers, total = await driver_repo.get_all_drivers(
        db=db,
        school_id=school_id,
        branch_ids=accessible_branch_ids,
        limit=limit,
        offset=offset,
        active_only=active_only,
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
    driver = await driver_repo.update_driver_by_driver_id(
        db, driver_id, school_id, branch_id,
        **payload.model_dump(exclude_unset=True),
    )
    return DriverResponse.model_validate(driver)


async def deactivate_driver(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
) -> DriverResponse:
    driver = await driver_repo.deactivate_driver_by_driver_id(db, driver_id, school_id, branch_id)
    return DriverResponse.model_validate(driver)