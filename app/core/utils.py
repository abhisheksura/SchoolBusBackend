from datetime import datetime, timezone


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