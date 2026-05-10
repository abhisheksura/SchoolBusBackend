from sqlalchemy.ext.asyncio import AsyncSession

from app.trips import repository as trip_repo
from app.trips.schemas import (
    PaginatedTripResponse,
    TripAssignAssets,
    TripCreate,
    TripLiveStatusResponse,
    TripLiveStatusUpsert,
    TripResponse,
    TripUpdateStatus,
)
from app.core.config import settings
from app.core.enums import TripStatus, TRIP_STATUS_TRANSITIONS
from app.core.exceptions import (
    ForbiddenError,
    InvalidStatusTransitionError,
    TripAlreadyExistsError,
    TripNotFoundError,
)
from app.core.schemas import paginate, pagination_params
from app.core.utils import utcnow


# =============================================================================
# Trip Services
# =============================================================================

async def create_trip(
    db: AsyncSession,
    payload: TripCreate,
) -> TripResponse:
    """
    Schedule a new trip.
    Checks for duplicate (route + date + trip_type) before inserting.
    Role check (BRANCH_ADMIN+) enforced at router.
    """
    existing = await trip_repo.get_trip_by_unique_key_or_none(
        db=db,
        school_id=payload.school_id,
        branch_id=payload.branch_id,
        route_id=payload.route_id,
        service_date=payload.service_date,
        trip_type=payload.trip_type,
    )
    if existing:
        raise TripAlreadyExistsError()

    trip = await trip_repo.create_trip(
        db=db,
        school_id=payload.school_id,
        branch_id=payload.branch_id,
        route_id=payload.route_id,
        service_date=payload.service_date,
        trip_type=payload.trip_type,
        bus_id=payload.bus_id,
        driver_id=payload.driver_id,
    )
    return TripResponse.model_validate(trip)


async def get_trip(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> TripResponse:
    """Fetch a single trip. Scope check BEFORE DB hit."""
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise TripNotFoundError(identifier=trip_id)

    trip = await trip_repo.get_trip_by_trip_id(db, trip_id, school_id, branch_id)
    return TripResponse.model_validate(trip)


async def get_all_trips(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    page: int,
    page_size: int,
    accessible_branch_ids: list[int] | None,
    service_date=None,
    trip_status: TripStatus | None = None,
    route_id: int | None = None,
) -> PaginatedTripResponse:
    """Fetch paginated trips filtered by scope and optional query filters."""
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)

    if accessible_branch_ids is None:
        trips, total = await trip_repo.get_all_trips_by_branch(
            db=db,
            school_id=school_id,
            branch_id=branch_id,
            limit=limit,
            offset=offset,
            service_date=service_date,
            trip_status=trip_status,
            route_id=route_id,
        )
    else:
        trips, total = await trip_repo.get_trips_by_branch_ids(
            db=db,
            school_id=school_id,
            branch_ids=accessible_branch_ids,
            limit=limit,
            offset=offset,
            service_date=service_date,
            trip_status=trip_status,
        )

    return paginate(
        items=[TripResponse.model_validate(t) for t in trips],
        total=total, page=page, page_size=page_size,
    )


async def assign_trip_assets(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
    payload: TripAssignAssets,
) -> TripResponse:
    """
    Assign or reassign bus/driver to a trip.
    Only allowed when trip is SCHEDULED.
    Role check enforced at router.
    """
    trip = await trip_repo.get_trip_by_trip_id(db, trip_id, school_id, branch_id)

    if trip.trip_status != TripStatus.SCHEDULED.value:
        raise ForbiddenError(
            detail=f"Cannot reassign assets on a {trip.trip_status} trip. Only SCHEDULED trips can be updated."
        )

    updated = await trip_repo.update_trip_assets(
        db=db,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        **payload.model_dump(exclude_unset=True),
    )
    return TripResponse.model_validate(updated)


async def update_trip_status(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
    payload: TripUpdateStatus,
) -> TripResponse:
    """
    Transition trip status.
    Validates transition via TRIP_STATUS_TRANSITIONS map.
    Automatically timestamps actual_start_time on IN_PROGRESS
    and actual_end_time on COMPLETED or CANCELLED.
    Role check enforced at router.
    """
    trip = await trip_repo.get_trip_by_trip_id(db, trip_id, school_id, branch_id)

    current = TripStatus(trip.trip_status)
    allowed = TRIP_STATUS_TRANSITIONS.get(current, set())
    if payload.trip_status not in allowed:
        raise InvalidStatusTransitionError(
            current=current.value,
            requested=payload.trip_status.value,
        )

    now = utcnow()
    actual_start_time = now if payload.trip_status == TripStatus.IN_PROGRESS else None
    actual_end_time   = now if payload.trip_status in (TripStatus.COMPLETED, TripStatus.CANCELLED) else None

    updated = await trip_repo.update_trip_status(
        db=db,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        new_status=payload.trip_status,
        actual_start_time=actual_start_time,
        actual_end_time=actual_end_time,
    )
    return TripResponse.model_validate(updated)


# =============================================================================
# TripLiveStatus Services
# =============================================================================

async def get_live_status(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
    accessible_branch_ids: list[int] | None,
) -> TripLiveStatusResponse:
    """
    Fetch live GPS position for a trip.
    Scope check BEFORE DB hit.
    Raises TripNotFoundError if trip not found or not yet started.
    """
    if accessible_branch_ids is not None and branch_id not in accessible_branch_ids:
        raise TripNotFoundError(identifier=trip_id)

    await trip_repo.get_trip_by_trip_id(db, trip_id, school_id, branch_id)

    live = await trip_repo.get_live_status_by_trip_id(db, trip_id)
    if not live:
        raise TripNotFoundError(identifier=trip_id)

    return TripLiveStatusResponse.model_validate(live)


