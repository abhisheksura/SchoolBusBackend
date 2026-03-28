from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import AttendanceStatus, TripType
from app.core.schemas import PaginatedResponse


# =============================================================================
# Shared
# =============================================================================
SchoolBranchField = Annotated[int, Field(gt=0, description="Must be a positive integer.")]


# =============================================================================
# StudentRouteAssignment Schemas
# =============================================================================

class StudentRouteAssignmentCreate(BaseModel):
    """
    Payload for POST /assignments/.
    Assigns a student to a route + boarding stop for a trip_type.
    A separate assignment is required for PICKUP and DROPOFF.
    school_id and branch_id must match the student, route, and stop.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    school_id      : SchoolBranchField
    branch_id      : SchoolBranchField
    student_id     : int     = Field(gt=0)
    route_id       : int     = Field(gt=0)
    stop_id        : int     = Field(gt=0)
    assignment_type: TripType


class StudentRouteAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assignment_id  : int
    school_id      : int
    branch_id      : int
    student_id     : int
    route_id       : int
    stop_id        : int
    assignment_type: str
    is_active      : bool
    assigned_at    : datetime
    updated_at     : datetime


# =============================================================================
# StudentAttendance Schemas
# =============================================================================

class AttendanceMarkRequest(BaseModel):
    """
    Payload for POST /assignments/trips/{trip_id}/attendance.
    Marks attendance for a student on an IN_PROGRESS trip.
    Called by the driver app during an active trip.
    marked_by_driver_id is optional — driver may mark on behalf of another.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    student_id         : int              = Field(gt=0)
    assignment_type    : TripType
    attendance_status  : AttendanceStatus
    stop_id            : int | None       = Field(default=None, gt=0)
    marked_by_driver_id: int | None       = Field(default=None, gt=0)


class AttendanceUpdateRequest(BaseModel):
    """
    Payload for PATCH /assignments/trips/{trip_id}/attendance/{attendance_id}.
    Corrects an existing attendance record. Only status can be changed.
    BRANCH_ADMIN or above required.
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


# =============================================================================
# Paginated Response Schemas
# =============================================================================
PaginatedAssignmentResponse = PaginatedResponse[StudentRouteAssignmentResponse]
PaginatedAttendanceResponse = PaginatedResponse[AttendanceResponse]