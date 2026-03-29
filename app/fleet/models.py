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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TZDateTime


# -----------------------------------------------------------------------------
# Bus
# Maps to: buses table
# Scoped to (branch_id, school_id).
# Rules:
#   - Soft delete only — is_active = False
#   - capacity must be > 0 (DB CHECK)
#   - ondelete="RESTRICT" — soft-delete system, no cascade wipes
# -----------------------------------------------------------------------------
class Bus(Base):
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

    def __repr__(self) -> str:
        return f"<Bus bus_id={self.bus_id} bus_number={self.bus_number}>"