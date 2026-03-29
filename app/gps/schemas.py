from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.schemas import PaginatedResponse


SchoolBranchField = Annotated[int, Field(gt=0, description="Must be a positive integer.")]


# =============================================================================
# GPSDevice Schemas
# =============================================================================

class GPSDeviceCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    school_id  : SchoolBranchField
    branch_id  : SchoolBranchField
    device_imei: str = Field(min_length=1, max_length=100, description="Unique IMEI of the GPS device.")


class GPSDeviceUpdate(BaseModel):
    """
    device_imei is not updatable — IMEI is hardware-bound.
    Use exclude_unset=True in service.
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
# BusDeviceAssignment Schemas
# =============================================================================

class AssignDeviceRequest(BaseModel):
    """
    Payload for POST /gps/devices/{device_id}/assign.
    school_id and branch_id come from query params — consistent with the rest of the API.
    bus_id is the only required body field.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    bus_id: int = Field(gt=0, description="Primary key of the bus to assign this device to.")


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
# Paginated
# =============================================================================
PaginatedGPSDeviceResponse = PaginatedResponse[GPSDeviceResponse]