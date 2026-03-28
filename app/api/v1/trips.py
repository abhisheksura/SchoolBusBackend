from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.trips import service as trip_service
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