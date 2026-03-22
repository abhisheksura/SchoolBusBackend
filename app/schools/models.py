from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import Base, TZDateTime


# -----------------------------------------------------------------------------
# School
# Maps to: schools table
# Top-level tenant — every resource in the system traces back to a school_id.
# Rules:
#   - Soft delete only — set is_active = False, never hard delete
#   - school_name used instead of name for consistent fully-qualified naming
# -----------------------------------------------------------------------------
class School(Base):
    __tablename__ = "schools"

    school_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    school_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # -------------------------------------------------------------------------
    # Relationships
    # lazy="noload" — must use selectinload/joinedload explicitly in queries
    #
    # cascade="save-update, merge" only — NO delete or delete-orphan.
    # This system uses soft deletes exclusively (is_active = False).
    # cascade="all, delete-orphan" would allow accidental hard deletes
    # via db.delete(school_obj) bypassing the soft-delete policy.
    # DB-level ON DELETE CASCADE on branches.school_id FK is intentional —
    # it only triggers on raw SQL DELETE, which is a conscious DBA action.
    # -------------------------------------------------------------------------
    branches: Mapped[list["Branch"]] = relationship(
        "Branch",
        back_populates="school",
        cascade="save-update, merge",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<School school_id={self.school_id} school_name={self.school_name}>"


# -----------------------------------------------------------------------------
# Branch
# Maps to: branches table
# Branch or campus under a school.
# Most resources in the system are scoped at (branch_id, school_id) level.
# Rules:
#   - Soft delete only — set is_active = False, never hard delete
#   - Composite unique constraint (branch_id, school_id) enforced at DB level
# -----------------------------------------------------------------------------
class Branch(Base):
    __tablename__ = "branches"

    branch_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    school_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("schools.school_id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_name: Mapped[str] = mapped_column(
        String(150), nullable=False
    )
    branch_address: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    branch_phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    branch_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # -------------------------------------------------------------------------
    # Constraints + Indexes
    # -------------------------------------------------------------------------
    __table_args__ = (
        UniqueConstraint(
            "branch_id",
            "school_id",
            name="uq_branches_branch_id_school_id",
        ),
        Index("idx_branches_school_id", "school_id"),
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    school: Mapped["School"] = relationship(
        "School",
        back_populates="branches",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<Branch branch_id={self.branch_id} "
            f"school_id={self.school_id} branch_name={self.branch_name}>"
        )