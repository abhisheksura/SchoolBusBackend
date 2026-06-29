from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import CurrentUser
from app.drivers import repository as driver_repo
from app.drivers.schemas import (
    DriverCreate,
    DriverResponse,
    DriverUpdate,
    PaginatedDriverResponse,
)
from app.core.config import settings
from app.core.enums import RoleName
from app.core.exceptions import DriverNotFoundError
from app.core.schemas import paginate, pagination_params
from app.core.utils import get_tenant_names, to_tenant_response


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
    school_id: int,
    branch_id: int,
    page: int,
    page_size: int,
    # accessible_branch_ids: list[int] | None,
    active_only: bool = False,
) -> PaginatedDriverResponse:
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)
    drivers, total = await driver_repo.get_all_drivers(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        limit=limit,
        offset=offset,
        active_only=active_only,
    )
    # 3. Short-circuit: skip cache parsing entirely if page is empty
    if not drivers:
        return paginate(
            items=[],
            total=total,
            page=page,
            page_size=page_size,
        )

    # 4. Fetch the tenant names *once* per request block (0ms response if cached)
    school_name, branch_name = await get_tenant_names(db, school_id, branch_id)

    # 5. Map rows efficiently into Pydantic passing string references
    mapped_items = [
        to_tenant_response(
            d,
            DriverResponse,
            school_name=school_name,
            branch_name=branch_name
        )
        for d in drivers
    ]
    # 6. Return standard paginated payload structure
    return paginate(
        items=mapped_items,
        total=total,
        page=page,
        page_size=page_size,
    )


async def update_driver(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
    payload: DriverUpdate,
    current_user: CurrentUser,
) -> DriverResponse:
    try:
        driver = await driver_repo.update_driver_by_driver_id(
            db=db,
            driver_id=driver_id,
            school_id=school_id,
            branch_id=branch_id,
            **payload.model_dump(exclude_unset=True),
        )
    except IntegrityError:
        raise DuplicateEntryError(field="Driver identity", value="duplicate name/license combination")
    return DriverResponse.model_validate(driver)


async def deactivate_driver(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
) -> DriverResponse:
    driver = await driver_repo.deactivate_driver_by_driver_id(db, driver_id, school_id, branch_id)
    return DriverResponse.model_validate(driver)


async def reactivate_driver(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
) -> DriverResponse:
    driver = await driver_repo.reactivate_driver_by_driver_id(db, driver_id, school_id, branch_id)
    return DriverResponse.model_validate(driver)