from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.buses import service as bus_service
from app.buses.schemas import BusCreate, BusResponse, BusUpdate, PaginatedBusResponse
from app.core.db import get_db
from app.core.enums import RoleName
from app.core.schemas import TenantScopeRequest
from app.core.scope import validate_scope_access
from app.api.v1.dependencies import (
    CurrentUser,
    AnyAuthenticated,
    SuperAdminRequired,
    BranchAdminRequired,
    require_roles
)

router = APIRouter()

# Convenience alias — BRANCH_ADMIN, SCHOOL_ADMIN, SUPER_ADMIN
BusAdminRequired = Depends(
    require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN)
)


@router.post(
    "/buses/",
    response_model=BusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Bus",
    description="Create a new physical bus stop. BRANCH_ADMIN or above required.",
)
async def create_stop(
    payload: BusCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = BusAdminRequired,
) -> BusResponse:
    return await bus_service.create_bus(db=db, payload=payload)


@router.get(
    "/buses/",
    response_model=PaginatedBusResponse,
    status_code=status.HTTP_200_OK,
    summary="List Buses",
    description="Fetch paginated buses."
)
async def get_all_buses(
    school_id: int  = Query(...),
    branch_id: int  = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = BranchAdminRequired,
) -> PaginatedBusResponse:
    """
    School-scoped bus list for all authenticated roles.
    has_school_access checked here — rejects cross-school access before hitting the DB.
    """
    validate_scope_access(
        current_user=current_user,
        school_id=school_id,
        branch_id=branch_id,
    )
    return await bus_service.get_all_buses(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        active_only=active_only,
    )

@router.patch(
    "/buses/{bus_id}",
    response_model=BusResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Bus",
    description="Partially update a Bus. BRANCH_ADMIN or above required.",
)
async def update_bus(
    bus_id : int,
    payload  : BusUpdate,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = BusAdminRequired,
) -> BusResponse:
    return await bus_service.update_bus(
        db=db,
        bus_id=bus_id,
        school_id=school_id,
        branch_id=branch_id,
        payload=payload,
    )


@router.patch(
    "/buses/{bus_id}/deactivate",
    response_model=BusResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate Bus",
    description="Soft-delete a route by setting is_active=False. BRANCH_ADMIN or above required.",
)
async def deactivate_bus(
    bus_id : int,
    scope: TenantScopeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = BusAdminRequired,
) -> BusResponse:
    return await bus_service.deactivate_bus(
        db=db,
        bus_id=bus_id,
        school_id=scope.school_id,
        branch_id=scope.branch_id,
    )

@router.patch(
    "/buses/{bus_id}/reactivate",
    response_model=BusResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate Bus",
    description="Activate a Bus. BRANCH_ADMIN or above required.",
)
async def reactivate_route(
    bus_id: int,
    scope: TenantScopeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = BusAdminRequired,
) -> BusResponse:
    return await bus_service.reactivate_bus(
        db=db, bus_id=bus_id, school_id=scope.school_id, branch_id=scope.branch_id,
    )
