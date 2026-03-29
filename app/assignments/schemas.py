from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import TripType
from app.core.schemas import PaginatedResponse

SchoolBranchField = Annotated[int, Field(gt=0, description="Must be a positive integer.")]


class StudentRouteAssignmentCreate(BaseModel):
    """
    Payload for POST /assignments/.
    Assigns a student to a route + boarding stop for a trip_type.
    A separate assignment is required for PICKUP and DROPOFF.
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


PaginatedAssignmentResponse = PaginatedResponse[StudentRouteAssignmentResponse]