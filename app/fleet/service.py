from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.fleet import repository as fleet_repo
from app.schools import repository as school_repo
from app.fleet.schemas import BusCreate, BusResponse, BusUpdate, PaginatedBusResponse
from app.core.config import settings
from app.core.exceptions import BusNotFoundError, DuplicateEntryError, ForbiddenError
from app.core.schemas import paginate, pagination_params
from app.api.v1.dependencies import CurrentUser


async def create_bus(
    db: AsyncSession,
    school_id: int,
    payload: BusCreate,
    current_user: CurrentUser,
) -> BusResponse:
    """
    Create a new bus scoped to the given school and the branch in the payload.

    Access rules:
      SUPER_ADMIN   — any school, any branch.
      SCHOOL_ADMIN  — only their own school, any branch within it.
      BRANCH_ADMIN  — only their own school and their own branch.

    Two-step branch validation:
      1. has_branch_access — role-level check.
      2. get_branch_by_branch_id — DB ownership check (branch must belong to school).
    """
    if not current_user.has_branch_access(school_id, payload.branch_id):
        raise ForbiddenError()

    await school_repo.get_branch_by_branch_id(db, payload.branch_id, school_id)

    try:
        bus = await fleet_repo.create_bus(
            db=db,
            school_id=school_id,
            branch_id=payload.branch_id,
            bus_number=payload.bus_number,
            capacity=payload.capacity,
        )
    except IntegrityError:
        raise DuplicateEntryError(field="bus_number", value=payload.bus_number)
    return BusResponse.model_validate(bus)


async def get_bus(
    db: AsyncSession,
    bus_id: int,
    school_id: int | None,
    current_user: CurrentUser,
) -> BusResponse:
    """
    Fetch a single bus by id.
    school_id = None for SUPER_ADMIN — repo skips the school filter.
    Scope violations return 404 — never reveal existence to another tenant.
    """
    bus = await fleet_repo.get_bus_by_bus_id_with_relations(db, bus_id, school_id)
    if not current_user.has_school_access(school_id):
        raise BusNotFoundError(identifier=bus_id)
    if not current_user.has_branch_access(school_id, bus.branch_id):
        raise BusNotFoundError(identifier=bus_id)
    return BusResponse.model_validate(bus)


async def get_all_buses(
    db: AsyncSession,
    school_id: int | None,
    branch_id: int | None,
    accessible_branch_ids: list[int] | None,
    page: int,
    page_size: int,
    active_only: bool = True,
    search: str | None = None,
) -> PaginatedBusResponse:
    """
    Return a paginated list of buses.

    school_id = None for SUPER_ADMIN — no school filter applied.
    search is passed to the repo for server-side ILIKE filtering on bus_number.
    """
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)
    buses, total = await fleet_repo.get_all_buses_by_branch(
        db, school_id, branch_id, accessible_branch_ids,
        limit, offset, active_only, search,
    )
    return paginate(
        items=[BusResponse.model_validate(b) for b in buses],
        total=total,
        page=page,
        page_size=page_size,
    )


async def update_bus(
    db: AsyncSession,
    bus_id: int,
    school_id: int | None,
    payload: BusUpdate,
    current_user: CurrentUser,
) -> BusResponse:
    """
    Partial update on a bus.
    Fetches first (no relations — only need branch_id for access check).
    If branch_id is being changed, applies the same two-step validation as create_bus.
    """
    bus = await fleet_repo.get_bus_by_bus_id(db, bus_id, school_id)
    if not current_user.has_school_access(school_id):
        raise ForbiddenError()
    if not current_user.has_branch_access(school_id, bus.branch_id):
        raise ForbiddenError()

    update_data = payload.model_dump(exclude_unset=True)

    if "branch_id" in update_data:
        new_branch_id = update_data["branch_id"]
        if not current_user.has_branch_access(bus.school_id, new_branch_id):
            raise ForbiddenError()
        await school_repo.get_branch_by_branch_id(db, new_branch_id, bus.school_id)

    try:
        updated_bus = await fleet_repo.update_bus_by_bus_id(
            db, bus_id, school_id, **update_data,
        )
    except IntegrityError:
        raise DuplicateEntryError(field="bus_number", value=payload.bus_number or "")
    return BusResponse.model_validate(updated_bus)


async def deactivate_bus(
    db: AsyncSession,
    bus_id: int,
    school_id: int | None,
    current_user: CurrentUser,
) -> BusResponse:
    """
    Soft-delete a bus (is_active=False).
    Fetches first to resolve branch_id for access check.
    """
    bus = await fleet_repo.get_bus_by_bus_id(db, bus_id, school_id)
    if not current_user.has_school_access(school_id):
        raise ForbiddenError()
    if not current_user.has_branch_access(school_id, bus.branch_id):
        raise ForbiddenError()
    deactivated = await fleet_repo.deactivate_bus_by_bus_id(db, bus_id, school_id)
    print(deactivated)
    return BusResponse.model_validate(deactivated)