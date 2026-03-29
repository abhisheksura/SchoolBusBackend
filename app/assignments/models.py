from datetime import datetime

from sqlalchemy import (
    Boolean,
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
# StudentRouteAssignment
# Maps to: student_route_assignments table
# Links a student to a route + boarding stop per trip_type (PICKUP/DROPOFF).
# Rules:
#   - Soft delete only — is_active = False
#   - A separate row required for PICKUP and DROPOFF
#   - UNIQUE (student_id, route_id, assignment_type, school_id, branch_id)
#   - ondelete="RESTRICT" on all FKs — soft-delete system
# -----------------------------------------------------------------------------
class StudentRouteAssignment(Base):
    __tablename__ = "student_route_assignments"

    assignment_id  : Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id      : Mapped[int]      = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
    branch_id      : Mapped[int]      = mapped_column(Integer, nullable=False)
    student_id     : Mapped[int]      = mapped_column(Integer, nullable=False)
    route_id       : Mapped[int]      = mapped_column(Integer, nullable=False)
    stop_id        : Mapped[int]      = mapped_column(Integer, nullable=False)
    assignment_type: Mapped[str]      = mapped_column(String(20), nullable=False)
    is_active      : Mapped[bool]     = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    assigned_at    : Mapped[datetime] = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    updated_at     : Mapped[datetime] = mapped_column(TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_sra_branch_school",
        ),
        ForeignKeyConstraint(
            ["student_id", "branch_id", "school_id"],
            ["students.student_id", "students.branch_id", "students.school_id"],
            ondelete="RESTRICT",
            name="fk_sra_student",
        ),
        ForeignKeyConstraint(
            ["route_id", "branch_id", "school_id"],
            ["routes.route_id", "routes.branch_id", "routes.school_id"],
            ondelete="RESTRICT",
            name="fk_sra_route",
        ),
        ForeignKeyConstraint(
            ["stop_id", "branch_id", "school_id"],
            ["stops.stop_id", "stops.branch_id", "stops.school_id"],
            ondelete="RESTRICT",
            name="fk_sra_stop",
        ),
        UniqueConstraint(
            "student_id", "route_id", "assignment_type", "school_id", "branch_id",
            name="uq_sra_student_route_type",
        ),
        Index("idx_sra_student", "student_id"),
        Index("idx_sra_route", "route_id"),
        Index("idx_sra_branch", "branch_id", "school_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<StudentRouteAssignment id={self.assignment_id} "
            f"student={self.student_id} route={self.route_id} "
            f"type={self.assignment_type} active={self.is_active}>"
        )