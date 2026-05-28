from sqlalchemy import select, update, func, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.routes.models import Route, RouteStop, Stop
from app.core.enums import TripType
from app.core.exceptions import (
    RouteNotFoundError,
    StopNotFoundError,
    DuplicateEntryError,
    ConflictError,
)


# =============================================================================
# Route Queries
# =============================================================================

async def get_route_by_route_id(
    db: AsyncSession,
    route_id: int,
    school_id: int,
    branch_id: int,
) -> Route:
    """Fetch a route scoped to branch. Raises RouteNotFoundError if not found."""
    result = await db.execute(
        select(Route).where(
            Route.route_id == route_id,
            Route.school_id == school_id,
            Route.branch_id == branch_id,
        )
    )
    route = result.scalar_one_or_none()
    if not route:
        raise RouteNotFoundError(identifier=route_id)
    return route

async def get_all_routes(
    db: AsyncSession,
    school_id: int | None,
    branch_ids: list[int] | None,
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Route], int]:

    query = select(Route).options(
        selectinload(Route.school),
        selectinload(Route.branch),
    )
    if school_id is not None:
        query = query.where(
            Route.school_id == school_id
        )

    if branch_ids is not None:
        query = query.where(
            Route.branch_id.in_(branch_ids)
        )

    if active_only:
        query = query.where(
            Route.is_active == True
        )

    total = await db.scalar(
        select(func.count()).select_from(
            query.subquery()
        )
    )

    result = await db.execute(
        query.order_by(Route.route_name)
        .limit(limit)
        .offset(offset)
    )

    return list(result.scalars().all()), total or 0

async def get_route_with_stops_by_route_id(
    db: AsyncSession,
    route_id: int,
    school_id: int,
    branch_id: int,
) -> Route:
    """
    Fetch a route with its route_stops eagerly loaded.
    Use with RouteDetailResponse — never use get_route_by_route_id()
    with RouteDetailResponse as route_stops is lazy="noload".
    """
    result = await db.execute(
        select(Route)
        .options(selectinload(Route.route_stops))
        .where(
            Route.route_id == route_id,
            Route.school_id == school_id,
            Route.branch_id == branch_id,
        )
    )
    route = result.scalar_one_or_none()
    if not route:
        raise RouteNotFoundError(identifier=route_id)
    return route


async def get_all_routes_by_branch(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Route], int]:
    """Fetch all routes for a branch with pagination."""
    query = select(Route).where(
        Route.school_id == school_id,
        Route.branch_id == branch_id,
    )
    if active_only:
        query = query.where(Route.is_active == True)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(Route.route_code).limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0


async def get_routes_by_branch_ids(
    db: AsyncSession,
    school_id: int,
    branch_ids: list[int],
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Route], int]:
    """Fetch routes filtered to a list of branch_ids within a school."""
    query = select(Route).where(
        Route.school_id == school_id,
        Route.branch_id.in_(branch_ids),
    )
    if active_only:
        query = query.where(Route.is_active == True)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(Route.route_code).limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0


async def create_route(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    route_code: str,
    route_name: str,
    description: str | None = None,
) -> Route:
    """Insert a new route record."""
    route = Route(
        school_id=school_id,
        branch_id=branch_id,
        route_code=route_code,
        route_name=route_name,
        description=description,
    )
    db.add(route)
    await db.flush()
    await db.refresh(route)
    return route


async def update_route_by_route_id(
    db: AsyncSession,
    route_id: int,
    school_id: int,
    branch_id: int,
    **kwargs,
) -> Route:
    """Update route fields. Uses RETURNING — single round-trip."""
    values = dict(kwargs)
    values["updated_at"] = func.now()

    result = await db.execute(
        update(Route)
        .where(
            Route.route_id == route_id,
            Route.school_id == school_id,
            Route.branch_id == branch_id,
        )
        .values(**values)
        .returning(Route)
    )
    await db.flush()
    route = result.scalar_one_or_none()
    if not route:
        raise RouteNotFoundError(identifier=route_id)
    return route


async def deactivate_route_by_route_id(
    db: AsyncSession,
    route_id: int,
    school_id: int,
    branch_id: int,
) -> Route:
    """Soft-delete a route. Uses RETURNING — single round-trip."""
    result = await db.execute(
        update(Route)
        .where(
            Route.route_id == route_id,
            Route.school_id == school_id,
            Route.branch_id == branch_id,
        )
        .values(is_active=False, updated_at=func.now())
        .returning(Route)
    )
    await db.flush()
    route = result.scalar_one_or_none()
    if not route:
        raise RouteNotFoundError(identifier=route_id)
    return route


