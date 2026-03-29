from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import AttendanceStatus, TripType
from app.core.schemas import PaginatedResponse

SchoolBranchField = Annotated[int, Field(gt=0, description="Must be a positive integer.")]


class AttendanceMarkRequest(BaseModel):
    """
    Payload for POST /attendance/trips/{trip_id}.
    Marks attendance for a student on an IN_PROGRESS trip.
    Called by driver app during an active trip.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    student_id         : int              = Field(gt=0)
    assignment_type    : TripType
    attendance_status  : AttendanceStatus
    stop_id            : int | None       = Field(default=None, gt=0)
    marked_by_driver_id: int | None       = Field(default=None, gt=0)


class AttendanceUpdateRequest(BaseModel):
    """
    Payload for PATCH /attendance/trips/{trip_id}/{attendance_id}.
    Only status can be corrected. BRANCH_ADMIN or above required.
    """
    attendance_status: AttendanceStatus


class AttendanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attendance_id      : int
    school_id          : int
    branch_id          : int
    student_id         : int
    trip_id            : int
    assignment_type    : str
    attendance_status  : str
    stop_id            : int | None
    marked_at          : datetime
    marked_by_driver_id: int | None


PaginatedAttendanceResponse = PaginatedResponse[AttendanceResponse]