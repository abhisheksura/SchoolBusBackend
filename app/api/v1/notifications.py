from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications import service as notif_service
from app.notifications.schemas import (
    NotificationCreate,
    NotificationResponse,
    NotificationStatusUpdate,
    PaginatedNotificationResponse,
)
from app.core.config import settings
from app.core.db import get_db
from app.core.enums import NotificationStatus, NotificationType, RoleName
from app.api.v1.dependencies import AnyAuthenticated, CurrentUser, require_roles

router = APIRouter(prefix = "/notifications")

NotifAdminRequired = Depends(
    require_roles(RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN)
)


# =============================================================================
# User-facing Routes — caller's own notifications
# =============================================================================

@router.get(
    "/",
    response_model=PaginatedNotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get my notifications",
    description=(
        "Fetch the authenticated user's own notifications. "
        "Optionally filter by status or type."
    ),
)
async def get_my_notifications(
    school_id    : int                       = Query(...),
    page         : int                       = Query(default=1, ge=1),
    page_size    : int                       = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    status_filter: NotificationStatus | None = Query(default=None, description="Filter by notification status."),
    type_filter  : NotificationType | None   = Query(default=None, description="Filter by notification type."),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedNotificationResponse:
    return await notif_service.get_my_notifications(
        db=db,
        user_id=current_user.user_id,
        school_id=school_id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        type_filter=type_filter,
    )


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get notification",
    description=(
        "Fetch a single notification. "
        "Non-admins can only fetch their own. Returns 404 if not found or unauthorized."
    ),
)
async def get_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> NotificationResponse:
    is_admin = current_user.has_any_role(
        RoleName.SUPER_ADMIN, RoleName.SCHOOL_ADMIN, RoleName.BRANCH_ADMIN
    )
    return await notif_service.get_notification(
        db=db,
        notification_id=notification_id,
        requesting_user_id=current_user.user_id,
        is_admin=is_admin,
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark notification as read",
    description=(
        "Mark a SENT notification as READ. "
        "Users can only mark their own notifications. "
        "Fails if notification is not in SENT status."
    ),
)
async def mark_as_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = AnyAuthenticated,
) -> NotificationResponse:
    return await notif_service.mark_as_read(
        db=db,
        notification_id=notification_id,
        requesting_user_id=current_user.user_id,
    )


# =============================================================================
# Admin Routes
# =============================================================================

@router.get(
    "/admin/",
    response_model=PaginatedNotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Admin — list notifications",
    description=(
        "Fetch all notifications for a school (audit view). "
        "Optionally filter by branch, status, type, user, or trip. "
        "BRANCH_ADMIN or above required."
    ),
)
async def get_admin_notifications(
    school_id    : int                       = Query(...),
    branch_id    : int | None               = Query(default=None),
    page         : int                       = Query(default=1, ge=1),
    page_size    : int                       = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    status_filter: NotificationStatus | None = Query(default=None),
    type_filter  : NotificationType | None   = Query(default=None),
    user_id      : int | None               = Query(default=None, description="Filter by recipient user."),
    trip_id      : int | None               = Query(default=None, description="Filter by trip."),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = NotifAdminRequired,
) -> PaginatedNotificationResponse:
    return await notif_service.get_admin_notifications(
        db=db,
        school_id=school_id,
        page=page,
        page_size=page_size,
        accessible_school_ids=current_user.get_accessible_school_ids(),
        branch_id=branch_id,
        status_filter=status_filter,
        type_filter=type_filter,
        user_id=user_id,
        trip_id=trip_id,
    )


@router.post(
    "/admin/",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin — create notification",
    description=(
        "Manually create a GENERAL notification for a specific user. "
        "BRANCH_ADMIN or above required. "
        "Use event_key to prevent duplicate sends for the same logical event."
    ),
)
async def create_notification(
    payload: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = NotifAdminRequired,
) -> NotificationResponse:
    return await notif_service.create_notification(
        db=db,
        payload=payload,
        accessible_school_ids=current_user.get_accessible_school_ids(),
    )


@router.patch(
    "/admin/{notification_id}/status",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Admin — update notification status",
    description=(
        "Update notification status (PENDING → SENT | FAILED). "
        "Intended for the internal dispatch service. "
        "BRANCH_ADMIN or above required."
    ),
)
async def update_notification_status(
    notification_id: int,
    payload: NotificationStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = NotifAdminRequired,
) -> NotificationResponse:
    return await notif_service.update_notification_status(
        db=db,
        notification_id=notification_id,
        payload=payload,
    )