# =============================================================================
# Stop Queries
# =============================================================================
async def get_all_stops(
    db: AsyncSession,
    school_id: int | None,
    branch_ids: list[int] | None,
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Stop], int]:

    query = select(Stop).options(
        selectinload(Stop.school),
        selectinload(Stop.branch),
    )
    if school_id is not None:
        query = query.where(
            Stop.school_id == school_id
        )

    if branch_ids is not None:
        query = query.where(
            Stop.branch_id.in_(branch_ids)
        )

    if active_only:
        query = query.where(
            Stop.is_active == True
        )

    total = await db.scalar(
        select(func.count()).select_from(
            query.subquery()
        )
    )

    result = await db.execute(
        query.order_by(Stop.stop_name)
        .limit(limit)
        .offset(offset)
    )

    return list(result.scalars().all()), total or 0

async def get_stop_by_stop_id(
    db: AsyncSession,
    stop_id: int,
    school_id: int,
    branch_id: int,
) -> Stop:
    """Fetch a stop scoped to branch. Raises StopNotFoundError if not found."""
    result = await db.execute(
        select(Stop).where(
            Stop.stop_id == stop_id,
            Stop.school_id == school_id,
            Stop.branch_id == branch_id,
        )
    )
    stop = result.scalar_one_or_none()
    if not stop:
        raise StopNotFoundError(identifier=stop_id)
    return stop


async def get_stop_by_stop_id_or_none(
    db: AsyncSession,
    stop_id: int,
    school_id: int,
    branch_id: int,
) -> Stop | None:
    """Fetch a stop scoped to branch. Returns None if not found."""
    result = await db.execute(
        select(Stop).where(
            Stop.stop_id == stop_id,
            Stop.school_id == school_id,
            Stop.branch_id == branch_id,
        )
    )
    return result.scalar_one_or_none()


async def get_all_stops_by_branch(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Stop], int]:
    """Fetch all stops for a branch with pagination."""
    query = select(Stop).where(
        Stop.school_id == school_id,
        Stop.branch_id == branch_id,
    )
    if active_only:
        query = query.where(Stop.is_active == True)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(Stop.stop_name).limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0


async def get_stops_by_branch_ids(
    db: AsyncSession,
    school_id: int,
    branch_ids: list[int],
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Stop], int]:
    """Fetch stops filtered to a list of branch_ids within a school."""
    query = select(Stop).where(
        Stop.school_id == school_id,
        Stop.branch_id.in_(branch_ids),
    )
    if active_only:
        query = query.where(Stop.is_active == True)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(Stop.stop_name).limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0


