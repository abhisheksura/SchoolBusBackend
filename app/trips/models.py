from datetime import date, datetime

from sqlalchemy import (
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import Base, TZDateTime
from app.core.enums import TripStatus, TripType


# -----------------------------------------------------------------------------
# Trip
# Maps to: trips table
# One trip per route per service_date per trip_type.
# Rules:
#   - Soft-cancel only — set trip_status = CANCELLED, never delete
#   - bus_id / driver_id nullable — SET NULL on delete preserves history
#   - Status transitions enforced by service via TRIP_STATUS_TRANSITIONS
#   - ondelete="RESTRICT" on route/school/branch — soft-delete system
#   - ondelete="SET NULL" on bus/driver — historical records preserved
# -----------------------------------------------------------------------------
class Trip(Base):
    __tablename__ = "trips"

    trip_id          : Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id        : Mapped[int]             = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
    branch_id        : Mapped[int]             = mapped_column(Integer, nullable=False)
    route_id         : Mapped[int]             = mapped_column(Integer, ForeignKey("routes.route_id", ondelete="RESTRICT"), nullable=False)
    bus_id           : Mapped[int | None]      = mapped_column(Integer, ForeignKey("buses.bus_id", ondelete="SET NULL"), nullable=True)
    driver_id        : Mapped[int | None]      = mapped_column(Integer, ForeignKey("drivers.driver_id", ondelete="SET NULL"), nullable=True)
    service_date     : Mapped[date]            = mapped_column(Date, nullable=False)
    trip_type        : Mapped[str]             = mapped_column(String(20), nullable=False)
    trip_status      : Mapped[str]             = mapped_column(
        String(20),
        nullable=False,
        default=TripStatus.SCHEDULED.value,
        server_default=TripStatus.SCHEDULED.value,
    )
    actual_start_time: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    actual_end_time  : Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    created_at       : Mapped[datetime]        = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    updated_at       : Mapped[datetime]        = mapped_column(TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_trips_branch_id_school_id_branches",
        ),
        UniqueConstraint(
            "school_id", "branch_id", "route_id", "service_date", "trip_type",
            name="uq_trips_route_date_type",
        ),
        Index("idx_trips_lookup", "school_id", "service_date", "route_id"),
        Index("idx_trips_branch", "branch_id", "school_id"),
    )

    # 1:1 relationship to live status — meaningless without the trip
    live_status: Mapped["TripLiveStatus | None"] = relationship(
        "TripLiveStatus",
        back_populates="trip",
        cascade="save-update, merge",
        lazy="noload",
        uselist=False,
    )

    @property
    def status(self) -> TripStatus:
        return TripStatus(self.trip_status)

    @property
    def type(self) -> TripType:
        return TripType(self.trip_type)

    def __repr__(self) -> str:
        return (
            f"<Trip trip_id={self.trip_id} route={self.route_id} "
            f"date={self.service_date} type={self.trip_type} status={self.trip_status}>"
        )


# -----------------------------------------------------------------------------
# TripLiveStatus
# Maps to: trip_live_status table
# 1:1 with trips — live GPS snapshot updated in real time by driver app / GPS device.
# Rules:
#   - Created when trip transitions to IN_PROGRESS
#   - Hard-deleted automatically when trip is deleted (CASCADE from trip_id FK)
#   - ALWAYS query live position from here — never from gps_logs
#   - last_stop_id nullable — updated as bus passes each stop
#   - ondelete="CASCADE" on trip_id — live status has no meaning without its trip
#   - ondelete="RESTRICT" on school/branch — soft-delete system
# -----------------------------------------------------------------------------
class TripLiveStatus(Base):
    __tablename__ = "trip_live_status"

    live_status_id        : Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id             : Mapped[int]             = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
    branch_id             : Mapped[int]             = mapped_column(Integer, nullable=False)
    trip_id               : Mapped[int]             = mapped_column(Integer, ForeignKey("trips.trip_id", ondelete="CASCADE"), unique=True, nullable=False)
    current_latitude      : Mapped[float]           = mapped_column(Numeric(9, 6), nullable=False)
    current_longitude     : Mapped[float]           = mapped_column(Numeric(9, 6), nullable=False)
    speed                 : Mapped[float | None]    = mapped_column(Numeric(5, 2), nullable=True)
    heading               : Mapped[float | None]    = mapped_column(Numeric(5, 2), nullable=True)
    last_stop_id          : Mapped[int | None]      = mapped_column(Integer, nullable=True)
    last_stop_arrival_time: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    last_updated          : Mapped[datetime]        = mapped_column(TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_trip_live_status_branch_school",
        ),
        ForeignKeyConstraint(
            ["last_stop_id", "branch_id", "school_id"],
            ["stops.stop_id", "stops.branch_id", "stops.school_id"],
            name="fk_trip_live_status_last_stop",
        ),
        Index("idx_live_status_trip", "trip_id"),
        Index("idx_live_status_updated", "last_updated"),
    )

    trip: Mapped["Trip"] = relationship(
        "Trip",
        back_populates="live_status",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<TripLiveStatus trip={self.trip_id} "
            f"lat={self.current_latitude} lon={self.current_longitude} "
            f"updated={self.last_updated}>"
        )