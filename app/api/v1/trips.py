from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.trips import service as trip_service
from app.trips.schemas import (
    PaginatedTripResponse,
    TodaysTripResponse,
    TripAssignAssets,
    TripCreate,
    TripLiveStatusResponse,
    TripLiveStatusUpsert,
    TripResponse,
    TripUpdateStatus,
)
from app.core.config import settings
from app.core.db import get_db
from app.core.enums import RoleName, TripStatus
from app.api.v1.dependencies import (
    AnyAuthenticated,
    CurrentUser,
    require_roles,
)

router = APIRouter()

TripAdminRequired     = Depends(require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN))
DriverOrAdminRequired = Depends(require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN, RoleName.DRIVER))
DriverRequired        = Depends(require_roles(RoleName.DRIVER))


# =============================================================================
# Trip Routes
# =============================================================================

@router.post(
    "/trips/",
    response_model=TripResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule a trip",
    description=(
        "Create a new trip for a route on a given date. "
        "One trip per route per service_date per trip_type. "
        "BRANCH_ADMIN or above required."
    ),
)
async def create_trip(
    payload: TripCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = TripAdminRequired,
) -> TripResponse:
    return await trip_service.create_trip(db=db, payload=payload)


@router.get(
    "/trips/",
    response_model=PaginatedTripResponse,
    status_code=status.HTTP_200_OK,
    summary="List trips",
    description=(
        "Fetch paginated trips filtered by branch scope. "
        "Optionally filter by service_date, trip_status, or route_id."
    ),
)
async def get_all_trips(
    school_id   : int              = Query(...),
    branch_id   : int              = Query(...),
    page        : int              = Query(default=1, ge=1),
    page_size   : int              = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    service_date: date | None      = Query(default=None, description="Filter by specific service date."),
    trip_status : TripStatus | None = Query(default=None, description="Filter by trip status."),
    route_id    : int | None       = Query(default=None, description="Filter by route."),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedTripResponse:
    return await trip_service.get_all_trips(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
        service_date=service_date,
        trip_status=trip_status,
        route_id=route_id,
    )


@router.get(
    "/trips/{trip_id}",
    response_model=TripResponse,
    status_code=status.HTTP_200_OK,
    summary="Get trip",
    description="Fetch a single trip. Returns 404 if outside caller's scope.",
)
async def get_trip(
    trip_id  : int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> TripResponse:
    return await trip_service.get_trip(
        db=db,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.patch(
    "/trips/{trip_id}/assign",
    response_model=TripResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign bus/driver to trip",
    description=(
        "Assign or reassign bus and/or driver to a SCHEDULED trip. "
        "Fails if trip is already IN_PROGRESS or completed. "
        "BRANCH_ADMIN or above required."
    ),
)
async def assign_trip_assets(
    trip_id  : int,
    payload  : TripAssignAssets,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = TripAdminRequired,
) -> TripResponse:
    return await trip_service.assign_trip_assets(
        db=db,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
    )


@router.patch(
    "/trips/{trip_id}/status",
    response_model=TripResponse,
    status_code=status.HTTP_200_OK,
    summary="Update trip status",
    description=(
        "Transition trip status. Valid transitions: "
        "SCHEDULED → IN_PROGRESS | CANCELLED. "
        "IN_PROGRESS → COMPLETED | CANCELLED. "
        "COMPLETED and CANCELLED are terminal — no further transitions allowed. "
        "BRANCH_ADMIN or above required."
    ),
)
async def update_trip_status(
    trip_id  : int,
    payload  : TripUpdateStatus,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = TripAdminRequired,
) -> TripResponse:
    return await trip_service.update_trip_status(
        db=db,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
    )

# =============================================================================
# Driver-facing Routes
# =============================================================================

@router.get(
    "/driver/todays-trips",
    response_model=list[TodaysTripResponse],
    status_code=status.HTTP_200_OK,
    summary="Driver — today's trips",
    description=(
        "Fetch all trips assigned to the authenticated driver for today (UTC). "
        "Returns SCHEDULED, IN_PROGRESS, COMPLETED, and CANCELLED trips "
        "so the driver sees the full picture of their day. "
        "school_id and branch_id are derived from the JWT — no query params needed. "
        "DRIVER role required."
    ),
)
async def get_todays_trips(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = DriverRequired,
) -> list[TodaysTripResponse]:
    """
    No school_id / branch_id query params — all context comes from the JWT.
    A driver can only see their own trips in their own branch.
    """
    if current_user.driver_id is None:
        # Driver record not linked to this user account yet
        raise ForbiddenError(
            detail="No driver profile is linked to this account. Contact your administrator."
        )
    return await trip_service.get_todays_trips_for_driver(
        db=db,
        driver_id=current_user.driver_id,
        school_id=current_user.school_id,
        branch_id=current_user.branch_id,
    )
 
 
@router.put(
    "/trips/{trip_id}/start",
    response_model=TripResponse,
    status_code=status.HTTP_200_OK,
    summary="Driver — start trip",
    description=(
        "Start a SCHEDULED trip: SCHEDULED → IN_PROGRESS. "
        "Records actual_start_time. "
        "Driver can only start their own assigned trip. "
        "DRIVER role required."
    ),
)
async def start_trip(
    trip_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = DriverRequired,
) -> TripResponse:
    """
    No school_id / branch_id query params — all context from JWT.
    Ownership verified in service: trip.driver_id must equal current_user.driver_id.
    """
    if current_user.driver_id is None:
        raise ForbiddenError(
            detail="No driver profile is linked to this account. Contact your administrator."
        )
    return await trip_service.start_trip(
        db=db,
        trip_id=trip_id,
        school_id=current_user.school_id,
        branch_id=current_user.branch_id,
        driver_id=current_user.driver_id,
    )
 
 
@router.put(
    "/trips/{trip_id}/end",
    response_model=TripResponse,
    status_code=status.HTTP_200_OK,
    summary="Driver — end trip",
    description=(
        "Complete an IN_PROGRESS trip: IN_PROGRESS → COMPLETED. "
        "Records actual_end_time. "
        "Driver can only end their own assigned trip. "
        "DRIVER role required."
    ),
)
async def end_trip(
    trip_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = DriverRequired,
) -> TripResponse:
    if current_user.driver_id is None:
        raise ForbiddenError(
            detail="No driver profile is linked to this account. Contact your administrator."
        )
    return await trip_service.end_trip(
        db=db,
        trip_id=trip_id,
        school_id=current_user.school_id,
        branch_id=current_user.branch_id,
        driver_id=current_user.driver_id,
    )
 
 
@router.put(
    "/trips/{trip_id}/cancel",
    response_model=TripResponse,
    status_code=status.HTTP_200_OK,
    summary="Driver — cancel trip",
    description=(
        "Cancel a trip: SCHEDULED | IN_PROGRESS → CANCELLED. "
        "Records actual_end_time (when the cancellation occurred). "
        "Driver can only cancel their own assigned trip. "
        "COMPLETED trips cannot be cancelled. "
        "DRIVER role required."
    ),
)
async def cancel_trip(
    trip_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = DriverRequired,
) -> TripResponse:
    if current_user.driver_id is None:
        raise ForbiddenError(
            detail="No driver profile is linked to this account. Contact your administrator."
        )
    return await trip_service.cancel_trip(
        db=db,
        trip_id=trip_id,
        school_id=current_user.school_id,
        branch_id=current_user.branch_id,
        driver_id=current_user.driver_id,
    )
 
# =============================================================================
# TripLiveStatus Routes
# =============================================================================

@router.get(
    "/trips/{trip_id}/live-status",
    response_model=TripLiveStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get live trip position",
    description=(
        "Get the current GPS position for an active trip. "
        "Always query live position from here — never from gps_logs. "
        "Returns 404 if the trip has not started yet."
    ),
)
async def get_live_status(
    trip_id  : int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> TripLiveStatusResponse:
    return await trip_service.get_live_status(
        db=db,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.put(
    "/trips/{trip_id}/live-status",
    response_model=TripLiveStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Update live trip position",
    description=(
        "Upsert live GPS position for an IN_PROGRESS trip. "
        "Creates the record on first ping, updates on subsequent pings. "
        "Rejects updates if trip is not IN_PROGRESS. "
        "DRIVER or above required."
    ),
)
async def upsert_live_status(
    trip_id  : int,
    payload  : TripLiveStatusUpsert,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = DriverOrAdminRequired,
) -> TripLiveStatusResponse:
    return await trip_service.upsert_live_status(
        db=db,
        trip_id=trip_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
    )