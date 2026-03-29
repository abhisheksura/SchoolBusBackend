from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.fleet import service as fleet_service
from app.fleet.schemas import BusCreate, BusResponse, BusUpdate, PaginatedBusResponse
from app.core.config import settings
from app.core.db import get_db
from app.core.enums import RoleName
from app.api.v1.dependencies import AnyAuthenticated, CurrentUser, require_roles

router = APIRouter()

BusAdminRequired = Depends(
    require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN)
)


@router.post(
    "/buses/",
    response_model=BusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create bus",
    description="Create a new bus. BRANCH_ADMIN or above required.",
)
async def create_bus(
    payload: BusCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = BusAdminRequired,
) -> BusResponse:
    return await fleet_service.create_bus(db=db, payload=payload)


@router.get(
    "/buses/",
    response_model=PaginatedBusResponse,
    status_code=status.HTTP_200_OK,
    summary="List buses",
    description="Fetch paginated buses filtered by caller's branch scope.",
)
async def get_all_buses(
    school_id  : int  = Query(...),
    branch_id  : int  = Query(...),
    page       : int  = Query(default=1, ge=1),
    page_size  : int  = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedBusResponse:
    if not current_user.has_any_role(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN):
        active_only = True
    return await fleet_service.get_all_buses(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
        active_only=active_only,
    )


@router.get(
    "/buses/{bus_id}",
    response_model=BusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get bus",
    description="Fetch a single bus. Returns 404 if outside caller's scope.",
)
async def get_bus(
    bus_id   : int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> BusResponse:
    return await fleet_service.get_bus(
        db=db, bus_id=bus_id, school_id=school_id, branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.patch(
    "/buses/{bus_id}",
    response_model=BusResponse,
    status_code=status.HTTP_200_OK,
    summary="Update bus",
    description="Partially update a bus. BRANCH_ADMIN or above required.",
)
async def update_bus(
    bus_id   : int,
    payload  : BusUpdate,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = BusAdminRequired,
) -> BusResponse:
    return await fleet_service.update_bus(
        db=db, bus_id=bus_id, school_id=school_id, branch_id=branch_id, payload=payload,
    )


@router.delete(
    "/buses/{bus_id}",
    response_model=BusResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate bus",
    description="Soft-delete a bus. BRANCH_ADMIN or above required.",
)
async def deactivate_bus(
    bus_id   : int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = BusAdminRequired,
) -> BusResponse:
    return await fleet_service.deactivate_bus(
        db=db, bus_id=bus_id, school_id=school_id, branch_id=branch_id,
    )