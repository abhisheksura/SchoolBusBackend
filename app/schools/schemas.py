from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.schemas import PaginatedResponse


# =============================================================================
# Shared Field Definitions
# =============================================================================
SchoolNameField = Annotated[
    str,
    Field(
        min_length=3,
        max_length=255,
        description="School name — 3 to 255 characters.",
    ),
]

BranchNameField = Annotated[
    str,
    Field(
        min_length=3,
        max_length=150,
        description="Branch name — 3 to 150 characters.",
    ),
]


# =============================================================================
# School Request Schemas
# =============================================================================

class SchoolCreate(BaseModel):
    """Payload for POST /schools/."""

    model_config = ConfigDict(str_strip_whitespace=True)

    school_name: SchoolNameField


class SchoolUpdate(BaseModel):
    """
    Payload for PATCH /schools/{school_id}.
    At least one field must be provided.

    Important: always use .model_dump(exclude_unset=True) in the service —
    NOT exclude_none=True. This preserves the distinction between:
      - Field not sent by client (unset)   → skip, do not update
      - Field explicitly sent as null/None → update to NULL in DB (clear value)
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    school_name: SchoolNameField | None = None
    is_active  : bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "SchoolUpdate":
        """Ensure at least one field is provided for update."""
        if self.school_name is None and self.is_active is None:
            raise ValueError("At least one field must be provided for update.")
        return self


# =============================================================================
# Branch Request Schemas
# =============================================================================

class BranchCreate(BaseModel):
    """
    Payload for POST /schools/{school_id}/branches/.
    Note: school_id is not included here — it comes from the URL path param,
    not the request body. The router passes it separately to the service.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    branch_name   : BranchNameField
    branch_address: str | None       = Field(default=None, max_length=500)
    branch_phone  : str | None       = Field(default=None, max_length=20)
    branch_email  : EmailStr | None  = Field(default=None, description="Valid email address.")


class BranchUpdate(BaseModel):
    """
    Payload for PATCH /schools/{school_id}/branches/{branch_id}.
    At least one field must be provided.

    Note: school_id and branch_id are not included here — they come from the
    URL path params. Mixing path params into the request body is a design
    smell — the path IS the tenant context.

    Important: always use .model_dump(exclude_unset=True) in the service —
    NOT exclude_none=True. This preserves the distinction between:
      - Field not sent by client (unset)   → skip, do not update
      - Field explicitly sent as null/None → update to NULL in DB (clear value)
      For example: sending {"branch_address": null} should clear the address.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    branch_name   : BranchNameField | None = None
    branch_address: str | None             = Field(default=None, max_length=500)
    branch_phone  : str | None             = Field(default=None, max_length=20)
    branch_email  : EmailStr | None        = Field(default=None, description="Valid email address.")
    is_active     : bool | None            = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "BranchUpdate":
        """Ensure at least one field is provided for update."""
        if all(
            v is None
            for v in [
                self.branch_name,
                self.branch_address,
                self.branch_phone,
                self.branch_email,
                self.is_active,
            ]
        ):
            raise ValueError("At least one field must be provided for update.")
        return self


# =============================================================================
# School Response Schemas
# =============================================================================

class SchoolResponse(BaseModel):
    """Public-safe school representation."""

    model_config = ConfigDict(from_attributes=True)

    school_id  : int
    school_name: str
    is_active  : bool
    created_at : datetime
    updated_at : datetime


class BranchResponse(BaseModel):
    """Public-safe branch representation."""

    model_config = ConfigDict(from_attributes=True)

    branch_id     : int
    school_id     : int
    branch_name   : str
    branch_address: str | None
    branch_phone  : str | None
    branch_email  : str | None
    is_active     : bool
    created_at    : datetime
    updated_at    : datetime


class SchoolDetailResponse(BaseModel):
    """
    Extended school response with full list of branches.

    ⚠️  IMPORTANT — async noload pitfall:
    The School ORM model uses lazy="noload" on the branches relationship.
    This schema will always return an empty branches list UNLESS you use
    selectinload(School.branches) in your repository query.

    Always use: get_school_with_branches_by_school_id() from school_repo
    Never use:  get_school_by_school_id() with this response schema.
    """

    model_config = ConfigDict(from_attributes=True)

    school_id  : int
    school_name: str
    is_active  : bool
    created_at : datetime
    updated_at : datetime
    branches   : list[BranchResponse] = []


# =============================================================================
# Paginated Response Schemas
# =============================================================================

# Concrete paginated types for OpenAPI schema generation.
# FastAPI needs concrete types (not raw generics) for correct docs rendering.
PaginatedSchoolResponse = PaginatedResponse[SchoolResponse]
PaginatedBranchResponse = PaginatedResponse[BranchResponse]