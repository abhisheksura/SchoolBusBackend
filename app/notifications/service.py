from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications import repository as notif_repo
from app.notifications.models import NotificationLog
from app.notifications.repository import NotificationNotFoundError
from app.notifications.schemas import (
    NotificationCreate,
    NotificationResponse,
    NotificationStatusUpdate,
    PaginatedNotificationResponse,
)
from app.core.config import settings
from app.core.enums import (
    NotificationStatus,
    NotificationType,
    NotificationChannel,
)
from app.core.exceptions import DuplicateEntryError, ForbiddenError
from app.core.schemas import paginate, pagination_params

# ---------------------------------------------------------------------------
# Status transition rules for notifications
# PENDING → SENT | FAILED  (handled internally by dispatch service)
# SENT    → READ            (user-facing — mark as read)
# ---------------------------------------------------------------------------
NOTIFICATION_STATUS_TRANSITIONS: dict[NotificationStatus, set[NotificationStatus]] = {
    NotificationStatus.PENDING: {NotificationStatus.SENT, NotificationStatus.FAILED},
    NotificationStatus.SENT:    {NotificationStatus.READ},
    NotificationStatus.FAILED:  set(),   # terminal
    NotificationStatus.READ:    set(),   # terminal
}


# =============================================================================
# User-facing Services
# =============================================================================

async def get_my_notifications(
    db: AsyncSession,
    user_id: int,
    school_id: int,
    page: int,
    page_size: int,
    status_filter: NotificationStatus | None = None,
    type_filter: NotificationType | None = None,
) -> PaginatedNotificationResponse:
    """
    Fetch the authenticated user's own notifications.
    Scoped to user_id — users can only see their own.
    """
    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)
    records, total = await notif_repo.get_notifications_by_user_id(
        db=db,
        user_id=user_id,
        school_id=school_id,
        limit=limit,
        offset=offset,
        status_filter=status_filter,
        type_filter=type_filter,
    )
    return paginate(
        items=[NotificationResponse.model_validate(r) for r in records],
        total=total, page=page, page_size=page_size,
    )


async def get_notification(
    db: AsyncSession,
    notification_id: int,
    requesting_user_id: int,
    is_admin: bool,
) -> NotificationResponse:
    """
    Fetch a single notification.
    Non-admins can only see their own notifications.
    """
    record = await notif_repo.get_notification_by_id(db, notification_id)

    if not is_admin and record.user_id != requesting_user_id:
        raise NotificationNotFoundError(identifier=notification_id)

    return NotificationResponse.model_validate(record)


async def mark_as_read(
    db: AsyncSession,
    notification_id: int,
    requesting_user_id: int,
) -> NotificationResponse:
    """
    Mark a SENT notification as READ.
    Users can only mark their own notifications as read.
    """
    record = await notif_repo.get_notification_by_id(db, notification_id)

    # Ownership check — users can only mark their own
    if record.user_id != requesting_user_id:
        raise NotificationNotFoundError(identifier=notification_id)

    current = NotificationStatus(record.notification_status)
    if NotificationStatus.READ not in NOTIFICATION_STATUS_TRANSITIONS.get(current, set()):
        raise ForbiddenError(
            detail=f"Cannot mark a {current.value} notification as READ."
        )

    updated = await notif_repo.update_notification_status(
        db, notification_id, NotificationStatus.READ
    )
    return NotificationResponse.model_validate(updated)


# =============================================================================
# Admin Services
# =============================================================================

async def get_admin_notifications(
    db: AsyncSession,
    school_id: int,
    page: int,
    page_size: int,
    accessible_school_ids: list[int] | None,
    branch_id: int | None = None,
    status_filter: NotificationStatus | None = None,
    type_filter: NotificationType | None = None,
    user_id: int | None = None,
    trip_id: int | None = None,
) -> PaginatedNotificationResponse:
    """
    Fetch all notifications for a school (admin audit view).
    Scope check BEFORE DB hit.
    """
    if accessible_school_ids is not None and school_id not in accessible_school_ids:
        raise ForbiddenError(detail="You do not have access to this school.")

    limit, offset = pagination_params(page, page_size, settings.MAX_PAGE_SIZE)
    records, total = await notif_repo.get_notifications_by_school(
        db=db,
        school_id=school_id,
        limit=limit,
        offset=offset,
        branch_id=branch_id,
        status_filter=status_filter,
        type_filter=type_filter,
        user_id=user_id,
        trip_id=trip_id,
    )
    return paginate(
        items=[NotificationResponse.model_validate(r) for r in records],
        total=total, page=page, page_size=page_size,
    )


async def create_notification(
    db: AsyncSession,
    payload: NotificationCreate,
    accessible_school_ids: list[int] | None,
) -> NotificationResponse:
    """
    Manually create a GENERAL notification (admin-only).
    Checks event_key uniqueness before inserting.
    Scope check BEFORE DB hit.
    """
    if accessible_school_ids is not None and payload.school_id not in accessible_school_ids:
        raise ForbiddenError(detail="You do not have access to this school.")

    # Duplicate check via event_key if provided
    if payload.event_key:
        existing = await notif_repo.get_notification_by_event_key_or_none(
            db, payload.user_id, payload.event_key
        )
        if existing:
            raise DuplicateEntryError(field="event_key", value=payload.event_key)

    record = await notif_repo.create_notification(
        db=db,
        school_id=payload.school_id,
        branch_id=payload.branch_id,
        user_id=payload.user_id,
        student_id=payload.student_id,
        trip_id=payload.trip_id,
        title=payload.title,
        message=payload.message,
        notification_type=NotificationType.GENERAL,
        channel=payload.channel,
        event_key=payload.event_key,
    )
    return NotificationResponse.model_validate(record)


async def update_notification_status(
    db: AsyncSession,
    notification_id: int,
    payload: NotificationStatusUpdate,
) -> NotificationResponse:
    """
    Internal status update — PENDING → SENT | FAILED.
    Used by the dispatch service, not user-facing.
    BRANCH_ADMIN+ enforced at router.
    """
    record = await notif_repo.get_notification_by_id(db, notification_id)

    current = NotificationStatus(record.notification_status)
    allowed = NOTIFICATION_STATUS_TRANSITIONS.get(current, set())
    if payload.notification_status not in allowed:
        raise ForbiddenError(
            detail=f"Cannot transition notification from {current.value} to {payload.notification_status.value}."
        )

    updated = await notif_repo.update_notification_status(
        db, notification_id, payload.notification_status
    )
    return NotificationResponse.model_validate(updated)


# =============================================================================
# Internal Helper — called by other services (trips, attendance)
# =============================================================================

async def log_notification(
    db: AsyncSession,
    school_id: int,
    user_id: int,
    title: str,
    message: str,
    notification_type: NotificationType,
    branch_id: int | None = None,
    student_id: int | None = None,
    trip_id: int | None = None,
    channel: NotificationChannel | None = None,
    event_key: str | None = None,
) -> NotificationLog | None:
    """
    Internal helper for other services to log a notification.
    Silently skips if event_key already exists for this user (idempotent).
    Returns the created record or None if skipped.
    """
    if event_key:
        existing = await notif_repo.get_notification_by_event_key_or_none(
            db, user_id, event_key
        )
        if existing:
            return None  # Already sent — skip silently

    return await notif_repo.create_notification(
        db=db,
        school_id=school_id,
        branch_id=branch_id,
        user_id=user_id,
        student_id=student_id,
        trip_id=trip_id,
        title=title,
        message=message,
        notification_type=notification_type,
        channel=channel,
        event_key=event_key,
    )