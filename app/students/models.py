from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import Base, TZDateTime
from app.core.enums import LeaveRequestStatus


# -----------------------------------------------------------------------------
# Student
# Maps to: students table
# Scoped to (branch_id, school_id). Every student must have a user account.
# Rules:
#   - Soft delete only — is_active = False
#   - user_id is NOT nullable (BIGINT) — every student must have a login
#   - ondelete="RESTRICT" on all FKs — soft-delete system, no cascade wipes
# -----------------------------------------------------------------------------
class Student(Base):
    __tablename__ = "students"

    student_id      : Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id       : Mapped[int]        = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
    branch_id       : Mapped[int]        = mapped_column(Integer, nullable=False)
    user_id         : Mapped[int]        = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), unique=True, nullable=False)
    first_name      : Mapped[str]        = mapped_column(String(100), nullable=False)
    last_name       : Mapped[str | None] = mapped_column(String(100), nullable=True)
    admission_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    grade           : Mapped[str | None] = mapped_column(String(20), nullable=True)
    section         : Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active       : Mapped[bool]       = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at      : Mapped[datetime]   = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    updated_at      : Mapped[datetime]   = mapped_column(TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_students_branch_id_school_id_branches",
        ),
        UniqueConstraint(
            "school_id", "branch_id", "first_name", "last_name", "grade", "section",
            name="uq_students_identity",
        ),
        UniqueConstraint(
            "student_id", "branch_id", "school_id",
            name="uq_students_student_id_branch_school",
        ),
        Index("idx_students_school_branch", "school_id", "branch_id"),
    )
    school: Mapped["School"] = relationship(  # type: ignore[name-defined]
        "School",
        foreign_keys=[school_id],
        lazy="noload",
    )
    branch: Mapped["Branch"] = relationship(  # type: ignore[name-defined]
        "Branch",
        primaryjoin="and_(Student.branch_id == Branch.branch_id, Student.school_id == Branch.school_id)",
        foreign_keys="[Student.branch_id, Student.school_id]",
        lazy="noload",
        viewonly=True,
    )
    # cascade="save-update, merge" only — soft-delete system
    student_parents: Mapped[list["StudentParent"]] = relationship(
        "StudentParent",
        back_populates="student",
        cascade="save-update, merge",
        lazy="noload",
    )
    leave_requests: Mapped[list["StudentLeaveRequest"]] = relationship(
        "StudentLeaveRequest",
        back_populates="student",
        cascade="save-update, merge",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Student student_id={self.student_id} name={self.first_name} {self.last_name}>"


# -----------------------------------------------------------------------------
# Parent
# Maps to: parents table
# Scoped to school_id only (not branch). 1:1 with users.
# Parents are school-scoped — they can have children in different branches.
# Rules:
#   - Soft delete only — is_active = False
#   - user_id NOT nullable (BIGINT) — every parent must have a login
# -----------------------------------------------------------------------------
class Parent(Base):
    __tablename__ = "parents"

    parent_id      : Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id        : Mapped[int]        = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), unique=True, nullable=False)
    school_id      : Mapped[int]        = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
    first_name     : Mapped[str]        = mapped_column(String(100), nullable=False)
    last_name      : Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone          : Mapped[str | None] = mapped_column(String(20), nullable=True)
    alternate_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email          : Mapped[str | None] = mapped_column(String(150), nullable=True)
    address        : Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active      : Mapped[bool]       = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at     : Mapped[datetime]   = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    updated_at     : Mapped[datetime]   = mapped_column(TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_parents_school", "school_id"),
    )

    student_parents: Mapped[list["StudentParent"]] = relationship(
        "StudentParent",
        back_populates="parent",
        cascade="save-update, merge",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Parent parent_id={self.parent_id} name={self.first_name} {self.last_name}>"


# -----------------------------------------------------------------------------
# StudentParent
# Maps to: student_parents table
# M:N link between students and parents.
# Rules:
#   - Hard-delete is valid here — removing the link ≠ deleting student/parent
#   - is_primary: app-enforced, only one primary parent per student
#   - ondelete="RESTRICT" — student/parent must be deactivated before unlinking
#   - relationship column holds label e.g. FATHER, MOTHER, GUARDIAN
# -----------------------------------------------------------------------------
class StudentParent(Base):
    __tablename__ = "student_parents"

    student_parent_id: Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id       : Mapped[int]      = mapped_column(Integer, ForeignKey("students.student_id", ondelete="RESTRICT"), nullable=False)
    parent_id        : Mapped[int]      = mapped_column(Integer, ForeignKey("parents.parent_id", ondelete="RESTRICT"), nullable=False)
    relationship_type: Mapped[str]      = mapped_column(String(50), nullable=False)
    is_primary       : Mapped[bool]     = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at       : Mapped[datetime] = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    updated_at       : Mapped[datetime] = mapped_column(TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("student_id", "parent_id", name="uq_student_parents_student_parent"),
        Index("idx_student_parents_student", "student_id"),
        Index("idx_student_parents_parent", "parent_id"),
    )

    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="student_parents",
        lazy="noload",
    )
    parent: Mapped["Parent"] = relationship(
        "Parent",
        back_populates="student_parents",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<StudentParent id={self.student_parent_id} "
            f"student={self.student_id} parent={self.parent_id} "
            f"rel={self.relationship_type} primary={self.is_primary}>"
        )


# -----------------------------------------------------------------------------
# StudentLeaveRequest
# Maps to: student_leave_requests table
# Date-range absence request submitted by parent or admin.
# Rules:
#   - end_date >= start_date enforced by DB CHECK
#   - Cancel via status=REJECTED — never hard-delete
#   - requested_by SET NULL on user delete — preserves leave history
#   - No updated_at — status transitions only, append-style
#   - Status transitions: PENDING → APPROVED | REJECTED
# -----------------------------------------------------------------------------
class StudentLeaveRequest(Base):
    __tablename__ = "student_leave_requests"

    leave_id    : Mapped[int]                = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id   : Mapped[int]                = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
    branch_id   : Mapped[int]                = mapped_column(Integer, nullable=False)
    student_id  : Mapped[int]                = mapped_column(Integer, ForeignKey("students.student_id", ondelete="RESTRICT"), nullable=False)
    requested_by: Mapped[int | None]         = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    start_date  : Mapped[date]               = mapped_column(Date, nullable=False)
    end_date    : Mapped[date]               = mapped_column(Date, nullable=False)
    reason      : Mapped[str | None]         = mapped_column(Text, nullable=True)
    status      : Mapped[str]                = mapped_column(
        String(20),
        nullable=False,
        default=LeaveRequestStatus.PENDING.value,
        server_default=LeaveRequestStatus.PENDING.value,
    )
    created_at  : Mapped[datetime]           = mapped_column(TZDateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_student_leave_requests_branch_school",
        ),
        CheckConstraint("end_date >= start_date", name="ck_leave_requests_date_range"),
        Index("idx_leave_student", "student_id"),
        Index("idx_leave_status", "status"),
        Index("idx_leave_date_range", "start_date", "end_date"),
    )

    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="leave_requests",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<StudentLeaveRequest leave_id={self.leave_id} "
            f"student={self.student_id} {self.start_date}→{self.end_date} "
            f"status={self.status}>"
        )