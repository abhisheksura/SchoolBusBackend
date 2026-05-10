from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import Base, TZDateTime

if TYPE_CHECKING:
    from app.schools.models import School, Branch


# -----------------------------------------------------------------------------
# Bus
# Maps to: buses table
# Scoped to (branch_id, school_id) via composite FK.
# Rules:
#   - Soft delete only — is_active = False, never hard delete
#   - capacity must be > 0 (DB CHECK)
#   - bus_number unique per school — same number allowed across schools
#   - ondelete="RESTRICT" — soft-delete system, no cascade wipes
# -----------------------------------------------------------------------------
class Bus(Base):
    """ORM model for the buses table."""

    __tablename__ = "buses"

    bus_id    : Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id : Mapped[int]      = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
    branch_id : Mapped[int]      = mapped_column(Integer, nullable=False)
    bus_number: Mapped[str]      = mapped_column(String(20), nullable=False)
    capacity  : Mapped[int]      = mapped_column(Integer, nullable=False)
    is_active : Mapped[bool]     = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # -------------------------------------------------------------------------
    # Relationships
    # lazy="noload" — never lazy load in async context.
    # Use selectinload explicitly in repo queries that return BusResponse.
    #
    # school: simple FK — school_id references schools.school_id directly.
    #
    # branch: composite FK — branch is identified by (branch_id, school_id).
    #   foreign_keys must be passed as a list of column objects (not strings)
    #   to avoid SQLAlchemy mapper resolution failures.
    # -------------------------------------------------------------------------
    school: Mapped["School"] = relationship(
        "School",
        foreign_keys=[school_id],
        lazy="noload",
    )
    branch: Mapped["Branch"] = relationship(
        "Branch",
        foreign_keys=[branch_id, school_id],
        lazy="noload",
        primaryjoin="and_(Bus.branch_id == Branch.branch_id, Bus.school_id == Branch.school_id)",
    )

    # -------------------------------------------------------------------------
    # Computed properties
    # Pydantic with from_attributes=True reads these as regular attributes.
    # Only valid when school/branch are loaded via selectinload — calling these
    # on a Bus fetched without relations raises AttributeError.
    # -------------------------------------------------------------------------
    @property
    def school_name(self) -> str:
        """Flattens bus.school.school_name for BusResponse serialization."""
        return self.school.school_name

    @property
    def branch_name(self) -> str:
        """Flattens bus.branch.branch_name for BusResponse serialization."""
        return self.branch.branch_name

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_buses_branch_id_school_id_branches",
        ),
        CheckConstraint("capacity > 0", name="ck_buses_capacity_positive"),
        UniqueConstraint("bus_number", "school_id", name="uq_buses_bus_number_school_id"),
        Index("idx_buses_school_branch", "school_id", "branch_id"),
    )

    def __repr__(self) -> str:
        """Return a human-readable representation of the Bus instance."""
        return f"<Bus bus_id={self.bus_id} bus_number={self.bus_number!r}>"