async def upsert_live_status(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
    payload: TripLiveStatusUpsert,
) -> TripLiveStatusResponse:
    """
    Create or update live GPS status for a trip.
    Trip must be IN_PROGRESS — GPS pings on non-active trips are rejected.
    Role check (DRIVER+) enforced at router.
    """
    trip = await trip_repo.get_trip_by_trip_id(db, trip_id, school_id, branch_id)

    if trip.trip_status != TripStatus.IN_PROGRESS.value:
        raise ForbiddenError(
            detail=f"Cannot update live status for a {trip.trip_status} trip. Trip must be IN_PROGRESS."
        )

    live = await trip_repo.upsert_live_status(
        db=db,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        current_latitude=payload.current_latitude,
        current_longitude=payload.current_longitude,
        speed=payload.speed,
        heading=payload.heading,
        last_stop_id=payload.last_stop_id,
        last_stop_arrival_time=payload.last_stop_arrival_time,
    )
    return TripLiveStatusResponse.model_validate(live)

# =============================================================================
# Driver-Facing Trip Services
# =============================================================================
 
async def get_todays_trips_for_driver(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
) -> list[TripResponse]:
    """
    Fetch all trips assigned to the authenticated driver for today (UTC date).
    Only the calling driver's own trips — no cross-driver access possible
    because driver_id, school_id, and branch_id all come from the JWT.
 
    Returns all statuses (SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED)
    so the driver sees the full day's picture.
 
    Role check (DRIVER only) enforced at router.
    """
    from app.core.utils import utcnow
    today = utcnow().date()
 
    trips = await trip_repo.get_todays_trips_for_driver(
        db=db,
        driver_id=driver_id,
        school_id=school_id,
        branch_id=branch_id,
        today=today,
    )
    return [TripResponse.model_validate(t) for t in trips]
 
 
async def start_trip(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
    driver_id: int,
) -> TripResponse:
    """
    Start a trip: SCHEDULED → IN_PROGRESS.
    Sets actual_start_time to utcnow().
 
    Ownership check: the trip's driver_id must match the calling driver's JWT
    driver_id. A driver cannot start another driver's trip.
    Role check (DRIVER only) enforced at router.
 
    Raises:
        TripNotFoundError         : trip not found or not in caller's branch
        ForbiddenError            : trip belongs to a different driver
        InvalidStatusTransitionError : trip is not SCHEDULED
    """
    trip = await trip_repo.get_trip_by_trip_id(db, trip_id, school_id, branch_id)
 
    # Ownership check — driver can only act on their own trip
    if trip.driver_id != driver_id:
        raise TripNotFoundError(identifier=trip_id)  # 404 — don't reveal existence
 
    current = TripStatus(trip.trip_status)
    allowed = TRIP_STATUS_TRANSITIONS.get(current, set())
    if TripStatus.IN_PROGRESS not in allowed:
        raise InvalidStatusTransitionError(
            current=current.value,
            requested=TripStatus.IN_PROGRESS.value,
        )
 
    updated = await trip_repo.update_trip_status(
        db=db,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        new_status=TripStatus.IN_PROGRESS,
        actual_start_time=utcnow(),
    )
    return TripResponse.model_validate(updated)
 
 
async def end_trip(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
    driver_id: int,
) -> TripResponse:
    """
    End a trip: IN_PROGRESS → COMPLETED.
    Sets actual_end_time to utcnow().
 
    Ownership check: the trip's driver_id must match the calling driver's JWT
    driver_id.
    Role check (DRIVER only) enforced at router.
 
    Raises:
        TripNotFoundError         : trip not found or not in caller's branch
        ForbiddenError            : trip belongs to a different driver
        InvalidStatusTransitionError : trip is not IN_PROGRESS
    """
    trip = await trip_repo.get_trip_by_trip_id(db, trip_id, school_id, branch_id)
 
    if trip.driver_id != driver_id:
        raise TripNotFoundError(identifier=trip_id)
 
    current = TripStatus(trip.trip_status)
    allowed = TRIP_STATUS_TRANSITIONS.get(current, set())
    if TripStatus.COMPLETED not in allowed:
        raise InvalidStatusTransitionError(
            current=current.value,
            requested=TripStatus.COMPLETED.value,
        )
 
    updated = await trip_repo.update_trip_status(
        db=db,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        new_status=TripStatus.COMPLETED,
        actual_end_time=utcnow(),
    )
    return TripResponse.model_validate(updated)
 
 
async def cancel_trip(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
    driver_id: int,
) -> TripResponse:
    """
    Cancel a trip: SCHEDULED | IN_PROGRESS → CANCELLED.
    Sets actual_end_time to utcnow() (records when the cancellation happened).
 
    Ownership check: the trip's driver_id must match the calling driver's JWT
    driver_id.
    Role check (DRIVER only) enforced at router.
 
    Raises:
        TripNotFoundError         : trip not found or not in caller's branch
        InvalidStatusTransitionError : trip is already COMPLETED or CANCELLED
    """
    trip = await trip_repo.get_trip_by_trip_id(db, trip_id, school_id, branch_id)
 
    if trip.driver_id != driver_id:
        raise TripNotFoundError(identifier=trip_id)
 
    current = TripStatus(trip.trip_status)
    allowed = TRIP_STATUS_TRANSITIONS.get(current, set())
    if TripStatus.CANCELLED not in allowed:
        raise InvalidStatusTransitionError(
            current=current.value,
            requested=TripStatus.CANCELLED.value,
        )
 
    updated = await trip_repo.update_trip_status(
        db=db,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        new_status=TripStatus.CANCELLED,
        actual_end_time=utcnow(),
    )
    return TripResponse.model_validate(updated)
 