async def create_stop(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    stop_name: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> Stop:
    """Insert a new stop record."""
    stop = Stop(
        school_id=school_id,
        branch_id=branch_id,
        stop_name=stop_name,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(stop)
    await db.flush()
    await db.refresh(stop)
    return stop


async def update_stop_by_stop_id(
    db: AsyncSession,
    stop_id: int,
    school_id: int,
    branch_id: int,
    **kwargs,
) -> Stop:
    """Update stop fields. Uses RETURNING — single round-trip."""
    values = dict(kwargs)
    values["updated_at"] = func.now()

    result = await db.execute(
        update(Stop)
        .where(
            Stop.stop_id == stop_id,
            Stop.school_id == school_id,
            Stop.branch_id == branch_id,
        )
        .values(**values)
        .returning(Stop)
    )
    await db.flush()
    stop = result.scalar_one_or_none()
    if not stop:
        raise StopNotFoundError(identifier=stop_id)
    return stop


async def deactivate_stop_by_stop_id(
    db: AsyncSession,
    stop_id: int,
    school_id: int,
    branch_id: int,
) -> Stop:
    """Soft-delete a stop. Uses RETURNING — single round-trip."""
    result = await db.execute(
        update(Stop)
        .where(
            Stop.stop_id == stop_id,
            Stop.school_id == school_id,
            Stop.branch_id == branch_id,
        )
        .values(is_active=False, updated_at=func.now())
        .returning(Stop)
    )
    await db.flush()
    stop = result.scalar_one_or_none()
    if not stop:
        raise StopNotFoundError(identifier=stop_id)
    return stop


# =============================================================================
# RouteStop Queries
# =============================================================================

async def get_route_stop_by_id(
    db: AsyncSession,
    route_stop_id: int,
    route_id: int,
    school_id: int,
    branch_id: int,
) -> RouteStop:
    """Fetch a single route stop entry. Raises StopNotFoundError if not found."""
    result = await db.execute(
        select(RouteStop).where(
            RouteStop.route_stop_id == route_stop_id,
            RouteStop.route_id == route_id,
            RouteStop.school_id == school_id,
            RouteStop.branch_id == branch_id,
        )
    )
    route_stop = result.scalar_one_or_none()
    if not route_stop:
        raise StopNotFoundError(identifier=route_stop_id)
    return route_stop


async def get_route_stops_by_route_and_trip_type(
    db: AsyncSession,
    route_id: int,
    school_id: int,
    branch_id: int,
    trip_type: TripType,
) -> list[RouteStop]:
    """
    Fetch all stops for a route + trip_type ordered by stop_sequence.
    Used to build ordered PICKUP or DROPOFF stop list for a route.
    """
    result = await db.execute(
        select(RouteStop)
        .where(
            RouteStop.route_id == route_id,
            RouteStop.school_id == school_id,
            RouteStop.branch_id == branch_id,
            RouteStop.trip_type == trip_type.value,
        )
        .order_by(RouteStop.stop_sequence)
    )
    return list(result.scalars().all())


async def get_all_route_stops_by_route_id(
    db: AsyncSession,
    route_id: int,
    school_id: int,
    branch_id: int,
) -> list[RouteStop]:
    """Fetch all route stop entries for a route (both trip_types), ordered by trip_type then sequence."""
    result = await db.execute(
        select(RouteStop)
        .where(
            RouteStop.route_id == route_id,
            RouteStop.school_id == school_id,
            RouteStop.branch_id == branch_id,
        )
        .order_by(RouteStop.trip_type, RouteStop.stop_sequence)
    )
    return list(result.scalars().all())


async def create_route_stop(
    db: AsyncSession,
    route_id: int,
    stop_id: int,
    school_id: int,
    branch_id: int,
    trip_type: TripType,
    stop_sequence: int,
    estimated_time: str | None = None,
) -> RouteStop:
    """
    Add a stop to a route at a given sequence position.
    DB UNIQUE constraints enforce:
        - No duplicate stop per route + trip_type
        - No duplicate sequence per route + trip_type
    """
    from datetime import time as time_type
    parsed_time: time_type | None = None
    if estimated_time:
        h, m = estimated_time.split(":")
        parsed_time = time_type(int(h), int(m))

    route_stop = RouteStop(
        route_id=route_id,
        stop_id=stop_id,
        school_id=school_id,
        branch_id=branch_id,
        trip_type=trip_type.value,
        stop_sequence=stop_sequence,
        estimated_time=parsed_time,
    )
    db.add(route_stop)
    await db.flush()
    await db.refresh(route_stop)
    return route_stop


async def update_route_stop_by_id(
    db: AsyncSession,
    route_stop_id: int,
    route_id: int,
    school_id: int,
    branch_id: int,
    **kwargs,
) -> RouteStop:
    """Update a route stop entry. Uses RETURNING — single round-trip."""
    values = dict(kwargs)
    values["updated_at"] = func.now()

    # Parse estimated_time string to time object if provided
    if "estimated_time" in values and isinstance(values["estimated_time"], str):
        from datetime import time as time_type
        h, m = values["estimated_time"].split(":")
        values["estimated_time"] = time_type(int(h), int(m))

    result = await db.execute(
        update(RouteStop)
        .where(
            RouteStop.route_stop_id == route_stop_id,
            RouteStop.route_id == route_id,
            RouteStop.school_id == school_id,
            RouteStop.branch_id == branch_id,
        )
        .values(**values)
        .returning(RouteStop)
    )
    await db.flush()
    route_stop = result.scalar_one_or_none()
    if not route_stop:
        raise StopNotFoundError(identifier=route_stop_id)
    return route_stop


async def delete_route_stop_by_id(
    db: AsyncSession,
    route_stop_id: int,
    route_id: int,
    school_id: int,
    branch_id: int,
) -> None:
    """
    Hard-delete a route stop entry.
    RouteStop is a mapping record — removing it is not a "soft delete",
    it means "this stop is no longer part of this route".
    """
    result = await db.execute(
        delete(RouteStop).where(
            RouteStop.route_stop_id == route_stop_id,
            RouteStop.route_id == route_id,
            RouteStop.school_id == school_id,
            RouteStop.branch_id == branch_id,
        )
    )
    await db.flush()
    if result.rowcount == 0:
        raise StopNotFoundError(identifier=route_stop_id)