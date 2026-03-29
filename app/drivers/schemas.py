import re
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.schemas import PaginatedResponse


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


class DriverCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    school_id     : SchoolBranchField
    branch_id     : SchoolBranchField
    first_name    : str        = Field(min_length=1, max_length=100)
    last_name     : str | None = Field(default=None, max_length=100)
    phone         : str | None = Field(default=None, max_length=20)
    license_number: str | None = Field(default=None, max_length=100)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone_number(cls, v: str | None) -> str | None:
        return validate_phone(v)


class DriverUpdate(BaseModel):
    """Use exclude_unset=True in service — None means clear the field."""
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


PaginatedDriverResponse = PaginatedResponse[DriverResponse]