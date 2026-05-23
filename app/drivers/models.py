from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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
# Driver
# Maps to: drivers table
# Scoped to (branch_id, school_id). Linked 1:1 to a user account.
# Rules:
#   - Soft delete only — is_active = False
#   - user_id is nullable — driver may exist before user account is created
#   - ondelete="RESTRICT" on all FKs — soft-delete system, no cascade wipes
# -----------------------------------------------------------------------------
class Driver(TenantInfoMixin, Base):
    __tablename__ = "drivers"

    driver_id     : Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id       : Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        unique=True,
        nullable=True,
    )
    school_id     : Mapped[int]        = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
    branch_id     : Mapped[int]        = mapped_column(Integer, nullable=False)
    first_name    : Mapped[str]        = mapped_column(String(100), nullable=False)
    last_name     : Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone         : Mapped[str | None] = mapped_column(String(20), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active     : Mapped[bool]       = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at    : Mapped[datetime]   = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    updated_at    : Mapped[datetime]   = mapped_column(TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_drivers_branch_id_school_id_branches",
        ),
        UniqueConstraint(
            "driver_id", "branch_id", "school_id",
            name="uq_drivers_driver_id_branch_id_school_id",
        ),
        Index("idx_drivers_school_branch", "school_id", "branch_id"),
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
        primaryjoin="and_(Driver.branch_id == Branch.branch_id, Driver.school_id == Branch.school_id)",
        foreign_keys="[Driver.branch_id, Driver.school_id]",
        lazy="noload",
        viewonly=True,
    )
    def __repr__(self) -> str:
        return f"<Driver driver_id={self.driver_id} name={self.first_name} {self.last_name}>"