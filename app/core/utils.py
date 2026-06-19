from datetime import datetime, timezone
from typing import Any, Type, TypeVar
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


def to_tenant_response(
    model: Any,
    schema_cls: Type[ResponseSchema],
    *,
    school_name: str | None,
    branch_name: str | None,
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

    # 3. Parse and validate directly into your Pydantic Response Class
    return schema_cls.model_validate(model_data)