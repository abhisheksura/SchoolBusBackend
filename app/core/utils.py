from datetime import datetime, timezone
from typing import Any, Type, TypeVar
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.cache import TTLCache, get_or_set


# -----------------------------------------------------------------------------
# utcnow()
# Returns the current UTC time as a timezone-naive datetime.
#
# Why not datetime.utcnow()?
#   - Deprecated since Python 3.12, will be removed in a future version
#   - Misleading — returns a naive datetime with no tzinfo, easy to confuse
#     with local time
#
# Why not datetime.now(timezone.utc)?
#   - Returns a timezone-AWARE datetime (tzinfo=UTC)
#   - Our DB columns are TIMESTAMP WITHOUT TIME ZONE — asyncpg rejects
#     timezone-aware datetimes with:
#     "can't subtract offset-naive and offset-aware datetimes"
#
# Solution:
#   - Use datetime.now(timezone.utc) for correctness (avoids deprecation)
#   - Strip tzinfo with .replace(tzinfo=None) to satisfy TIMESTAMP WITHOUT
#     TIME ZONE columns
#
# Usage:
#   from app.core.utils import utcnow
#   expires_at = utcnow()
# -----------------------------------------------------------------------------
def utcnow() -> datetime:
    """
    Return the current UTC time as a timezone-naive datetime.
    Safe replacement for the deprecated datetime.utcnow().
    Compatible with PostgreSQL TIMESTAMP WITHOUT TIME ZONE columns.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)

# Define a Generic type bound to Pydantic's BaseModel for our schema converter
ResponseSchema = TypeVar("ResponseSchema", bound=BaseModel)

# Thread-safe global in-memory caches to save round-trips to the DB.
# (If your deployment uses multiple workers/servers, you can later replace 
# these with Redis using the exact same function signatures).
_SCHOOL_CACHE: dict[int, str] = {}
_BRANCH_CACHE: dict[int, str] = {}

# Paginated stop lists — one cache line per (tenant scope, filters, page)
_ROUTE_CACHE = TTLCache(ttl_seconds=300)

# Paginated route lists — same shape as stops
_STOP_CACHE = TTLCache(ttl_seconds=300)

async def get_tenant_names(db: AsyncSession, school_id: int, branch_id: int) -> tuple[str, str]:
    """
    Retrieves school and branch names. Looks them up in the local in-memory 
    cache first; falls back to a fast database query if they aren't cached yet.
    """
    # 1. Resolve School Name
    if school_id not in _SCHOOL_CACHE:
        # Inline import to prevent circular dependency issues within core utils
        from app.schools.models import School  
        
        school_name = await db.scalar(
            select(School.school_name).where(School.school_id == school_id)
        )
        _SCHOOL_CACHE[school_id] = school_name or "Unknown School"

    # 2. Resolve Branch Name
    if branch_id not in _BRANCH_CACHE:
        # Inline import based on your database schema structure
        from app.schools.models import Branch  
        
        branch_name = await db.scalar(
            select(Branch.branch_name).where(Branch.branch_id == branch_id)
        )
        _BRANCH_CACHE[branch_id] = branch_name or "Unknown Branch"

    return _SCHOOL_CACHE[school_id], _BRANCH_CACHE[branch_id]

# ---------------------------------------------------------------------------
# Reads — cache-aside, same shape as your original
# ---------------------------------------------------------------------------

async def get_route_names(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
) -> dict[int, str]:
    """
    Returns {route_id: route_name} for every route in this tenant.
    Built once per tenant and cached until explicitly invalidated by a
    write to that tenant's routes (see invalidate_route_names below).
    """
    cache_key = (school_id, branch_id)
    async def _load() -> dict[int, str]:
        # Inline import to avoid circular dependency with app.routes.models
        from app.routes.models import Route

        rows = await db.execute(
            select(Route.route_id, Route.route_name).where(
                Route.school_id == school_id,
                Route.branch_id == branch_id,
            )
        )
        return {route_id: route_name for route_id, route_name in rows.all()}

    return await get_or_set(_ROUTE_CACHE, cache_key, _load)


async def get_stop_names(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
) -> dict[int, str]:
    """
    Returns {stop_id: stop_name} for every stop in this tenant.
    Built once per tenant and cached until explicitly invalidated by a
    write to that tenant's stops (see invalidate_stop_names below).
    """
    cache_key = (school_id, branch_id)
    async def _load() -> dict[int, str]:
        # Inline import to avoid circular dependency with app.stops.models
        from app.routes.models import Stop

        rows = await db.execute(
            select(Stop.stop_id, Stop.stop_name).where(
                Stop.school_id == school_id,
                Stop.branch_id == branch_id,
            )
        )
        return {stop_id: stop_name for stop_id, stop_name in rows.all()}

    return await get_or_set(_STOP_CACHE, cache_key, _load)

# ---------------------------------------------------------------------------
# Invalidation — MUST be called from every route/stop write path
# ---------------------------------------------------------------------------

def invalidate_route_names(school_id: int, branch_id: int) -> None:
    """
    Drops the cached route name map for this tenant.

    Call this from: create_route, update_route (if route_name changed),
    deactivate_route. Cheap to call unconditionally on any route write —
    the next get_route_names() call just rebuilds it from the DB.
    """
    _ROUTE_CACHE.invalidate_prefix((school_id, branch_id))


def invalidate_stop_names(school_id: int, branch_id: int) -> None:
    """
    Drops the cached stop name map for this tenant.

    Call this from: create_stop, update_stop (if stop_name changed),
    deactivate_stop. Cheap to call unconditionally on any stop write.
    """
    _STOP_CACHE.invalidate_prefix((school_id, branch_id))


def to_tenant_response(
    model: Any,
    schema_cls: Type[ResponseSchema],
    *,
    school_name: str | None,
    branch_name: str | None,
    **extra_fields: Any,
) -> ResponseSchema:
    """
    Maps an SQLAlchemy ORM model directly to a target Pydantic Response schema
    while injecting global tenant data safely.

    This avoids model.__dict__ pitfalls (like leaking SQLAlchemy internal states) 
    by rebuilding a clean dataset map directly from the table columns.
    """
    # 1. Safely extract core database fields into a dictionary
    model_data = {
        col.name: getattr(model, col.name)
        for col in model.__table__.columns
        if hasattr(model, col.name)
    }

    # 2. Inject the cached context strings
    model_data["school_name"] = school_name
    model_data["branch_name"] = branch_name

    # 3. Inject any additional resolved fields (route_name, stop_name, etc.)
    model_data.update(extra_fields)

    # 4. Parse and validate directly into your Pydantic Response Class
    return schema_cls.model_validate(model_data)