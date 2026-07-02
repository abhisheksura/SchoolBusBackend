
from datetime import datetime

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
from app.core.db.mixins.tenant_mixin import TenantInfoMixin


# -----------------------------------------------------------------------------
# Bus
# Maps to: buses table
# Scoped to (branch_id, school_id).
# Rules:
#   - Soft delete only — is_active = False
#   - capacity must be > 0 (DB CHECK)
#   - ondelete="RESTRICT" — soft-delete system, no cascade wipes
#   - TenantInfoMixin provides school_name / branch_name computed properties
#     when school/branch relationships are selectinload-ed
# -----------------------------------------------------------------------------
class Bus(TenantInfoMixin, Base):
    __tablename__ = "buses"

    bus_id    : Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id : Mapped[int]      = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
    branch_id : Mapped[int]      = mapped_column(Integer, nullable=False)
    bus_number: Mapped[str]      = mapped_column(String(50), nullable=False)
    capacity  : Mapped[int]      = mapped_column(Integer, nullable=False)
    is_active : Mapped[bool]     = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_buses_branch_id_school_id_branches",
        ),
        CheckConstraint("capacity > 0", name="ck_buses_capacity_positive"),
        UniqueConstraint("bus_id", "branch_id", "school_id", name="uq_buses_bus_id_branch_id_school_id"),
        Index("idx_buses_school_branch", "school_id", "branch_id"),
    )

    # -------------------------------------------------------------------------
    # Relationships — lazy="noload" enforces explicit selectinload in repo.
    # Accessing without loading raises an error rather than triggering a silent
    # N+1 sync query (which would fail in async context anyway).
    # TenantInfoMixin.school_name / .branch_name use getattr — safe if not loaded
    # (returns None), so list endpoints that skip joining are fine.
    # -------------------------------------------------------------------------
    school: Mapped["School"] = relationship(  # type: ignore[name-defined]
        "School",
        foreign_keys=[school_id],
        lazy="noload",
    )
    branch: Mapped["Branch"] = relationship(  # type: ignore[name-defined]
        "Branch",
        primaryjoin="and_(Bus.branch_id == Branch.branch_id, Bus.school_id == Branch.school_id)",
        foreign_keys="[Bus.branch_id, Bus.school_id]",
        lazy="noload",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<Bus bus_id={self.bus_id} bus_number={self.bus_number}>"