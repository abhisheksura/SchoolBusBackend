from datetime import datetime, time
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import TripType
from app.core.schemas import PaginatedResponse, TenantResponse


# =============================================================================
# Shared Field Definitions
# =============================================================================
SchoolBranchField = Annotated[int, Field(gt=0, description="Must be a positive integer.")]


# =============================================================================
# Route Schemas
# =============================================================================

class RouteCreate(BaseModel):
    """Payload for POST /routes/routes/."""
    model_config = ConfigDict(str_strip_whitespace=True)

    school_id  : SchoolBranchField
    branch_id  : SchoolBranchField
    route_code : str            = Field(min_length=1, max_length=50, description="Unique code for this route within the branch.")
    route_name : str            = Field(min_length=1, max_length=100)
    description: str | None    = Field(default=None, max_length=500)


class RouteUpdate(BaseModel):
    """
    Payload for PATCH /routes/routes/{route_id}.
    Use exclude_unset=True in service.
    At least one field must be provided.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    route_code : str | None  = Field(default=None, min_length=1, max_length=50)
    route_name : str | None  = Field(default=None, min_length=1, max_length=100)
    description: str | None  = Field(default=None, max_length=500)
    is_active  : bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "RouteUpdate":
        if all(v is None for v in [self.route_code, self.route_name, self.description, self.is_active]):
            raise ValueError("At least one field must be provided for update.")
        return self


class RouteResponse(TenantResponse):
    model_config = ConfigDict(from_attributes=True)

    route_id   : int
    school_id  : int
    branch_id  : int
    route_code : str
    route_name : str
    description: str | None
    is_active  : bool
    created_at : datetime
    updated_at : datetime


class RouteDetailResponse(BaseModel):
    """
    Extended route response with ordered stop lists per trip_type.

    ⚠️  IMPORTANT — async noload pitfall:
    Route uses lazy="noload" on the route_stops relationship.
    Always use get_route_with_stops_by_route_id() from route_repo,
    never get_route_by_route_id() with this response schema.
    """
    model_config = ConfigDict(from_attributes=True)

    route_id   : int
    school_id  : int
    branch_id  : int
    route_code : str
    route_name : str
    description: str | None
    is_active  : bool
    created_at : datetime
    updated_at : datetime
    pickup_stops : list["RouteStopResponse"] = []
    dropoff_stops: list["RouteStopResponse"] = []


# =============================================================================
# Stop Schemas
# =============================================================================

class StopCreate(BaseModel):
    """Payload for POST /routes/stops/."""
    model_config = ConfigDict(str_strip_whitespace=True)

    school_id : SchoolBranchField
    branch_id : SchoolBranchField
    stop_name : str           = Field(min_length=1, max_length=255)
    latitude  : float | None  = Field(default=None, ge=-90.0,  le=90.0)
    longitude : float | None  = Field(default=None, ge=-180.0, le=180.0)

    @model_validator(mode="after")
    def lat_lon_both_or_neither(self) -> "StopCreate":
        """Latitude and longitude must be provided together or not at all."""
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must both be provided or both be omitted.")
        return self


class StopUpdate(BaseModel):
    """
    Payload for PATCH /routes/stops/{stop_id}.
    Use exclude_unset=True in service.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    stop_name : str | None   = Field(default=None, min_length=1, max_length=255)
    latitude  : float | None = Field(default=None, ge=-90.0,  le=90.0)
    longitude : float | None = Field(default=None, ge=-180.0, le=180.0)
    is_active : bool | None  = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "StopUpdate":
        if all(v is None for v in [self.stop_name, self.latitude, self.longitude, self.is_active]):
            raise ValueError("At least one field must be provided for update.")
        return self


class StopResponse(TenantResponse):
    model_config = ConfigDict(from_attributes=True)

    stop_id   : int
    school_id : int
    branch_id : int
    stop_name : str
    latitude  : float | None
    longitude : float | None
    is_active : bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# RouteStop Schemas
# =============================================================================

class RouteStopCreate(BaseModel):
    """
    Payload for POST /routes/routes/{route_id}/stops.
    Adds a stop to a route for a given trip_type at a specific sequence position.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    stop_id       : int      = Field(gt=0)
    trip_type     : TripType
    stop_sequence : int      = Field(gt=0, description="Order of this stop in the route. Must be unique per route + trip_type.")
    estimated_time: str | None = Field(
        default=None,
        pattern=r"^\d{2}:\d{2}$",
        description="Estimated arrival time in HH:MM format (24-hour).",
    )


class RouteStopUpdate(BaseModel):
    """
    Payload for PATCH /routes/routes/{route_id}/stops/{route_stop_id}.
    Only sequence and estimated_time can be updated — stop_id and trip_type
    are fixed after creation. To change a stop, remove and re-add.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    stop_sequence : int | None = Field(default=None, gt=0)
    estimated_time: str | None = Field(
        default=None,
        pattern=r"^\d{2}:\d{2}$",
        description="Estimated arrival time in HH:MM format (24-hour).",
    )

    @model_validator(mode="after")
    def at_least_one_field(self) -> "RouteStopUpdate":
        if all(v is None for v in [self.stop_sequence, self.estimated_time]):
            raise ValueError("At least one field must be provided for update.")
        return self


class RouteStopResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    route_stop_id : int
    route_id      : int
    stop_id       : int
    stop_name     : str
    school_id     : int
    branch_id     : int
    trip_type     : TripType
    stop_sequence : int
    estimated_time: time | None
    created_at    : datetime
    updated_at    : datetime


# =============================================================================
# Paginated Response Schemas
# =============================================================================
PaginatedRouteResponse = PaginatedResponse[RouteResponse]
PaginatedStopResponse  = PaginatedResponse[StopResponse]