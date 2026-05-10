from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.fleet import service as fleet_service
from app.fleet.schemas import BusCreate, BusResponse, BusUpdate, PaginatedBusResponse
from app.core.db import get_db
from app.api.v1.dependencies import (
    CurrentUser,
    AnyAuthenticated,
    SuperAdminRequired,
    BranchAdminRequired,
)

router = APIRouter(tags=["fleet"])


# ---------------------------------------------------------------------------
# Buses
# ---------------------------------------------------------------------------

@router.post(
    "/schools/{school_id}/buses/",
    response_model=BusResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bus(
    school_id: int,
    payload: BusCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = BranchAdminRequired,
) -> BusResponse:
    """
    Create a new bus scoped to the given school.
    BRANCH_ADMIN is allowed — service enforces they can only create within their own branch.
    school_id comes from the URL — BusCreate carries only bus_number, capacity, branch_id.
    """
    return await fleet_service.create_bus(db, school_id, payload, current_user)


@router.get(
    "/buses/",
    response_model=PaginatedBusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_all_buses_global(
    school_id: int | None = Query(default=None),
    branch_id: int | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = SuperAdminRequired,
) -> PaginatedBusResponse:
    """
    SUPER_ADMIN-only global list.
    accessible_branch_ids is always None for SUPER_ADMIN.
    """
    if branch_id is not None and school_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="branch_id requires school_id to be specified.",
        )
    return await fleet_service.get_all_buses(
        db, school_id, branch_id, accessible_branch_ids=None,
        page=page, page_size=page_size, active_only=active_only, search=search,
    )


@router.get(
    "/schools/{school_id}/buses/",
    response_model=PaginatedBusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_all_buses(
    school_id: int,
    branch_id: int | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedBusResponse:
    """
    School-scoped bus list for all authenticated roles.
    has_school_access checked here — rejects cross-school access before hitting the DB.
    """
    if not current_user.has_school_access(school_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this school.",
        )
    accessible_branch_ids = current_user.get_accessible_branch_ids(school_id)
    return await fleet_service.get_all_buses(
        db, school_id, branch_id, accessible_branch_ids,
        page, page_size, active_only, search,
    )


@router.get(
    "/schools/{school_id}/buses/{bus_id}",
    response_model=BusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_bus(
    school_id: int,
    bus_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> BusResponse:
    """Fetch a single bus by id within a school."""
    return await fleet_service.get_bus(db, bus_id, school_id, current_user)


@router.patch(
    "/schools/{school_id}/buses/{bus_id}",
    response_model=BusResponse,
    status_code=status.HTTP_200_OK,
)
async def update_bus(
    school_id: int,
    bus_id: int,
    payload: BusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = BranchAdminRequired,
) -> BusResponse:
    """Partial update on a bus. BRANCH_ADMIN and above."""
    return await fleet_service.update_bus(db, bus_id, school_id, payload, current_user)


@router.delete(
    "/schools/{school_id}/buses/{bus_id}",
    response_model=BusResponse,
    status_code=status.HTTP_200_OK,
)
async def deactivate_bus(
    school_id: int,
    bus_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = BranchAdminRequired,
) -> BusResponse:
    """Soft-delete a bus. BRANCH_ADMIN and above."""
    return await fleet_service.deactivate_bus(db, bus_id, school_id, current_user)