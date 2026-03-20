from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData


# -----------------------------------------------------------------------------
# Constraint Naming Convention
# Alembic uses these to auto-generate consistent migration names.
# Without this, FK / index names differ across environments and
# alembic downgrade fails because it can't find the constraint to drop.
# -----------------------------------------------------------------------------
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


# -----------------------------------------------------------------------------
# Declarative Base
# All domain models across every domain (auth, fleet, trips etc.)
# inherit from this single Base so Alembic can discover them all.
# -----------------------------------------------------------------------------
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
