from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.routes import repository as route_repo
from app.routes.schemas import (
    RouteCreate,
    RouteDetailResponse,
    RouteResponse,
    RouteStopCreate,
    RouteStopResponse,
    RouteStopUpdate,
    RouteUpdate,
    StopCreate,
    StopResponse,
    StopUpdate,
    PaginatedRouteResponse,
    PaginatedStopResponse,
)
from app.core.config import settings
from app.core.enums import TripType
from app.core.exceptions import (
    DuplicateEntryError,
    RouteNotFoundError,
    StopNotFoundError,
)
from app.core.schemas import paginate, pagination_params


# =============================================================================
# Route Services
# =============================================================================

async def create_route(
    db: AsyncSession,
    payload: RouteCreate,
) -> RouteResponse:
    """
    Create a new route.
    Role check (BRANCH_ADMIN+) enforced at router.
    """
    try:
        route = await route_repo.create_route(
            db=db,
            school_id=payload.school_id,
            branch_id=payload.branch_id,
            route_code=payload.route_code,
            route_name=payload.route_name,
            description=payload.description,
        )
    except IntegrityError:
        raise DuplicateEntryError(field="route_code", value=payload.route_code)
    return RouteResponse.model_validate(route)


async def get_route(
    db: AsyncSession,
    route_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> RouteResponse:
    """Fetch a single route. Scope check BEFORE DB hit."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise RouteNotFoundError(identifier=route_id)

    route = await route_repo.get_route_by_route_id(db, route_id, school_id, branch_id)
    return RouteResponse.model_validate(route)


async def get_route_detail(
    db: AsyncSession,
    route_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> RouteDetailResponse:
    """
    Fetch a route with its full ordered stop lists (PICKUP + DROPOFF).
    Uses get_route_with_stops_by_route_id — eagerly loads route_stops.
    Scope check BEFORE DB hit.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise RouteNotFoundError(identifier=route_id)

    route = await route_repo.get_route_with_stops_by_route_id(
        db, route_id, school_id, branch_id
    )
    pickup_stops  = sorted(
        [rs for rs in route.route_stops if rs.trip_type == TripType.PICKUP.value],
        key=lambda rs: rs.stop_sequence,
    )
    dropoff_stops = sorted(
        [rs for rs in route.route_stops if rs.trip_type == TripType.DROPOFF.value],
        key=lambda rs: rs.stop_sequence,
    )

    return RouteDetailResponse(
        route_id=route.route_id,
        school_id=route.school_id,
        branch_id=route.branch_id,
        route_code=route.route_code,
        route_name=route.route_name,
        description=route.description,
        is_active=route.is_active,
        created_at=route.created_at,
        updated_at=route.updated_at,
        pickup_stops=[RouteStopResponse.model_validate(rs) for rs in pickup_stops],
        dropoff_stops=[RouteStopResponse.model_validate(rs) for rs in dropoff_stops],
    )


async def get_all_routes(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    page: int,
    page_size: int,
    accessible_branch_ids: list[int] | None,
    active_only: bool = True,
) -> PaginatedRouteResponse:
    """Fetch paginated routes for a branch, filtered by caller's scope."""
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)

    if accessible_branch_ids is None:
        routes, total = await route_repo.get_all_routes_by_branch(
            db=db, school_id=school_id, branch_id=branch_id,
            limit=limit, offset=offset, active_only=active_only,
        )
    else:
        routes, total = await route_repo.get_routes_by_branch_ids(
            db=db, school_id=school_id, branch_ids=accessible_branch_ids,
            limit=limit, offset=offset, active_only=active_only,
        )

    return paginate(
        items=[RouteResponse.model_validate(r) for r in routes],
        total=total, page=page, page_size=page_size,
    )


async def update_route(
    db: AsyncSession,
    route_id: int,
    school_id: int,
    branch_id: int,
    payload: RouteUpdate,
) -> RouteResponse:
    """Update a route. Role check enforced at router."""
    try:
        route = await route_repo.update_route_by_route_id(
            db=db,
            route_id=route_id,
            school_id=school_id,
            branch_id=branch_id,
            **payload.model_dump(exclude_unset=True),
        )
    except IntegrityError:
        raise DuplicateEntryError(field="route_code", value=payload.route_code or "")
    return RouteResponse.model_validate(route)


async def deactivate_route(
    db: AsyncSession,
    route_id: int,
    school_id: int,
    branch_id: int,
) -> RouteResponse:
    """Soft-delete a route. Role check enforced at router."""
    route = await route_repo.deactivate_route_by_route_id(
        db, route_id, school_id, branch_id
    )
    return RouteResponse.model_validate(route)


# =============================================================================
# Stop Services
# =============================================================================

async def create_stop(
    db: AsyncSession,
    payload: StopCreate,
) -> StopResponse:
    """
    Create a new stop.
    Role check (BRANCH_ADMIN+) enforced at router.
    """
    try:
        stop = await route_repo.create_stop(
            db=db,
            school_id=payload.school_id,
            branch_id=payload.branch_id,
            stop_name=payload.stop_name,
            latitude=payload.latitude,
            longitude=payload.longitude,
        )
    except IntegrityError:
        raise DuplicateEntryError(field="stop_name", value=payload.stop_name)
    return StopResponse.model_validate(stop)


