from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.trips.models import Trip, TripLiveStatus
from app.core.enums import TripStatus, TripType
from app.core.exceptions import TripAlreadyExistsError, TripNotFoundError
from app.core.utils import utcnow


# =============================================================================
# Trip Queries
# =============================================================================

async def get_trip_by_trip_id(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
) -> Trip:
    """Fetch a trip scoped to branch. Raises TripNotFoundError if not found."""
    result = await db.execute(
        select(Trip).where(
            Trip.trip_id == trip_id,
            Trip.school_id == school_id,
            Trip.branch_id == branch_id,
        )
    )
    trip = result.scalar_one_or_none()
    if not trip:
        raise TripNotFoundError(identifier=trip_id)
    return trip


async def get_trip_by_unique_key_or_none(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    route_id: int,
    service_date,
    trip_type: TripType,
) -> Trip | None:
    """
    Fetch a trip by its natural unique key (route + date + type).
    Used to prevent duplicate creation before insert.
    """
    result = await db.execute(
        select(Trip).where(
            Trip.school_id == school_id,
            Trip.branch_id == branch_id,
            Trip.route_id == route_id,
            Trip.service_date == service_date,
            Trip.trip_type == trip_type.value,
        )
    )
    return result.scalar_one_or_none()


async def get_all_trips_by_branch(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    limit: int,
    offset: int,
    service_date=None,
    trip_status: TripStatus | None = None,
    route_id: int | None = None,
) -> tuple[list[Trip], int]:
    """Fetch trips for a branch with optional date / status / route filters."""
    query = select(Trip).where(
        Trip.school_id == school_id,
        Trip.branch_id == branch_id,
    )
    if service_date:
        query = query.where(Trip.service_date == service_date)
    if trip_status:
        query = query.where(Trip.trip_status == trip_status.value)
    if route_id:
        query = query.where(Trip.route_id == route_id)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(Trip.service_date.desc(), Trip.trip_type).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def get_trips_by_branch_ids(
    db: AsyncSession,
    school_id: int,
    branch_ids: list[int],
    limit: int,
    offset: int,
    service_date=None,
    trip_status: TripStatus | None = None,
) -> tuple[list[Trip], int]:
    """Fetch trips filtered to a list of branch_ids."""
    query = select(Trip).where(
        Trip.school_id == school_id,
        Trip.branch_id.in_(branch_ids),
    )
    if service_date:
        query = query.where(Trip.service_date == service_date)
    if trip_status:
        query = query.where(Trip.trip_status == trip_status.value)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(Trip.service_date.desc(), Trip.trip_type).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def create_trip(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    route_id: int,
    service_date,
    trip_type: TripType,
    bus_id: int | None = None,
    driver_id: int | None = None,
) -> Trip:
    """Insert a new trip. Caller must verify uniqueness before calling."""
    trip = Trip(
        school_id=school_id,
        branch_id=branch_id,
        route_id=route_id,
        service_date=service_date,
        trip_type=trip_type.value,
        bus_id=bus_id,
        driver_id=driver_id,
    )
    db.add(trip)
    await db.flush()
    await db.refresh(trip)
    return trip


async def update_trip_assets(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
    **kwargs,
) -> Trip:
    """
    Update bus_id and/or driver_id on a trip.
    Uses RETURNING — single round-trip.
    Caller must verify trip is SCHEDULED before calling.
    """
    values = dict(kwargs)
    values["updated_at"] = func.now()

    result = await db.execute(
        update(Trip)
        .where(
            Trip.trip_id == trip_id,
            Trip.school_id == school_id,
            Trip.branch_id == branch_id,
        )
        .values(**values)
        .returning(Trip)
    )
    await db.flush()
    trip = result.scalar_one_or_none()
    if not trip:
        raise TripNotFoundError(identifier=trip_id)
    return trip


async def update_trip_status(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
    new_status: TripStatus,
    actual_start_time=None,
    actual_end_time=None,
) -> Trip:
    """
    Update trip_status and optionally stamp actual_start_time / actual_end_time.
    Uses RETURNING — single round-trip.
    Caller must validate the transition before calling.
    """
    values: dict = {
        "trip_status": new_status.value,
        "updated_at": func.now(),
    }
    if actual_start_time is not None:
        values["actual_start_time"] = actual_start_time
    if actual_end_time is not None:
        values["actual_end_time"] = actual_end_time

    result = await db.execute(
        update(Trip)
        .where(
            Trip.trip_id == trip_id,
            Trip.school_id == school_id,
            Trip.branch_id == branch_id,
        )
        .values(**values)
        .returning(Trip)
    )
    await db.flush()
    trip = result.scalar_one_or_none()
    if not trip:
        raise TripNotFoundError(identifier=trip_id)
    return trip


# =============================================================================
# TripLiveStatus Queries
# =============================================================================

async def get_live_status_by_trip_id(
    db: AsyncSession,
    trip_id: int,
) -> TripLiveStatus | None:
    """Fetch live GPS status for a trip. Returns None if trip has not started."""
    result = await db.execute(
        select(TripLiveStatus).where(TripLiveStatus.trip_id == trip_id)
    )
    return result.scalar_one_or_none()


async def upsert_live_status(
    db: AsyncSession,
    trip_id: int,
    school_id: int,
    branch_id: int,
    current_latitude: float,
    current_longitude: float,
    speed: float | None = None,
    heading: float | None = None,
    last_stop_id: int | None = None,
    last_stop_arrival_time=None,
) -> TripLiveStatus:
    """
    Create or update the live GPS status for a trip.
    If a record exists for this trip_id, updates it.
    If not, inserts a new record.
    """
    existing = await get_live_status_by_trip_id(db, trip_id)

    if existing:
        result = await db.execute(
            update(TripLiveStatus)
            .where(TripLiveStatus.trip_id == trip_id)
            .values(
                current_latitude=current_latitude,
                current_longitude=current_longitude,
                speed=speed,
                heading=heading,
                last_stop_id=last_stop_id,
                last_stop_arrival_time=last_stop_arrival_time,
                last_updated=utcnow(),
            )
            .returning(TripLiveStatus)
        )
        await db.flush()
        return result.scalar_one()

    live = TripLiveStatus(
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        current_latitude=current_latitude,
        current_longitude=current_longitude,
        speed=speed,
        heading=heading,
        last_stop_id=last_stop_id,
        last_stop_arrival_time=last_stop_arrival_time,
    )
    db.add(live)
    await db.flush()
    await db.refresh(live)
    return live

async def get_todays_trips_for_driver(
    db: AsyncSession,
    driver_id: int,
    school_id: int,
    branch_id: int,
    today,
) -> list[Trip]:
    """
    Fetch all trips assigned to a specific driver for today.
    Ordered by trip_type (PICKUP before DROPOFF).
    Scoped to the driver's school and branch from JWT — driver cannot
    query another branch's trips.
    """
    result = await db.execute(
        select(Trip).where(
            Trip.driver_id == driver_id,
            Trip.school_id == school_id,
            Trip.branch_id == branch_id,
            Trip.service_date == today,
        ).order_by(Trip.trip_type)
    )
    return list(result.scalars().all())
 