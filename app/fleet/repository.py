# app/fleet/repository.py
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.fleet.models import Bus
from app.core.exceptions import BusNotFoundError


# -----------------------------------------------------------------------------
# Internal helper
# Applies selectinload for school and branch — required for any query whose
# result is serialized into BusResponse (needs school_name, branch_name).
# Not applied on internal-only fetches (access checks before writes).
# -----------------------------------------------------------------------------
def _with_relations(query):
    """Eagerly load school and branch onto a Bus query for BusResponse serialization."""
    return query.options(
        selectinload(Bus.school),
        selectinload(Bus.branch),
    )


async def get_bus_by_bus_id(
    db: AsyncSession,
    bus_id: int,
    school_id: int | None,
) -> Bus:
    """
    Fetch a single bus by primary key — internal use only (access checks, writes).
    Does not load school/branch relations — not needed before service-layer checks.
    school_id = None means SUPER_ADMIN — no school filter applied.
    Raises BusNotFoundError if not found.
    """
    query = select(Bus).where(Bus.bus_id == bus_id)
    if school_id is not None:
        query = query.where(Bus.school_id == school_id)
    result = await db.execute(query)
    bus = result.scalar_one_or_none()
    if not bus:
        raise BusNotFoundError(identifier=bus_id)
    return bus


async def get_bus_by_bus_id_with_relations(
    db: AsyncSession,
    bus_id: int,
    school_id: int | None,
) -> Bus:
    """
    Fetch a single bus with school and branch loaded — use when the result
    is serialized into BusResponse (get_bus endpoint, post-update response).
    Raises BusNotFoundError if not found.
    """
    query = _with_relations(select(Bus).where(Bus.bus_id == bus_id))
    if school_id is not None:
        query = query.where(Bus.school_id == school_id)
    result = await db.execute(query)
    bus = result.scalar_one_or_none()
    if not bus:
        raise BusNotFoundError(identifier=bus_id)
    return bus


async def get_bus_detail(
    db: AsyncSession,
    bus_id: int,
    school_id: int | None,
) -> Bus | None:

    stmt = (
        select(Bus)
        .options(
            selectinload(Bus.school),
            selectinload(Bus.branch),
        )
        .execution_options(populate_existing=True)
        .where(
            Bus.bus_id == bus_id,
            Bus.school_id == school_id,
        )
    )

    result = await db.execute(stmt)

    return result.scalar_one_or_none()


async def get_all_buses_by_branch(
    db: AsyncSession,
    school_id: int | None,
    branch_id: int | None,
    accessible_branch_ids: list[int] | None,
    limit: int,
    offset: int,
    active_only: bool = True,
    search: str | None = None,
) -> tuple[list[Bus], int]:
    """
    Return a paginated list of buses with school and branch loaded for BusResponse.

    school_id semantics:
      None      — SUPER_ADMIN: no school filter, sees all buses across all schools.
      int       — SCHOOL_ADMIN / BRANCH_ADMIN / others: restrict to this school.

    accessible_branch_ids semantics (resolved by router from current_user):
      None      — SUPER_ADMIN or SCHOOL_ADMIN: no branch restriction.
      list[int] — BRANCH_ADMIN / DRIVER / etc: restrict to this explicit whitelist.

    branch_id (optional URL query param):
      Pre-validated by the router — branch_id without school_id is rejected at 400
      before reaching here, so this function always receives a valid combination.

    search:
      Case-insensitive partial match on bus_number — applied server-side so
      results span all pages, not just the current one.
    """
    # Build base query without relations — reused for COUNT (no joins needed)
    # and then extended with _with_relations for the actual data fetch.
    base_query = select(Bus)

    # 🔐 School scope — None means SUPER_ADMIN, no restriction
    if school_id is not None:
        base_query = base_query.where(Bus.school_id == school_id)

    # 🔐 Branch scope — None means SUPER_ADMIN or SCHOOL_ADMIN, no restriction
    if accessible_branch_ids is not None:
        base_query = base_query.where(Bus.branch_id.in_(accessible_branch_ids))
    elif branch_id is not None:
        base_query = base_query.where(Bus.branch_id == branch_id)

    if active_only:
        base_query = base_query.where(Bus.is_active == True)  # noqa: E712

    # 🔍 Search — ILIKE for case-insensitive partial match on bus_number
    if search:
        base_query = base_query.where(Bus.bus_number.ilike(f"%{search}%"))

    # COUNT on the base query — no joins, no selectinload overhead
    total = await db.scalar(select(func.count()).select_from(base_query.subquery()))

    # Apply relations + ordering/pagination only for the actual data fetch
    result_query = _with_relations(base_query).order_by(Bus.bus_number).limit(limit).offset(offset)
    result = await db.execute(result_query)
    return list(result.scalars().all()), total or 0


