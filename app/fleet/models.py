from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import Base, TZDateTime


# -----------------------------------------------------------------------------
# Driver
# Maps to: drivers table
# Scoped to (branch_id, school_id). Linked 1:1 to a user account.
# Rules:
#   - Soft delete only — set is_active = False
#   - user_id is nullable — driver may exist before user account is created
#   - ondelete="RESTRICT" on all FKs — prevents accidental hard-delete cascade
# -----------------------------------------------------------------------------
class Driver(Base):
    __tablename__ = "drivers"

    driver_id     : Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id       : Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        unique=True,
        nullable=True,
    )
    school_id     : Mapped[int]        = mapped_column(
        Integer,
        ForeignKey("schools.school_id", ondelete="RESTRICT"),
        nullable=False,
    )
    branch_id     : Mapped[int]        = mapped_column(Integer, nullable=False)
    first_name    : Mapped[str]        = mapped_column(String(100), nullable=False)
    last_name     : Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone         : Mapped[str | None] = mapped_column(String(20), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active     : Mapped[bool]       = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at    : Mapped[datetime]   = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    updated_at    : Mapped[datetime]   = mapped_column(TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # ondelete="RESTRICT" — prevent cascade hard-delete in soft-delete system
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

    def __repr__(self) -> str:
        return f"<Driver driver_id={self.driver_id} name={self.first_name} {self.last_name}>"


# -----------------------------------------------------------------------------
# Bus
# Maps to: buses table
# Scoped to (branch_id, school_id).
# Rules:
#   - Soft delete only — set is_active = False
#   - capacity must be > 0 (enforced by DB CHECK constraint)
#   - ondelete="RESTRICT" — prevents accidental hard-delete cascade
# -----------------------------------------------------------------------------
class Bus(Base):
    __tablename__ = "buses"

    bus_id    : Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id : Mapped[int]      = mapped_column(
        Integer,
        ForeignKey("schools.school_id", ondelete="RESTRICT"),
        nullable=False,
    )
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
        UniqueConstraint(
            "bus_id", "branch_id", "school_id",
            name="uq_buses_bus_id_branch_id_school_id",
        ),
        Index("idx_buses_school_branch", "school_id", "branch_id"),
    )

    # No relationship to BusDeviceAssignment here — use repository queries
    # directly to avoid composite FK join ambiguity.

    def __repr__(self) -> str:
        return f"<Bus bus_id={self.bus_id} bus_number={self.bus_number}>"


# -----------------------------------------------------------------------------
# GPSDevice
# Maps to: gps_devices table
# Hardware GPS units, scoped to a branch. IMEI is globally unique.
# Rules:
#   - Soft delete only — set is_active = False
#   - device_imei must be unique across the entire system
#   - ondelete="RESTRICT" — prevents accidental hard-delete cascade
# -----------------------------------------------------------------------------
class GPSDevice(Base):
    __tablename__ = "gps_devices"

    device_id  : Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id  : Mapped[int]      = mapped_column(
        Integer,
        ForeignKey("schools.school_id", ondelete="RESTRICT"),
        nullable=False,
    )
    branch_id  : Mapped[int]      = mapped_column(Integer, nullable=False)
    device_imei: Mapped[str]      = mapped_column(String(100), nullable=False, unique=True)
    is_active  : Mapped[bool]     = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at : Mapped[datetime] = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    updated_at : Mapped[datetime] = mapped_column(TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_gps_devices_branch_id_school_id_branches",
        ),
        UniqueConstraint(
            "device_id", "branch_id", "school_id",
            name="uq_gps_devices_device_id_branch_id_school_id",
        ),
        Index("idx_gps_devices_school_branch", "school_id", "branch_id"),
    )

    # No relationship to BusDeviceAssignment — use repository queries directly.

    def __repr__(self) -> str:
        return f"<GPSDevice device_id={self.device_id} imei={self.device_imei}>"


