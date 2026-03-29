from datetime import datetime

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TZDateTime
from app.core.enums import NotificationChannel, NotificationStatus, NotificationType


# -----------------------------------------------------------------------------
# NotificationLog
# Maps to: notification_logs table
# Append-only log of all notifications sent to users.
#
# Rules:
#   - NEVER UPDATE or DELETE — immutable records
#   - event_key + user_id = partial unique index to prevent duplicates
#     (enforced via Alembic migration — SQLAlchemy cannot express WHERE clause)
#   - branch_id is nullable — school-level notifications don't need a branch
#   - student_id / trip_id nullable — SET NULL on delete preserves history
#   - user_id ondelete="CASCADE" — no orphan notifications after user deletion
#   - school/branch ondelete="CASCADE" — notifications scoped to tenant
#   - Status lifecycle: PENDING → SENT | FAILED → READ (SENT only)
#
# Partial unique index (add via Alembic migration):
#   CREATE UNIQUE INDEX idx_notifications_user_event
#       ON notification_logs(user_id, event_key)
#       WHERE event_key IS NOT NULL;
# -----------------------------------------------------------------------------
class NotificationLog(Base):
    __tablename__ = "notification_logs"

    notification_id    : Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id          : Mapped[int]             = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="CASCADE"), nullable=False)
    branch_id          : Mapped[int | None]      = mapped_column(Integer, nullable=True)
    user_id            : Mapped[int]             = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    student_id         : Mapped[int | None]      = mapped_column(Integer, nullable=True)
    trip_id            : Mapped[int | None]      = mapped_column(Integer, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=True)
    title              : Mapped[str]             = mapped_column(Text, nullable=False)
    message            : Mapped[str]             = mapped_column(Text, nullable=False)
    notification_type  : Mapped[str]             = mapped_column(String(50), nullable=False)
    notification_status: Mapped[str]             = mapped_column(
        String(20),
        nullable=False,
        default=NotificationStatus.PENDING.value,
        server_default=NotificationStatus.PENDING.value,
    )
    event_key          : Mapped[str | None]      = mapped_column(String(255), nullable=True)
    channel            : Mapped[str | None]      = mapped_column(String(20), nullable=True)
    sent_at            : Mapped[datetime]        = mapped_column(TZDateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        # branch_id nullable — FK only enforced when non-NULL
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="CASCADE",
            name="fk_notification_logs_branch_school",
        ),
        # student_id nullable — SET NULL on student delete preserves log
        ForeignKeyConstraint(
            ["student_id", "branch_id", "school_id"],
            ["students.student_id", "students.branch_id", "students.school_id"],
            name="fk_notification_logs_student",
        ),
        Index("idx_notifications_user", "user_id"),
        Index("idx_notifications_trip", "trip_id"),
        Index("idx_notifications_status", "notification_status"),
        Index("idx_notifications_sent_at", "sent_at"),
        # Partial unique index — must be created in Alembic migration:
        # CREATE UNIQUE INDEX idx_notifications_user_event
        #     ON notification_logs(user_id, event_key)
        #     WHERE event_key IS NOT NULL;
    )

    @property
    def status(self) -> NotificationStatus:
        return NotificationStatus(self.notification_status)

    @property
    def type(self) -> NotificationType:
        return NotificationType(self.notification_type)

    def __repr__(self) -> str:
        return (
            f"<NotificationLog id={self.notification_id} "
            f"user={self.user_id} type={self.notification_type} "
            f"status={self.notification_status}>"
        )