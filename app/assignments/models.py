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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import Base, TZDateTime
from app.core.enums import AttendanceStatus, TripType


# -----------------------------------------------------------------------------
# StudentRouteAssignment
# Maps to: student_route_assignments table
# Links a student to a route + boarding stop per trip_type (PICKUP/DROPOFF).
# Rules:
#   - Soft delete only — is_active = False
#   - A separate row is required for PICKUP and DROPOFF
#   - UNIQUE (student_id, route_id, assignment_type, school_id, branch_id)
#   - ondelete="RESTRICT" on stop — a stop in use cannot be hard-deleted
#   - ondelete="RESTRICT" on student/route/branch/school — soft-delete system
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


# -----------------------------------------------------------------------------
# StudentAttendance
# Maps to: student_attendance table
# Per-trip attendance record per student. Immutable once created.
# Rules:
#   - Not soft-deleted — records are permanent once marked
#   - Status can be corrected via UPDATE (BRANCH_ADMIN+)
#   - stop_id / marked_by_driver_id nullable — SET NULL if asset deleted
#   - UNIQUE per (student, trip, assignment_type, school, branch)
#   - ondelete="CASCADE" on trip_id — attendance gone if trip is deleted
#   - ondelete="RESTRICT" on student/school/branch — soft-delete system
# -----------------------------------------------------------------------------
class StudentAttendance(Base):
    __tablename__ = "student_attendance"

    attendance_id      : Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id          : Mapped[int]        = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
    branch_id          : Mapped[int]        = mapped_column(Integer, nullable=False)
    student_id         : Mapped[int]        = mapped_column(Integer, nullable=False)
    trip_id            : Mapped[int]        = mapped_column(Integer, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False)
    assignment_type    : Mapped[str]        = mapped_column(String(20), nullable=False)
    attendance_status  : Mapped[str]        = mapped_column(String(20), nullable=False)
    stop_id            : Mapped[int | None] = mapped_column(Integer, nullable=True)
    marked_at          : Mapped[datetime]   = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    marked_by_driver_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_attendance_branch_school",
        ),
        ForeignKeyConstraint(
            ["student_id", "branch_id", "school_id"],
            ["students.student_id", "students.branch_id", "students.school_id"],
            ondelete="RESTRICT",
            name="fk_attendance_student",
        ),
        # stop_id nullable — no ondelete needed (FK only enforced when non-NULL)
        ForeignKeyConstraint(
            ["stop_id", "branch_id", "school_id"],
            ["stops.stop_id", "stops.branch_id", "stops.school_id"],
            name="fk_attendance_stop",
        ),
        # marked_by_driver_id nullable — SET NULL behaviour handled at app layer
        ForeignKeyConstraint(
            ["marked_by_driver_id", "branch_id", "school_id"],
            ["drivers.driver_id", "drivers.branch_id", "drivers.school_id"],
            name="fk_attendance_driver",
        ),
        UniqueConstraint(
            "student_id", "trip_id", "assignment_type", "school_id", "branch_id",
            name="uq_attendance_student_trip_type",
        ),
        Index("idx_attendance_trip", "trip_id"),
        Index("idx_attendance_student", "student_id"),
        Index("idx_attendance_branch", "branch_id", "school_id"),
        Index("idx_attendance_driver", "marked_by_driver_id"),
    )

    @property
    def status(self) -> AttendanceStatus:
        return AttendanceStatus(self.attendance_status)

    def __repr__(self) -> str:
        return (
            f"<StudentAttendance id={self.attendance_id} "
            f"student={self.student_id} trip={self.trip_id} "
            f"type={self.assignment_type} status={self.attendance_status}>"
        )