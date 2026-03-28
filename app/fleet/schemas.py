from datetime import datetime
from typing import Annotated
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.schemas import PaginatedResponse


# =============================================================================
# Shared Field Definitions
# =============================================================================

# Positive integer for school_id / branch_id — catches 0 and negatives at
# the Pydantic layer before any DB hit, returning a clean 422.
SchoolBranchField = Annotated[int, Field(gt=0, description="Must be a positive integer.")]

# International phone number — allows digits, spaces, hyphens, parentheses,
# leading +. Min 7 chars (shortest valid numbers), max 20.
# Examples: "+91 98765 43210", "(555) 123-4567", "+1-800-555-0199"
PHONE_REGEX = re.compile(r"^\+?[\d\s\-().]{7,20}$")


def validate_phone(v: str | None) -> str | None:
    """Validate phone number format. Returns None if None (optional field)."""
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
# Driver Schemas
# =============================================================================

class DriverCreate(BaseModel):
    """
    Payload for POST /fleet/drivers/.
    school_id and branch_id come from the request body since drivers
    can be created across branches by SUPER_ADMIN / SCHOOL_ADMIN.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    school_id     : SchoolBranchField
    branch_id     : SchoolBranchField
    first_name    : str            = Field(min_length=1, max_length=100)
    last_name     : str | None     = Field(default=None, max_length=100)
    phone         : str | None     = Field(default=None, max_length=20)
    license_number: str | None     = Field(default=None, max_length=100)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone_number(cls, v: str | None) -> str | None:
        return validate_phone(v)


class DriverUpdate(BaseModel):
    """
    Payload for PATCH /fleet/drivers/{driver_id}.
    Use exclude_unset=True in service — None means clear the field.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    first_name    : str | None  = Field(default=None, min_length=1, max_length=100)
    last_name     : str | None  = Field(default=None, max_length=100)
    phone         : str | None  = Field(default=None, max_length=20)
    license_number: str | None  = Field(default=None, max_length=100)
    is_active     : bool | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone_number(cls, v: str | None) -> str | None:
        return validate_phone(v)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "DriverUpdate":
        if all(v is None for v in [self.first_name, self.last_name, self.phone, self.license_number, self.is_active]):
            raise ValueError("At least one field must be provided for update.")
        return self


class DriverResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    driver_id     : int
    user_id       : int | None
    school_id     : int
    branch_id     : int
    first_name    : str
    last_name     : str | None
    phone         : str | None
    license_number: str | None
    is_active     : bool
    created_at    : datetime
    updated_at    : datetime


# =============================================================================
# Bus Schemas
# =============================================================================

class BusCreate(BaseModel):
    """Payload for POST /fleet/buses/."""
    model_config = ConfigDict(str_strip_whitespace=True)

    school_id : SchoolBranchField
    branch_id : SchoolBranchField
    bus_number: str  = Field(min_length=1, max_length=50)
    capacity  : int  = Field(gt=0, description="Seating capacity — must be greater than 0.")


class BusUpdate(BaseModel):
    """
    Payload for PATCH /fleet/buses/{bus_id}.
    Use exclude_unset=True in service.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    bus_number: str | None  = Field(default=None, min_length=1, max_length=50)
    capacity  : int | None  = Field(default=None, gt=0)
    is_active : bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "BusUpdate":
        if all(v is None for v in [self.bus_number, self.capacity, self.is_active]):
            raise ValueError("At least one field must be provided for update.")
        return self


class BusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bus_id    : int
    school_id : int
    branch_id : int
    bus_number: str
    capacity  : int
    is_active : bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# GPS Device Schemas
# =============================================================================

class GPSDeviceCreate(BaseModel):
    """Payload for POST /fleet/devices/."""
    model_config = ConfigDict(str_strip_whitespace=True)

    school_id  : SchoolBranchField
    branch_id  : SchoolBranchField
    device_imei: str = Field(min_length=1, max_length=100, description="Unique IMEI of the GPS device.")


class GPSDeviceUpdate(BaseModel):
    """
    Payload for PATCH /fleet/devices/{device_id}.
    Use exclude_unset=True in service.
    Note: device_imei is not updatable — IMEI is hardware-bound.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    is_active: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "GPSDeviceUpdate":
        if self.is_active is None:
            raise ValueError("At least one field must be provided for update.")
        return self


class GPSDeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_id  : int
    school_id  : int
    branch_id  : int
    device_imei: str
    is_active  : bool
    created_at : datetime
    updated_at : datetime


# =============================================================================
# Bus Device Assignment Schemas
# =============================================================================

class AssignDeviceRequest(BaseModel):
    """
    Payload for POST /fleet/buses/{bus_id}/assign-device.
    school_id and branch_id are NOT included here — they come from
    query params in the route, consistent with the rest of the fleet API.
    The router passes them directly to the service.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    device_id: int = Field(gt=0, description="Primary key of the GPS device to assign.")


class BusDeviceAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bus_device_id: int
    school_id    : int
    branch_id    : int
    bus_id       : int
    device_id    : int
    assigned_at  : datetime
    unassigned_at: datetime | None
    is_active    : bool


# =============================================================================
# Paginated Response Schemas
# =============================================================================
PaginatedDriverResponse = PaginatedResponse[DriverResponse]
PaginatedBusResponse    = PaginatedResponse[BusResponse]
PaginatedDeviceResponse = PaginatedResponse[GPSDeviceResponse]