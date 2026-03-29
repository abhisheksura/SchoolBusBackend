from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.models import NotificationLog
from app.core.enums import NotificationChannel, NotificationStatus, NotificationType
from app.core.exceptions import NotFoundError


# Custom exception for this domain
class NotificationNotFoundError(NotFoundError):
    def __init__(self, identifier=None):
        super().__init__(resource="Notification", identifier=identifier)


# =============================================================================
# NotificationLog Queries
# =============================================================================

async def get_notification_by_id(
    db: AsyncSession,
    notification_id: int,
) -> NotificationLog:
    """Fetch a single notification. Raises NotificationNotFoundError if not found."""
    result = await db.execute(
        select(NotificationLog).where(
            NotificationLog.notification_id == notification_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise NotificationNotFoundError(identifier=notification_id)
    return record


async def get_notifications_by_user_id(
    db: AsyncSession,
    user_id: int,
    school_id: int,
    limit: int,
    offset: int,
    status_filter: NotificationStatus | None = None,
    type_filter: NotificationType | None = None,
) -> tuple[list[NotificationLog], int]:
    """
    Fetch all notifications for a specific user.
    Used for the user's own notification inbox.
    """
    query = select(NotificationLog).where(
        NotificationLog.user_id == user_id,
        NotificationLog.school_id == school_id,
    )
    if status_filter:
        query = query.where(NotificationLog.notification_status == status_filter.value)
    if type_filter:
        query = query.where(NotificationLog.notification_type == type_filter.value)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(NotificationLog.sent_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def get_notifications_by_school(
    db: AsyncSession,
    school_id: int,
    limit: int,
    offset: int,
    branch_id: int | None = None,
    status_filter: NotificationStatus | None = None,
    type_filter: NotificationType | None = None,
    user_id: int | None = None,
    trip_id: int | None = None,
) -> tuple[list[NotificationLog], int]:
    """
    Fetch notifications scoped to a school with optional filters.
    Used by admins to audit notifications.
    """
    query = select(NotificationLog).where(
        NotificationLog.school_id == school_id,
    )
    if branch_id:
        query = query.where(NotificationLog.branch_id == branch_id)
    if status_filter:
        query = query.where(NotificationLog.notification_status == status_filter.value)
    if type_filter:
        query = query.where(NotificationLog.notification_type == type_filter.value)
    if user_id:
        query = query.where(NotificationLog.user_id == user_id)
    if trip_id:
        query = query.where(NotificationLog.trip_id == trip_id)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(NotificationLog.sent_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def get_notification_by_event_key_or_none(
    db: AsyncSession,
    user_id: int,
    event_key: str,
) -> NotificationLog | None:
    """
    Check if a notification with this event_key already exists for this user.
    Used to prevent duplicate notifications before insert.
    The DB partial unique index is the final guard.
    """
    result = await db.execute(
        select(NotificationLog).where(
            NotificationLog.user_id == user_id,
            NotificationLog.event_key == event_key,
        )
    )
    return result.scalar_one_or_none()


async def create_notification(
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
) -> NotificationLog:
    """
    Insert a new notification log record.
    Append-only — never UPDATE or DELETE after creation.
    Caller must check event_key uniqueness before calling.
    """
    record = NotificationLog(
        school_id=school_id,
        branch_id=branch_id,
        user_id=user_id,
        student_id=student_id,
        trip_id=trip_id,
        title=title,
        message=message,
        notification_type=notification_type.value,
        channel=channel.value if channel else None,
        event_key=event_key,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def update_notification_status(
    db: AsyncSession,
    notification_id: int,
    new_status: NotificationStatus,
) -> NotificationLog:
    """
    Update the status of a notification.
    Uses RETURNING — single round-trip.
    Caller must validate the transition before calling.
    """
    result = await db.execute(
        update(NotificationLog)
        .where(NotificationLog.notification_id == notification_id)
        .values(notification_status=new_status.value)
        .returning(NotificationLog)
    )
    await db.flush()
    record = result.scalar_one_or_none()
    if not record:
        raise NotificationNotFoundError(identifier=notification_id)
    return record