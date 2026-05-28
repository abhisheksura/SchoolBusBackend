from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import Base, TZDateTime
from app.core.db.mixins.tenant_mixin import TenantInfoMixin
from app.core.enums import TripType


# -----------------------------------------------------------------------------
# Route
# Maps to: routes table
# Logical route — no PICKUP/DROP distinction at this level.
# PICKUP and DROP stop ordering is handled in route_stops.trip_type.
# Rules:
#   - Soft delete only — is_active = False
#   - route_code is unique per (branch_id, school_id)
#   - ondelete="RESTRICT" — soft-delete system, no hard-delete cascade
# -----------------------------------------------------------------------------
class Route(Base):
    __tablename__ = "routes"

    route_id   : Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id  : Mapped[int]        = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
    branch_id  : Mapped[int]        = mapped_column(Integer, nullable=False)
    route_code : Mapped[str]        = mapped_column(String(50), nullable=False)
    route_name : Mapped[str]        = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active  : Mapped[bool]       = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at : Mapped[datetime]   = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    updated_at : Mapped[datetime]   = mapped_column(TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_routes_branch_id_school_id_branches",
        ),
        UniqueConstraint("route_code", "branch_id", "school_id", name="uq_routes_route_code_branch_school"),
        UniqueConstraint("route_id", "branch_id", "school_id", name="uq_routes_route_id_branch_school"),
        Index("idx_routes_school_branch", "school_id", "branch_id"),
    )

    # cascade="save-update, merge" only — soft-delete system
    route_stops: Mapped[list["RouteStop"]] = relationship(
        "RouteStop",
        back_populates="route",
        cascade="save-update, merge",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Route route_id={self.route_id} code={self.route_code} name={self.route_name}>"


# -----------------------------------------------------------------------------
# Stop
# Maps to: stops table
# Physical GPS-tagged bus stop, scoped to a branch.
# Rules:
#   - Soft delete only — is_active = False
#   - stop_name is unique per (branch_id, school_id)
#   - latitude / longitude validated by DB CHECK constraints
#   - ondelete="RESTRICT" — a stop in use by route_stops cannot be deleted
# -----------------------------------------------------------------------------
class Stop(TenantInfoMixin, Base):
    __tablename__ = "stops"

    stop_id   : Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id : Mapped[int]          = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
    branch_id : Mapped[int]          = mapped_column(Integer, nullable=False)
    stop_name : Mapped[str]          = mapped_column(String(255), nullable=False)
    latitude  : Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude : Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    is_active : Mapped[bool]         = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime]     = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime]     = mapped_column(TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_stops_branch_id_school_id_branches",
        ),
        UniqueConstraint("stop_name", "branch_id", "school_id", name="uq_stops_stop_name_branch_school"),
        UniqueConstraint("stop_id", "branch_id", "school_id", name="uq_stops_stop_id_branch_school"),
        CheckConstraint("latitude  BETWEEN -90  AND 90",  name="ck_stops_valid_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_stops_valid_longitude"),
        Index("idx_stops_school_branch", "school_id", "branch_id"),
        Index("idx_stops_lat_lng", "latitude", "longitude"),
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
        primaryjoin="and_(Stop.branch_id == Branch.branch_id, Stop.school_id == Branch.school_id)",
        foreign_keys="[Stop.branch_id, Stop.school_id]",
        lazy="noload",
        viewonly=True,
    )
    # cascade="save-update, merge" only — soft-delete system
    route_stops: Mapped[list["RouteStop"]] = relationship(
        "RouteStop",
        back_populates="stop",
        cascade="save-update, merge",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Stop stop_id={self.stop_id} name={self.stop_name}>"


# -----------------------------------------------------------------------------
# RouteStop
# Maps to: route_stops table
# Ordered stop list per route, split by trip_type (PICKUP / DROPOFF).
# Rules:
#   - A stop cannot appear twice on the same route + trip_type (DB UNIQUE)
#   - stop_sequence must be unique per route + trip_type (DB UNIQUE)
#   - stop_sequence must be > 0 (DB CHECK)
#   - ondelete="CASCADE" from route_id — if a route is hard-deleted, its
#     stop list goes with it. This is intentional: route_stops have no
#     independent meaning without their parent route.
#   - ondelete="RESTRICT" from stop_id — a stop in use cannot be hard-deleted.
# -----------------------------------------------------------------------------
class RouteStop(Base):
    __tablename__ = "route_stops"

    route_stop_id : Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id      : Mapped[int]          = mapped_column(Integer, ForeignKey("routes.route_id", ondelete="CASCADE"), nullable=False)
    stop_id       : Mapped[int]          = mapped_column(Integer, ForeignKey("stops.stop_id", ondelete="RESTRICT"), nullable=False)
    school_id     : Mapped[int]          = mapped_column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False)
    branch_id     : Mapped[int]          = mapped_column(Integer, nullable=False)
    trip_type     : Mapped[TripType]     = mapped_column(
        String(20),
        nullable=False,
    )
    stop_sequence : Mapped[int]          = mapped_column(Integer, nullable=False)
    estimated_time: Mapped[time | None]  = mapped_column(Time, nullable=True)
    created_at    : Mapped[datetime]     = mapped_column(TZDateTime, nullable=False, server_default=func.now())
    updated_at    : Mapped[datetime]     = mapped_column(TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="RESTRICT",
            name="fk_route_stops_branch_id_school_id_branches",
        ),
        CheckConstraint("stop_sequence > 0", name="ck_route_stops_sequence_positive"),
        UniqueConstraint("route_id", "trip_type", "stop_id",       name="uq_route_stops_route_trip_stop"),
        UniqueConstraint("route_id", "trip_type", "stop_sequence", name="uq_route_stops_route_trip_sequence"),
        Index("idx_route_stops_route_type", "route_id", "trip_type"),
    )

    route: Mapped["Route"] = relationship(
        "Route",
        back_populates="route_stops",
        lazy="noload",
    )
    stop: Mapped["Stop"] = relationship(
        "Stop",
        back_populates="route_stops",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<RouteStop id={self.route_stop_id} "
            f"route={self.route_id} stop={self.stop_id} "
            f"type={self.trip_type} seq={self.stop_sequence}>"
        )