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
# GPSDevice
# Maps to: gps_devices table
# Hardware GPS units, scoped to a branch. IMEI is globally unique.
# Rules:
#   - Soft delete only — is_active = False
#   - device_imei unique across the entire system
#   - ondelete="RESTRICT" — soft-delete system, no cascade wipes
# -----------------------------------------------------------------------------
class GPSDevice(Base):
    __tablename__ = "gps_devices"

    device_id  : Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id  : Mapped[int]      = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
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

    def __repr__(self) -> str:
        return f"<GPSDevice device_id={self.device_id} imei={self.device_imei}>"


# -----------------------------------------------------------------------------
# BusDeviceAssignment
# Maps to: bus_device_assignments table
# Tracks GPS device ↔ bus assignment history. Append-only — never deleted.
# Active assignment: unassigned_at IS NULL
# Rules:
#   - Never hard delete — set unassigned_at = utcnow() to close assignment
#   - ondelete="RESTRICT" on all FKs — soft-delete system
# Partial Unique Indexes (must be added in Alembic migration via op.execute()):
#   CREATE UNIQUE INDEX idx_one_active_device_per_bus
#       ON bus_device_assignments(bus_id) WHERE unassigned_at IS NULL;
#   CREATE UNIQUE INDEX idx_one_active_bus_per_device
#       ON bus_device_assignments(device_id) WHERE unassigned_at IS NULL;
# -----------------------------------------------------------------------------
class BusDeviceAssignment(Base):
    __tablename__ = "bus_device_assignments"

    bus_device_id: Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id    : Mapped[int]             = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
    branch_id    : Mapped[int]             = mapped_column(Integer, nullable=False)
    bus_id       : Mapped[int]             = mapped_column(Integer, nullable=False)
    device_id    : Mapped[int]             = mapped_column(Integer, nullable=False)
    assigned_at  : Mapped[datetime]        = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    unassigned_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True, default=None)

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_bus_device_assignments_branch_school",
        ),
        ForeignKeyConstraint(
            ["bus_id", "branch_id", "school_id"],
            ["buses.bus_id", "buses.branch_id", "buses.school_id"],
            ondelete="RESTRICT",
            name="fk_bus_device_assignments_bus",
        ),
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
    )

    @property
    def is_active(self) -> bool:
        return self.unassigned_at is None

    def __repr__(self) -> str:
        return (
            f"<BusDeviceAssignment id={self.bus_device_id} "
            f"bus={self.bus_id} device={self.device_id} active={self.is_active}>"
        )