async def get_stop(
    db: AsyncSession,
    stop_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> StopResponse:
    """Fetch a single stop. Scope check BEFORE DB hit."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise StopNotFoundError(identifier=stop_id)

    stop = await route_repo.get_stop_by_stop_id(db, stop_id, school_id, branch_id)
    return StopResponse.model_validate(stop)


async def get_all_stops(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    page: int,
    page_size: int,
    accessible_branch_ids: list[int] | None,
    active_only: bool = True,
) -> PaginatedStopResponse:
    """Fetch paginated stops for a branch, filtered by caller's scope."""
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)

    if accessible_branch_ids is None:
        stops, total = await route_repo.get_all_stops_by_branch(
            db=db, school_id=school_id, branch_id=branch_id,
            limit=limit, offset=offset, active_only=active_only,
        )
    else:
        stops, total = await route_repo.get_stops_by_branch_ids(
            db=db, school_id=school_id, branch_ids=accessible_branch_ids,
            limit=limit, offset=offset, active_only=active_only,
        )

    return paginate(
        items=[StopResponse.model_validate(s) for s in stops],
        total=total, page=page, page_size=page_size,
    )


async def update_stop(
    db: AsyncSession,
    stop_id: int,
    school_id: int,
    branch_id: int,
    payload: StopUpdate,
) -> StopResponse:
    """Update a stop. Role check enforced at router."""
    try:
        stop = await route_repo.update_stop_by_stop_id(
            db=db,
            stop_id=stop_id,
            school_id=school_id,
            branch_id=branch_id,
            **payload.model_dump(exclude_unset=True),
        )
    except IntegrityError:
        raise DuplicateEntryError(field="stop_name", value=payload.stop_name or "")
    return StopResponse.model_validate(stop)


async def deactivate_stop(
    db: AsyncSession,
    stop_id: int,
    school_id: int,
    branch_id: int,
) -> StopResponse:
    """
    Soft-delete a stop. Role check enforced at router.
    DB will raise IntegrityError if stop is in use by any route_stops
    (ondelete=RESTRICT on stop_id FK) — surfaces as 500 without explicit catch.
    Future improvement: check for active route_stops before deactivating.
    """
    stop = await route_repo.deactivate_stop_by_stop_id(
        db, stop_id, school_id, branch_id
    )
    return StopResponse.model_validate(stop)


# =============================================================================
# RouteStop Services
# =============================================================================

async def add_stop_to_route(
    db: AsyncSession,
    route_id: int,
    school_id: int,
    branch_id: int,
    payload: RouteStopCreate,
    accessible_branch_ids: list[int] | None,
) -> RouteStopResponse:
    """
    Add a stop to a route at a given sequence position for a trip_type.
    Verifies:
        1. Caller has branch access
        2. Route exists in this branch
        3. Stop exists and is active in this branch
    DB UNIQUE constraints reject duplicate stop or sequence per route + trip_type.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise RouteNotFoundError(identifier=route_id)

    # Verify route exists
    await route_repo.get_route_by_route_id(db, route_id, school_id, branch_id)

    # Verify stop exists and is active
    stop = await route_repo.get_stop_by_stop_id(db, payload.stop_id, school_id, branch_id)
    if not stop.is_active:
        raise StopNotFoundError(identifier=payload.stop_id)

    try:
        route_stop = await route_repo.create_route_stop(
            db=db,
            route_id=route_id,
            stop_id=payload.stop_id,
            school_id=school_id,
            branch_id=branch_id,
            trip_type=payload.trip_type,
            stop_sequence=payload.stop_sequence,
            estimated_time=payload.estimated_time,
        )
    except IntegrityError:
        raise DuplicateEntryError(
            field="stop_sequence or stop_id",
            value=f"sequence {payload.stop_sequence} or stop {payload.stop_id} already exists for this route + trip_type",
        )
    return RouteStopResponse.model_validate(route_stop)


async def update_route_stop(
    db: AsyncSession,
    route_stop_id: int,
    route_id: int,
    school_id: int,
    branch_id: int,
    payload: RouteStopUpdate,
    accessible_branch_ids: list[int] | None,
) -> RouteStopResponse:
    """Update a route stop entry (sequence or estimated_time only)."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise StopNotFoundError(identifier=route_stop_id)

    try:
        route_stop = await route_repo.update_route_stop_by_id(
            db=db,
            route_stop_id=route_stop_id,
            route_id=route_id,
            school_id=school_id,
            branch_id=branch_id,
            **payload.model_dump(exclude_unset=True),
        )
    except IntegrityError:
        raise DuplicateEntryError(
            field="stop_sequence",
            value=str(payload.stop_sequence or ""),
        )
    return RouteStopResponse.model_validate(route_stop)


async def remove_stop_from_route(
    db: AsyncSession,
    route_stop_id: int,
    route_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> None:
    """
    Remove a stop from a route (hard-delete the route_stop record).
    This is not a soft-delete — the mapping is simply removed.
    Role check enforced at router.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise StopNotFoundError(identifier=route_stop_id)

    await route_repo.delete_route_stop_by_id(
        db, route_stop_id, route_id, school_id, branch_id
    )


async def get_route_stops(
    db: AsyncSession,
    route_id: int,
    school_id: int,
    branch_id: int,
    trip_type: TripType | None,
    accessible_branch_ids: list[int] | None,
) -> list[RouteStopResponse]:
    """
    Get ordered stop list for a route.
    If trip_type is provided, returns stops for that type only.
    Otherwise returns all stops (both types) ordered by trip_type then sequence.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise RouteNotFoundError(identifier=route_id)

    # Verify route exists
    await route_repo.get_route_by_route_id(db, route_id, school_id, branch_id)

    if trip_type:
        stops = await route_repo.get_route_stops_by_route_and_trip_type(
            db, route_id, school_id, branch_id, trip_type
        )
    else:
        stops = await route_repo.get_all_route_stops_by_route_id(
            db, route_id, school_id, branch_id
        )

    return [RouteStopResponse.model_validate(rs) for rs in stops]