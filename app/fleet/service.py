from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.fleet import repository as fleet_repo
from app.fleet.schemas import BusCreate, BusResponse, BusUpdate, PaginatedBusResponse
from app.core.config import settings
from app.core.exceptions import BusNotFoundError, DuplicateEntryError
from app.core.schemas import paginate, pagination_params


async def create_bus(db: AsyncSession, payload: BusCreate) -> BusResponse:
    try:
        bus = await fleet_repo.create_bus(
            db=db, school_id=payload.school_id, branch_id=payload.branch_id,
            bus_number=payload.bus_number, capacity=payload.capacity,
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
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)
    if accessible_branch_ids is None:
        buses, total = await fleet_repo.get_all_buses_by_branch(db, school_id, branch_id, limit, offset, active_only)
    else:
        buses, total = await fleet_repo.get_buses_by_branch_ids(db, school_id, accessible_branch_ids, limit, offset, active_only)
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
    try:
        bus = await fleet_repo.update_bus_by_bus_id(
            db, bus_id, school_id, branch_id,
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
    bus = await fleet_repo.deactivate_bus_by_bus_id(db, bus_id, school_id, branch_id)
    return BusResponse.model_validate(bus)