async def create_bus(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    bus_number: str,
    capacity: int,
) -> Bus:
    """
    Insert a new bus record and return it with school and branch loaded
    so the result can be immediately serialized into BusResponse.

    The newly created Bus instance is expunged before re-fetching — after
    flush it sits in the identity map without relations loaded, so
    get_bus_by_bus_id_with_relations would return that same cached object
    and selectinload would have nothing to attach to.
    """
    bus = Bus(school_id=school_id, branch_id=branch_id, bus_number=bus_number, capacity=capacity)
    db.add(bus)
    await db.flush()
    created_id = bus.bus_id
    db.expunge(bus)  # evict before re-fetch so selectinload runs on a fresh instance
    return await get_bus_by_bus_id_with_relations(db, created_id, school_id)


async def update_bus_by_bus_id(
    db: AsyncSession,
    bus_id: int,
    school_id: int | None,
    **kwargs,
) -> Bus:
    """
    Update bus fields by primary key, then re-fetch with relations for BusResponse.
    Returns Bus.bus_id from RETURNING to avoid stale identity map risk.
    Raises BusNotFoundError if the bus does not exist.

    The Core SQL UPDATE bypasses the ORM, so SQLAlchemy does not invalidate
    the cached Bus instance from the earlier get_bus_by_bus_id call. Without
    expunge, get_bus_by_bus_id_with_relations returns that stale object and
    selectinload skips it — school/branch stay None, breaking BusResponse.
    """
    query = update(Bus).where(Bus.bus_id == bus_id)
    if school_id is not None:
        query = query.where(Bus.school_id == school_id)
    result = await db.execute(
        query.values(**{**kwargs, "updated_at": func.now()}).returning(Bus.bus_id)
    )
    await db.flush()
    updated_id = result.scalar_one_or_none()
    if not updated_id:
        raise BusNotFoundError(identifier=bus_id)

    # Evict stale instance cached by the pre-mutation get_bus_by_bus_id call
    stale = db.identity_map.get((Bus, (updated_id,)))
    if stale is not None:
        db.expunge(stale)

    # After update, school_id on the bus may have changed — use None for SUPER_ADMIN
    # so the re-fetch isn't constrained to the old school_id
    return await get_bus_by_bus_id_with_relations(db, updated_id, None)


async def deactivate_bus_by_bus_id(
    db: AsyncSession,
    bus_id: int,
    school_id: int | None,
) -> Bus:
    """
    Soft-delete a bus by setting is_active=False, then re-fetch with relations.
    Raises BusNotFoundError if not found.

    Same stale identity map fix as update_bus_by_bus_id — the Core SQL UPDATE
    does not invalidate the cached instance from the pre-mutation fetch.
    """
    query = update(Bus).where(Bus.bus_id == bus_id)
    if school_id is not None:
        query = query.where(Bus.school_id == school_id)
    result = await db.execute(
        query.values(is_active=False, updated_at=func.now()).returning(Bus.bus_id)
    )
    await db.flush()
    updated_id = result.scalar_one_or_none()
    if not updated_id:
        raise BusNotFoundError(identifier=bus_id)

    # Evict stale instance cached by the pre-mutation get_bus_by_bus_id call
    stale = db.identity_map.get((Bus, (updated_id,)))
    if stale is not None:
        db.expunge(stale)

    return await get_bus_by_bus_id_with_relations(db, updated_id, None)