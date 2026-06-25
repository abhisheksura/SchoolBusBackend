from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.drivers import service as driver_service
from app.drivers.schemas import DriverCreate, DriverResponse, DriverUpdate, PaginatedDriverResponse
from app.core.config import settings
from app.core.db import get_db
from app.core.enums import RoleName
from app.core.schemas import TenantScopeRequest
from app.api.v1.dependencies import AnyAuthenticated, CurrentUser, require_roles

router = APIRouter(prefix = "/drivers")

DriverAdminRequired = Depends(
    require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN)
)


@router.post(
    "/",
    response_model=DriverResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create driver",
    description="Create a new driver. BRANCH_ADMIN or above required.",
)
async def create_driver(
    payload: DriverCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = DriverAdminRequired,
) -> DriverResponse:
    return await driver_service.create_driver(db=db, payload=payload)


@router.get(
    "/",
    response_model=PaginatedDriverResponse,
    status_code=status.HTTP_200_OK,
    summary="List drivers",
    description="Fetch paginated drivers filtered by caller's branch scope.",
)
async def get_all_drivers(
    school_id  : int | None = Query(default=None),
    branch_id  : int | None = Query(default=None),
    page       : int  = Query(default=1, ge=1),
    page_size  : int  = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    active_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedDriverResponse:

    # if not current_user.has_any_role(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN):
    #     active_only = True

    return await driver_service.get_all_drivers(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        active_only=active_only,
    )


@router.get(
    "/{driver_id}",
    response_model=DriverResponse,
    status_code=status.HTTP_200_OK,
    summary="Get driver",
    description="Fetch a single driver. Returns 404 if outside caller's scope.",
)
async def get_driver(
    driver_id: int,
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> DriverResponse:
    return await driver_service.get_driver(
        db=db,
        driver_id=driver_id,
        school_id=school_id,
        branch_id=branch_id,
        accessible_branch_ids=current_user.get_accessible_branch_ids(school_id),
    )


@router.patch(
    "/{driver_id}",
    response_model=DriverResponse,
    status_code=status.HTTP_200_OK,
    summary="Update driver",
    description="Partially update a driver. BRANCH_ADMIN or above required.",
)
async def update_driver(
    driver_id: int,
    payload  : DriverUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = DriverAdminRequired,
) -> DriverResponse:
    return await driver_service.update_driver(
        db=db, driver_id=driver_id, payload=payload,
        current_user=current_user
    )


@router.patch(
    "/{driver_id}/deactivate",
    response_model=DriverResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate driver",
    description="Soft-delete a driver. BRANCH_ADMIN or above required.",
)
async def deactivate_driver(
    driver_id: int,
    scope: TenantScopeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = DriverAdminRequired,
) -> DriverResponse:
    return await driver_service.deactivate_driver(
        db=db, driver_id=driver_id, school_id=scope.school_id, branch_id=scope.branch_id,
    )

@router.patch(
    "/{driver_id}/reactivate",
    response_model=DriverResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate driver",
    description="Activate a driver. BRANCH_ADMIN or above required.",
)
async def reactivate_driver(
    driver_id: int,
    scope: TenantScopeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = DriverAdminRequired,
) -> DriverResponse:
    return await driver_service.reactivate_driver(
        db=db, driver_id=driver_id, school_id=scope.school_id, branch_id=scope.branch_id,
    )