# -----------------------------------------------------------------------------
# BusDeviceAssignment
# Maps to: bus_device_assignments table
# Tracks GPS device ↔ bus assignment history. Append-only — never deleted.
# Active assignment: unassigned_at IS NULL
#
# Rules:
#   - Never hard delete — set unassigned_at = utcnow() to close assignment
#   - ondelete="RESTRICT" on all FKs — soft-delete system, no cascade wipes
#
# Partial Unique Indexes (enforced at DB level via Alembic migration):
#   CREATE UNIQUE INDEX idx_one_active_device_per_bus
#       ON bus_device_assignments(bus_id) WHERE unassigned_at IS NULL;
#   CREATE UNIQUE INDEX idx_one_active_bus_per_device
#       ON bus_device_assignments(device_id) WHERE unassigned_at IS NULL;
#
# These cannot be expressed in SQLAlchemy Index() — they must be created
# in the Alembic migration with op.execute(). They are the final DB-level
# guard against race conditions in assign_device_to_bus().
#
# ORM Relationships:
#   No back-references to Bus or GPSDevice are defined here.
#   BusDeviceAssignment has three ForeignKeyConstraints sharing branch_id
#   and school_id — SQLAlchemy cannot resolve the join ambiguity automatically
#   even with explicit foreign_keys. All assignment lookups go through the
#   repository directly (get_active_assignment_by_bus_id, etc.).
# -----------------------------------------------------------------------------
class BusDeviceAssignment(Base):
    __tablename__ = "bus_device_assignments"

    bus_device_id: Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id    : Mapped[int]             = mapped_column(
        Integer,
        ForeignKey("schools.school_id", ondelete="RESTRICT"),
        nullable=False,
    )
    branch_id    : Mapped[int]             = mapped_column(Integer, nullable=False)
    bus_id       : Mapped[int]             = mapped_column(Integer, nullable=False)
    device_id    : Mapped[int]             = mapped_column(Integer, nullable=False)
    assigned_at  : Mapped[datetime]        = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    unassigned_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True, default=None)

    __table_args__ = (
        # Branch + school scope
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_bus_device_assignments_branch_school",
        ),
        # Bus composite FK
        ForeignKeyConstraint(
            ["bus_id", "branch_id", "school_id"],
            ["buses.bus_id", "buses.branch_id", "buses.school_id"],
            ondelete="RESTRICT",
            name="fk_bus_device_assignments_bus",
        ),
        # GPS device composite FK
        ForeignKeyConstraint(
            ["device_id", "branch_id", "school_id"],
            ["gps_devices.device_id", "gps_devices.branch_id", "gps_devices.school_id"],
            ondelete="RESTRICT",
            name="fk_bus_device_assignments_device",
        ),
        CheckConstraint(
            "unassigned_at IS NULL OR unassigned_at > assigned_at",
            name="ck_bus_device_assignments_dates",
        ),
        Index("idx_bus_device_assignments_school_branch", "school_id", "branch_id"),
        Index("idx_bus_device_assignments_bus_id", "bus_id"),
        Index("idx_bus_device_assignments_device_id", "device_id"),
        # --------------------------------------------------------------------
        # Partial unique indexes are defined in Alembic migration, not here.
        # SQLAlchemy Index() does not support WHERE clauses.
        # Add to migration with:
        #   op.execute("""
        #       CREATE UNIQUE INDEX idx_one_active_device_per_bus
        #           ON bus_device_assignments(bus_id)
        #           WHERE unassigned_at IS NULL;
        #       CREATE UNIQUE INDEX idx_one_active_bus_per_device
        #           ON bus_device_assignments(device_id)
        #           WHERE unassigned_at IS NULL;
        #   """)
        # --------------------------------------------------------------------
    )

    @property
    def is_active(self) -> bool:
        """Return True if this assignment is currently active."""
        return self.unassigned_at is None

    def __repr__(self) -> str:
        return (
            f"<BusDeviceAssignment id={self.bus_device_id} "
            f"bus={self.bus_id} device={self.device_id} active={self.is_active}>"
        )