import math
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, computed_field

T = TypeVar("T")


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
# paginate()
# Helper to build a PaginatedResponse from a list of items and a total count.
# Called in every service list function — avoids repeating the pages calculation.
#
# Usage in service:
#   items, total = await repo.get_all_schools(db, limit=page_size, offset=(page-1)*page_size)
#   return paginate(items, total, page, page_size)
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
# Enforces MAX_PAGE_SIZE from settings.
#
# Usage in service:
#   limit, offset = pagination_params(page, page_size)
#   items, total = await repo.get_all_schools(db, limit=limit, offset=offset)
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