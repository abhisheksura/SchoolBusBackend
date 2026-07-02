from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.buses import repository as bus_repo
from app.schools import repository as school_repo
from app.buses.schemas import BusCreate, BusResponse, BusUpdate, PaginatedBusResponse
from app.core.config import settings
from app.core.exceptions import BusNotFoundError, DuplicateEntryError, ForbiddenError
from app.core.schemas import paginate, pagination_params
from app.api.v1.dependencies import CurrentUser
from app.core.scope import validate_scope_access
from app.core.utils import get_tenant_names, to_tenant_response


async def get_all_buses(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    page: int,
    page_size: int,
    active_only: bool = False,
) -> PaginatedBusResponse:
    """Fetch paginated routes for a branch, filtered by caller's scope."""
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)

    buses, total = await bus_repo.get_all_buses(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        limit=limit,
        offset=offset,
        active_only=active_only,
    )
    # 3. Short-circuit: skip cache parsing entirely if page is empty
    if not buses:
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
            bus,
            BusResponse,
            school_name=school_name,
            branch_name=branch_name
        )
        for bus in buses
    ]

    # 6. Return standard paginated payload structure
    return paginate(
        items=mapped_items,
        total=total,
        page=page,
        page_size=page_size,
    )

async def create_bus(
    db: AsyncSession,
    payload: BusCreate,
) -> BusResponse:
    """
    Create a new bus.
    Role check (BRANCH_ADMIN+) enforced at router.
    """
    try:
        bus = await bus_repo.create_bus(
            db=db,
            school_id=payload.school_id,
            branch_id=payload.branch_id,
            bus_number=payload.bus_number,
            capacity=payload.capacity,
        )
    except IntegrityError:
        raise DuplicateEntryError(field="bus_number", value=payload.bus_number)
    return BusResponse.model_validate(bus)


async def update_bus(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
    payload: BusUpdate,
) -> BusResponse:
    """Update a route. Role check enforced at router."""
    try:
        bus = await bus_repo.update_bus_by_bus_id(
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
    bus = await bus_repo.deactivate_bus_by_bus_id(
        db, bus_id, school_id, branch_id
    )
    return BusResponse.model_validate(bus)


async def reactivate_bus(
    db: AsyncSession,
    bus_id: int,
    school_id: int,
    branch_id: int,
) -> BusResponse:
    bus = await bus_repo.reactivate_bus_by_bus_id(db, bus_id, school_id, branch_id)
    return BusResponse.model_validate(bus)
