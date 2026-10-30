from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import TripType
from app.core.schemas import PaginatedResponse, TenantResponse
from app.students.schemas import StudentSummary

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


class StudentRouteAssignmentResponse(TenantResponse):
    model_config = ConfigDict(from_attributes=True)

    assignment_id  : int
    school_id      : int
    branch_id      : int
    student_id     : int
    student        : StudentSummary
    route_id       : int
    stop_id        : int
    assignment_type: str
    route_name     : str
    stop_name      : str
    is_active      : bool
    assigned_at    : datetime
    updated_at     : datetime

class StudentRouteAssignmentMapper:

    @staticmethod
    def to_response(assignment):
        return StudentRouteAssignmentResponse(
            assignment_id=assignment.assignment_id,
            school_id=assignment.school_id,
            branch_id=assignment.branch_id,
            student_id=assignment.student_id,
            student=StudentSummary.model_validate(assignment.student),
            route_id=assignment.route_id,
            stop_id=assignment.stop_id,
            assignment_type=assignment.assignment_type,
            route_name=assignment.route.route_name,
            stop_name=assignment.stop.stop_name,
            is_active=assignment.is_active,
            assigned_at=assignment.assigned_at,
            updated_at=assignment.updated_at,
        )

PaginatedAssignmentResponse = PaginatedResponse[StudentRouteAssignmentResponse]