from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.routes import service as route_service
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
from app.core.db import get_db
from app.core.enums import RoleName, TripType
from app.core.schemas import TenantScopeRequest
from app.core.scope import validate_scope_access
from app.api.v1.dependencies import (
    AnyAuthenticated,
    CurrentUser,
    require_roles,
)

router = APIRouter()

# Convenience alias — BRANCH_ADMIN, SCHOOL_ADMIN, SUPER_ADMIN
RouteAdminRequired = Depends(
    require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN)
)


# =============================================================================
# Route Routes
# =============================================================================

@router.post(
    "/routes/",
    response_model=RouteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create route",
    description="Create a new route. BRANCH_ADMIN or above required.",
)
async def create_route(
    payload: RouteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = RouteAdminRequired,
) -> RouteResponse:
    return await route_service.create_route(db=db, payload=payload)


@router.get(
    "/routes/",
    response_model=PaginatedRouteResponse,
    status_code=status.HTTP_200_OK,
    summary="List routes",
    description="Fetch paginated routes filtered by caller's branch scope.",
)
async def get_all_routes(
    school_id  : int  = Query(...),
    branch_id  : int  = Query(...),
    page       : int  = Query(default=1, ge=1),
    page_size  : int  = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    active_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedRouteResponse:

    validate_scope_access(
        current_user=current_user,
        school_id=school_id,
        branch_id=branch_id,
    )
    return await route_service.get_all_routes(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        active_only=active_only,
    )

@router.get(
    "/routes/{route_id}",
    response_model=RouteResponse,
    status_code=status.HTTP_200_OK,
    summary="Get route",
    description="Fetch a single route. Returns 404 if outside caller's scope.",
)
async def get_route(
    route_id : int,
    school_id: int | None = Query(default=None, description="School ID"),
    branch_id: int | None = Query(default=None, description="Branch ID"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> RouteResponse:
    return await route_service.get_route(
        db=db,
        route_id=route_id,
        school_id=school_id,
        branch_id=branch_id,
        # accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.get(
    "/routes/{route_id}/detail",
    response_model=RouteDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get route with stops",
    description=(
        "Fetch a route with its full ordered stop lists for both PICKUP and DROPOFF. "
        "Returns 404 if outside caller's scope."
    ),
)
async def get_route_detail(
    route_id : int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> RouteDetailResponse:
    return await route_service.get_route_detail(
        db=db,
        route_id=route_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.patch(
    "/routes/{route_id}",
    response_model=RouteResponse,
    status_code=status.HTTP_200_OK,
    summary="Update route",
    description="Partially update a route. BRANCH_ADMIN or above required.",
)
async def update_route(
    route_id : int,
    payload  : RouteUpdate,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = RouteAdminRequired,
) -> RouteResponse:
    return await route_service.update_route(
        db=db,
        route_id=route_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
    )


@router.patch(
    "/routes/{route_id}/deactivate",
    response_model=RouteResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate route",
    description="Soft-delete a route by setting is_active=False. BRANCH_ADMIN or above required.",
)
async def deactivate_route(
    route_id : int,
    scope: TenantScopeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = RouteAdminRequired,
) -> RouteResponse:
    return await route_service.deactivate_route(
        db=db,
        route_id=route_id,
        school_id=scope.school_id,
        branch_id=scope.branch_id,
    )

@router.patch(
    "/routes/{route_id}/reactivate",
    response_model=RouteResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate Route",
    description="Activate a Route. BRANCH_ADMIN or above required.",
)
async def reactivate_stop(
    route_id: int,
    scope: TenantScopeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = RouteAdminRequired,
) -> RouteResponse:
    return await route_service.reactivate_route(
        db=db, route_id=route_id, school_id=scope.school_id, branch_id=scope.branch_id,
    )

# =============================================================================
# Stop Routes
# =============================================================================

@router.post(
    "/stops/",
    response_model=StopResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create stop",
    description="Create a new physical bus stop. BRANCH_ADMIN or above required.",
)
async def create_stop(
    payload: StopCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = RouteAdminRequired,
) -> StopResponse:
    return await route_service.create_stop(db=db, payload=payload)


@router.get(
    "/stops/",
    response_model=PaginatedStopResponse,
    status_code=status.HTTP_200_OK,
    summary="List stops",
    description="Fetch paginated stops filtered by caller's branch scope.",
)
async def get_all_stops(
    school_id  : int  = Query(...),
    branch_id  : int  = Query(...),
    page       : int  = Query(default=1, ge=1),
    page_size  : int  = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    active_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedStopResponse:
    
    return await route_service.get_all_stops(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        active_only=active_only,
    )


@router.get(
    "/stops/{stop_id}",
    response_model=StopResponse,
    status_code=status.HTTP_200_OK,
    summary="Get stop",
    description="Fetch a single stop. Returns 404 if outside caller's scope.",
)
async def get_stop(
    stop_id  : int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> StopResponse:
    return await route_service.get_stop(
        db=db,
        stop_id=stop_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.patch(
    "/stops/{stop_id}",
    response_model=StopResponse,
    status_code=status.HTTP_200_OK,
    summary="Update stop",
    description="Partially update a stop. BRANCH_ADMIN or above required.",
)
async def update_stop(
    stop_id  : int,
    payload  : StopUpdate,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = RouteAdminRequired,
) -> StopResponse:
    return await route_service.update_stop(
        db=db,
        stop_id=stop_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
    )


@router.patch(
    "/stops/{stop_id}/deactivate",
    response_model=StopResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate stop",
    description="Soft-delete a stop. BRANCH_ADMIN or above required.",
)
async def deactivate_stop(
    stop_id  : int,
    scope: TenantScopeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = RouteAdminRequired,
) -> StopResponse:
    return await route_service.deactivate_stop(
        db=db,
        stop_id=stop_id,
        school_id=scope.school_id,
        branch_id=scope.branch_id,
    )

@router.patch(
    "/stops/{stop_id}/reactivate",
    response_model=StopResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate Stop",
    description="Activate a Stop. BRANCH_ADMIN or above required.",
)
async def reactivate_stop(
    stop_id: int,
    scope: TenantScopeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = RouteAdminRequired,
) -> StopResponse:
    return await route_service.reactivate_stop(
        db=db, stop_id=stop_id, school_id=scope.school_id, branch_id=scope.branch_id,
    )

# =============================================================================
# RouteStop Routes (nested under /routes/{route_id}/stops)
# =============================================================================

@router.get(
    "/routes/{route_id}/stops",
    response_model=list[RouteStopResponse],
    status_code=status.HTTP_200_OK,
    summary="Get route stops",
    description=(
        "Get ordered stop list for a route. "
        "Optionally filter by trip_type (PICKUP or DROPOFF). "
        "Returns stops ordered by sequence."
    ),
)
async def get_route_stops(
    route_id : int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    trip_type: TripType | None = Query(default=None, description="Filter by PICKUP or DROPOFF."),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> list[RouteStopResponse]:
    return await route_service.get_route_stops(
        db=db,
        route_id=route_id,
        school_id=school_id,
        branch_id=branch_id,
        trip_type=trip_type,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )

@router.post(
    "/routes/{route_id}/stops",
    response_model=RouteStopResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add stop to route",
    description=(
        "Add a stop to a route at a given sequence position for a trip_type. "
        "BRANCH_ADMIN or above required."
    ),
)
async def add_stop_to_route(
    route_id : int,
    payload  : RouteStopCreate,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = RouteAdminRequired,
) -> RouteStopResponse:
    return await route_service.add_stop_to_route(
        db=db,
        route_id=route_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.patch(
    "/routes/{route_id}/stops/{route_stop_id}",
    response_model=RouteStopResponse,
    status_code=status.HTTP_200_OK,
    summary="Update route stop",
    description=(
        "Update a stop's sequence or estimated_time within a route. "
        "To change the stop itself, remove and re-add. "
        "BRANCH_ADMIN or above required."
    ),
)
async def update_route_stop(
    route_id     : int,
    route_stop_id: int,
    payload      : RouteStopUpdate,
    school_id    : int = Query(...),
    branch_id    : int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = RouteAdminRequired,
) -> RouteStopResponse:
    return await route_service.update_route_stop(
        db=db,
        route_stop_id=route_stop_id,
        route_id=route_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.delete(
    "/routes/{route_id}/stops/{route_stop_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove stop from route",
    description=(
        "Remove a stop from a route. This hard-deletes the route_stop record — "
        "the stop itself is not deleted. BRANCH_ADMIN or above required."
    ),
)
async def remove_stop_from_route(
    route_id     : int,
    route_stop_id: int,
    school_id    : int = Query(...),
    branch_id    : int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = RouteAdminRequired,
) -> None:
    await route_service.remove_stop_from_route(
        db=db,
        route_stop_id=route_stop_id,
        route_id=route_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )
