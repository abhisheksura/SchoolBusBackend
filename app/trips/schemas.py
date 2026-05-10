from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import TripStatus, TripType
from app.core.schemas import PaginatedResponse


# =============================================================================
# Shared
# =============================================================================
SchoolBranchField = Annotated[int, Field(gt=0, description="Must be a positive integer.")]


# =============================================================================
# Trip Schemas
# =============================================================================

class TripCreate(BaseModel):
    """
    Payload for POST /trips/trips/.
    bus_id and driver_id are optional at creation — can be assigned later
    via PATCH /trips/{trip_id}/assign.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    school_id   : SchoolBranchField
    branch_id   : SchoolBranchField
    route_id    : int        = Field(gt=0)
    service_date: date
    trip_type   : TripType
    bus_id      : int | None = Field(default=None, gt=0)
    driver_id   : int | None = Field(default=None, gt=0)


class TripAssignAssets(BaseModel):
    """
    Payload for PATCH /trips/{trip_id}/assign.
    Assigns or reassigns bus/driver to a SCHEDULED trip.
    At least one of bus_id or driver_id must be provided.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    bus_id   : int | None = Field(default=None, gt=0)
    driver_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def at_least_one(self) -> "TripAssignAssets":
        if self.bus_id is None and self.driver_id is None:
            raise ValueError("At least one of bus_id or driver_id must be provided.")
        return self


class TripUpdateStatus(BaseModel):
    """
    Payload for PATCH /trips/{trip_id}/status.
    Transitions enforced in service via TRIP_STATUS_TRANSITIONS:
        SCHEDULED   → IN_PROGRESS | CANCELLED
        IN_PROGRESS → COMPLETED | CANCELLED
    COMPLETED and CANCELLED are terminal states.
    """
    trip_status: TripStatus


class TripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trip_id          : int
    school_id        : int
    branch_id        : int
    route_id         : int
    bus_id           : int | None
    driver_id        : int | None
    service_date     : date
    trip_type        : str
    trip_status      : str
    actual_start_time: datetime | None
    actual_end_time  : datetime | None
    created_at       : datetime
    updated_at       : datetime


# =============================================================================
# TripLiveStatus Schemas
# =============================================================================

class TripLiveStatusUpsert(BaseModel):
    """
    Payload for PUT /trips/{trip_id}/live-status.
    Upsert — creates if not exists, updates if exists.
    Only valid when trip is IN_PROGRESS.
    Called by GPS device ingestion or driver app.
    heading: 0–360 degrees, 0 = North.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    current_latitude      : float           = Field(ge=-90.0,  le=90.0)
    current_longitude     : float           = Field(ge=-180.0, le=180.0)
    speed                 : float | None    = Field(default=None, ge=0.0)
    heading               : float | None    = Field(default=None, ge=0.0, le=360.0)
    last_stop_id          : int | None      = Field(default=None, gt=0)
    last_stop_arrival_time: datetime | None = None


class TripLiveStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    live_status_id        : int
    trip_id               : int
    school_id             : int
    branch_id             : int
    current_latitude      : float
    current_longitude     : float
    speed                 : float | None
    heading               : float | None
    last_stop_id          : int | None
    last_stop_arrival_time: datetime | None
    last_updated          : datetime


# =============================================================================
# Paginated Response Schemas
# =============================================================================
PaginatedTripResponse = PaginatedResponse[TripResponse]

# =============================================================================
# Driver-specific Schemas
# =============================================================================
 
class TodaysTripResponse(BaseModel):
    """
    Enriched trip summary for the driver's today view.
    Identical to TripResponse but named distinctly for OpenAPI clarity —
    makes it obvious in the docs that this is the driver-facing endpoint.
    Future enrichment (e.g. route_name, stop_count) can be added here
    without changing the admin-facing TripResponse.
    """
    model_config = ConfigDict(from_attributes=True)
 
    trip_id          : int
    school_id        : int
    branch_id        : int
    route_id         : int
    bus_id           : int | None
    driver_id        : int | None
    service_date     : date
    trip_type        : str
    trip_status      : str
    actual_start_time: datetime | None
    actual_end_time  : datetime | None
    created_at       : datetime
    updated_at       : datetime