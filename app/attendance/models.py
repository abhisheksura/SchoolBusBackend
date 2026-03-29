from datetime import datetime

from sqlalchemy import (
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
from app.core.enums import AttendanceStatus


# -----------------------------------------------------------------------------
# StudentAttendance
# Maps to: student_attendance table
# Per-trip attendance record per student. Immutable once marked.
# Rules:
#   - Not soft-deleted — records are permanent once marked
#   - Status can be corrected via UPDATE (BRANCH_ADMIN+)
#   - stop_id / marked_by_driver_id nullable — SET NULL if asset deleted
#   - UNIQUE per (student, trip, assignment_type, school, branch)
#   - ondelete="CASCADE" on trip_id — attendance gone when trip deleted
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
        # stop_id nullable — FK only enforced when non-NULL
        ForeignKeyConstraint(
            ["stop_id", "branch_id", "school_id"],
            ["stops.stop_id", "stops.branch_id", "stops.school_id"],
            name="fk_attendance_stop",
        ),
        # marked_by_driver_id nullable — preserved as NULL if driver deleted
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