from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import NotificationChannel, NotificationStatus, NotificationType
from app.core.schemas import PaginatedResponse

SchoolBranchField = Annotated[int, Field(gt=0, description="Must be a positive integer.")]


# =============================================================================
# Request Schemas
# =============================================================================

class NotificationCreate(BaseModel):
    """
    Payload for POST /notifications/ (admin-only, GENERAL type).
    Used to manually send a notification to a specific user.
    event_key is optional — omit for non-deduplicated messages.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    school_id : SchoolBranchField
    branch_id : int | None              = Field(default=None, gt=0)
    user_id   : int                     = Field(gt=0)
    student_id: int | None              = Field(default=None, gt=0)
    trip_id   : int | None              = Field(default=None, gt=0)
    title     : str                     = Field(min_length=1, max_length=255)
    message   : str                     = Field(min_length=1)
    channel   : NotificationChannel | None = None
    event_key : str | None              = Field(default=None, max_length=255)


class NotificationStatusUpdate(BaseModel):
    """
    Payload for PATCH /notifications/{notification_id}/status.
    Only SENT → READ transition is user-facing.
    PENDING → SENT/FAILED is handled internally by dispatch service.
    """
    notification_status: NotificationStatus


# =============================================================================
# Response Schemas
# =============================================================================

class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notification_id    : int
    school_id          : int
    branch_id          : int | None
    user_id            : int
    student_id         : int | None
    trip_id            : int | None
    title              : str
    message            : str
    notification_type  : str
    notification_status: str
    event_key          : str | None
    channel            : str | None
    sent_at            : datetime


# =============================================================================
# Paginated
# =============================================================================
PaginatedNotificationResponse = PaginatedResponse[NotificationResponse]