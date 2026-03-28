import re
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.enums import LeaveRequestStatus, LEAVE_STATUS_TRANSITIONS
from app.core.schemas import PaginatedResponse


# =============================================================================
# Shared Field Definitions
# =============================================================================
SchoolBranchField = Annotated[int, Field(gt=0, description="Must be a positive integer.")]

PHONE_REGEX = re.compile(r"^\+?[\d\s\-().]{7,20}$")


def validate_phone(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip()
    if not PHONE_REGEX.match(v):
        raise ValueError(
            "Phone must be 7–20 characters and may only contain digits, "
            "spaces, hyphens, parentheses, and a leading +."
        )
    return v


# =============================================================================
# Student Schemas
# =============================================================================

class StudentCreate(BaseModel):
    """Payload for POST /students/students/."""
    model_config = ConfigDict(str_strip_whitespace=True)

    school_id       : SchoolBranchField
    branch_id       : SchoolBranchField
    user_id         : int            = Field(gt=0, description="user_id of the student's login account.")
    first_name      : str            = Field(min_length=1, max_length=100)
    last_name       : str | None     = Field(default=None, max_length=100)
    admission_number: str | None     = Field(default=None, max_length=50)
    grade           : str | None     = Field(default=None, max_length=20)
    section         : str | None     = Field(default=None, max_length=10)


class StudentUpdate(BaseModel):
    """
    Payload for PATCH /students/students/{student_id}.
    Use exclude_unset=True in service.
    user_id, school_id, branch_id are not updatable.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    first_name      : str | None  = Field(default=None, min_length=1, max_length=100)
    last_name       : str | None  = Field(default=None, max_length=100)
    admission_number: str | None  = Field(default=None, max_length=50)
    grade           : str | None  = Field(default=None, max_length=20)
    section         : str | None  = Field(default=None, max_length=10)
    is_active       : bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "StudentUpdate":
        if all(v is None for v in [
            self.first_name, self.last_name, self.admission_number,
            self.grade, self.section, self.is_active,
        ]):
            raise ValueError("At least one field must be provided for update.")
        return self


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id      : int
    school_id       : int
    branch_id       : int
    user_id         : int
    first_name      : str
    last_name       : str | None
    admission_number: str | None
    grade           : str | None
    section         : str | None
    is_active       : bool
    created_at      : datetime
    updated_at      : datetime


# =============================================================================
# Parent Schemas
# =============================================================================

class ParentCreate(BaseModel):
    """Payload for POST /students/parents/."""
    model_config = ConfigDict(str_strip_whitespace=True)

    school_id      : SchoolBranchField
    user_id        : int            = Field(gt=0, description="user_id of the parent's login account.")
    first_name     : str            = Field(min_length=1, max_length=100)
    last_name      : str | None     = Field(default=None, max_length=100)
    phone          : str | None     = Field(default=None, max_length=20)
    alternate_phone: str | None     = Field(default=None, max_length=20)
    email          : EmailStr | None = None
    address        : str | None     = Field(default=None, max_length=500)

    @field_validator("phone", "alternate_phone", mode="before")
    @classmethod
    def validate_phone_numbers(cls, v: str | None) -> str | None:
        return validate_phone(v)


class ParentUpdate(BaseModel):
    """
    Payload for PATCH /students/parents/{parent_id}.
    Use exclude_unset=True in service.
    user_id and school_id are not updatable.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    first_name     : str | None      = Field(default=None, min_length=1, max_length=100)
    last_name      : str | None      = Field(default=None, max_length=100)
    phone          : str | None      = Field(default=None, max_length=20)
    alternate_phone: str | None      = Field(default=None, max_length=20)
    email          : EmailStr | None = None
    address        : str | None      = Field(default=None, max_length=500)
    is_active      : bool | None     = None

    @field_validator("phone", "alternate_phone", mode="before")
    @classmethod
    def validate_phone_numbers(cls, v: str | None) -> str | None:
        return validate_phone(v)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "ParentUpdate":
        if all(v is None for v in [
            self.first_name, self.last_name, self.phone,
            self.alternate_phone, self.email, self.address, self.is_active,
        ]):
            raise ValueError("At least one field must be provided for update.")
        return self


class ParentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    parent_id      : int
    user_id        : int
    school_id      : int
    first_name     : str
    last_name      : str | None
    phone          : str | None
    alternate_phone: str | None
    email          : str | None
    address        : str | None
    is_active      : bool
    created_at     : datetime
    updated_at     : datetime


# =============================================================================
# StudentParent Schemas
# =============================================================================

class StudentParentCreate(BaseModel):
    """Payload for POST /students/students/{student_id}/parents."""
    model_config = ConfigDict(str_strip_whitespace=True)

    parent_id   : int  = Field(gt=0)
    relationship: str  = Field(min_length=1, max_length=50, description="e.g. FATHER, MOTHER, GUARDIAN")
    is_primary  : bool = Field(default=False)


class StudentParentUpdate(BaseModel):
    """Payload for PATCH /students/students/{student_id}/parents/{student_parent_id}."""
    model_config = ConfigDict(str_strip_whitespace=True)

    relationship: str | None  = Field(default=None, min_length=1, max_length=50)
    is_primary  : bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "StudentParentUpdate":
        if all(v is None for v in [self.relationship, self.is_primary]):
            raise ValueError("At least one field must be provided for update.")
        return self


class StudentParentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_parent_id: int
    student_id       : int
    parent_id        : int
    relationship     : str
    is_primary       : bool
    created_at       : datetime
    updated_at       : datetime


# =============================================================================
# StudentLeaveRequest Schemas
# =============================================================================

class LeaveRequestCreate(BaseModel):
    """Payload for POST /students/students/{student_id}/leave-requests."""
    model_config = ConfigDict(str_strip_whitespace=True)

    start_date: date
    end_date  : date
    reason    : str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def end_after_start(self) -> "LeaveRequestCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        return self


class LeaveRequestUpdateStatus(BaseModel):
    """
    Payload for PATCH /students/students/{student_id}/leave-requests/{leave_id}.
    Only status can be updated — reason and dates are immutable after creation.
    Valid transitions: PENDING → APPROVED | REJECTED
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    status: LeaveRequestStatus

    @model_validator(mode="after")
    def valid_transition(self) -> "LeaveRequestUpdateStatus":
        # Full transition validation happens in service with current status.
        # This validator is a lightweight pre-check — service does the real check.
        return self


class LeaveRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    leave_id    : int
    school_id   : int
    branch_id   : int
    student_id  : int
    requested_by: int | None
    start_date  : date
    end_date    : date
    reason      : str | None
    status      : str
    created_at  : datetime


# =============================================================================
# Paginated Response Schemas
# =============================================================================
PaginatedStudentResponse      = PaginatedResponse[StudentResponse]
PaginatedParentResponse       = PaginatedResponse[ParentResponse]
PaginatedLeaveRequestResponse = PaginatedResponse[LeaveRequestResponse]