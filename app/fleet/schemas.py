# app/fleet/schemas.py

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.schemas import PaginatedResponse, TenantResponse

SchoolBranchField = Annotated[int, Field(gt=0, description="Must be a positive integer.")]


class BusCreate(BaseModel):
    """
    school_id is intentionally absent — it comes from the URL path param only.
    Putting school_id in the body would allow a caller to mismatch the URL school
    with a different school in the payload.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    school_id : SchoolBranchField
    branch_id : SchoolBranchField
    bus_number: str = Field(min_length=1, max_length=20)
    capacity  : int = Field(gt=0, description="Seating capacity — must be greater than 0.")


class BusUpdate(BaseModel):
    """Use exclude_unset=True in service."""
    model_config = ConfigDict(str_strip_whitespace=True)

    bus_number: str | None = Field(default=None, min_length=1, max_length=20)
    capacity  : int | None = Field(default=None, gt=0)
    is_active : bool | None = None
    # branch_id — allowed for SCHOOL_ADMIN and SUPER_ADMIN to move a bus
    # between branches. BRANCH_ADMIN attempting to change branch_id is
    # rejected in the service layer via has_branch_access.
    branch_id : int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "BusUpdate":
        if all(v is None for v in [self.bus_number, self.capacity, self.is_active, self.branch_id]):
            raise ValueError("At least one field must be provided for update.")
        return self


class BusResponse(TenantResponse):
    """
    Inherits school_id, school_name, branch_id, branch_name from TenantResponse.
    school_name and branch_name are populated via @property on the Bus ORM model
    which flattens bus.school.school_name and bus.branch.branch_name.
    Requires selectinload(Bus.school) + selectinload(Bus.branch) in repo queries.
    """
    bus_id    : int
    bus_number: str
    capacity  : int
    is_active : bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


PaginatedBusResponse = PaginatedResponse[BusResponse]