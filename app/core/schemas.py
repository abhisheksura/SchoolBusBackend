import math
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

SchoolBranchField = Annotated[int, Field(gt=0, description="Must be a positive integer.")]

# -----------------------------------------------------------------------------
# PaginatedResponse
# Generic paginated envelope used by all list endpoints across every domain.
#
# Usage:
#   async def get_all_schools(...) -> PaginatedResponse[SchoolResponse]:
#       items, total = await school_repo.get_all_schools(db, limit, offset)
#       return paginate(items, total, page, page_size)
# -----------------------------------------------------------------------------
class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standard paginated response envelope.
    All list endpoints return this shape — never a raw list.
    """

    model_config = ConfigDict(from_attributes=True)

    items    : list[T]
    total    : int
    page     : int
    page_size: int
    pages    : int


# -----------------------------------------------------------------------------
# TenantResponse
# Shared school + branch context embedded in any domain response that is
# scoped to a branch. Import and inherit from this in domain response schemas
# instead of re-declaring school_id / school_name / branch_id / branch_name
# on every model.
#
# Usage:
#   class BusResponse(TenantResponse):
#       bus_id    : int
#       bus_number: str
#       ...
#
# The response stays flat — all tenant fields appear at the top level alongside
# domain fields. No nested object on the client side.
#
# Backend: requires selectinload(Bus.school) + selectinload(Bus.branch) in the
# repo query, and @property accessors on the ORM model to flatten the names:
#
#   @property
#   def school_name(self) -> str:
#       return self.school.school_name
#
#   @property
#   def branch_name(self) -> str:
#       return self.branch.branch_name
# -----------------------------------------------------------------------------
class TenantResponse(BaseModel):
    """
    Reusable school + branch context.
    Inherit from this in any domain response scoped to a branch.
    """

    model_config = ConfigDict(from_attributes=True)

    school_id  : int
    school_name: str | None = None
    branch_id  : int
    branch_name: str | None = None


class TenantScopeRequest(BaseModel):
    school_id: SchoolBranchField
    branch_id: SchoolBranchField

# -----------------------------------------------------------------------------
# paginate()
# Helper to build a PaginatedResponse from a list of items and a total count.
# -----------------------------------------------------------------------------
def paginate(
    items: list[T],
    total: int,
    page: int,
    page_size: int,
) -> PaginatedResponse[T]:
    """
    Build a PaginatedResponse from raw query results.

    Args:
        items     : list of ORM instances or Pydantic models for the current page
        total     : total count of matching records across all pages
        page      : current page number (1-indexed)
        page_size : number of items per page

    Returns:
        PaginatedResponse with calculated pages count
    """
    pages = math.ceil(total / page_size) if page_size > 0 else 0
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# -----------------------------------------------------------------------------
# pagination_params()
# Helper to convert page + page_size into limit + offset for DB queries.
# -----------------------------------------------------------------------------
def pagination_params(
    page: int,
    page_size: int,
    max_page_size: int = 100,
) -> tuple[int, int]:
    """
    Convert page + page_size into limit + offset for DB queries.
    Clamps page_size to max_page_size.

    Args:
        page         : current page number (1-indexed, minimum 1)
        page_size    : number of items per page
        max_page_size: maximum allowed page_size (default 100)

    Returns:
        Tuple of (limit, offset)
    """
    page = max(1, page)
    page_size = max(1, min(page_size, max_page_size))
    offset = (page - 1) * page_size
    return page_size, offset