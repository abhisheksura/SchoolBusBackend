from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.schemas import PaginatedResponse

SchoolBranchField = Annotated[int, Field(gt=0, description="Must be a positive integer.")]


class BusCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    school_id : SchoolBranchField
    branch_id : SchoolBranchField
    bus_number: str = Field(min_length=1, max_length=50)
    capacity  : int = Field(gt=0, description="Seating capacity — must be greater than 0.")


class BusUpdate(BaseModel):
    """Use exclude_unset=True in service."""
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


PaginatedBusResponse = PaginatedResponse[BusResponse]