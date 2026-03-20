import enum


class RoleName(str, enum.Enum):
    """
    Maps to: role_name_enum
    Scoping rules (enforced via CHECK constraint in user_roles):
      - SUPER_ADMIN  → school_id IS NULL, branch_id IS NULL
      - SCHOOL_ADMIN → school_id IS NOT NULL, branch_id IS NULL
      - others       → school_id IS NOT NULL, branch_id IS NOT NULL
    """
    SUPER_ADMIN  = "SUPER_ADMIN"
    SCHOOL_ADMIN = "SCHOOL_ADMIN"
    BRANCH_ADMIN = "BRANCH_ADMIN"
    DRIVER       = "DRIVER"
    PARENT       = "PARENT"
    STUDENT      = "STUDENT"


class TripType(str, enum.Enum):
    """
    Maps to: trip_type_enum
    Used in: route_stops.trip_type, trips.trip_type,
             student_route_assignments.assignment_type
    A single route has two ordered stop lists — one per TripType.
    """
    PICKUP  = "PICKUP"
    DROPOFF = "DROPOFF"


class TripStatus(str, enum.Enum):
    """
    Maps to: trip_status_enum
    Lifecycle: SCHEDULED → IN_PROGRESS → COMPLETED | CANCELLED
    """
    SCHEDULED   = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED   = "COMPLETED"
    CANCELLED   = "CANCELLED"


class AttendanceStatus(str, enum.Enum):
    """
    Maps to: attendance_status_enum
    Set per student per trip.
      - BOARDED  → student got on the bus (PICKUP trip)
      - DROPPED  → student was dropped off (DROPOFF trip)
      - NO_SHOW  → student did not board at their stop
    """
    BOARDED  = "BOARDED"
    DROPPED  = "DROPPED"
    NO_SHOW  = "NO_SHOW"


class NotificationType(str, enum.Enum):
    """
    Maps to: notification_type_enum
    Determines the content template used when dispatching.
    """
    ATTENDANCE  = "ATTENDANCE"
    TRIP_START  = "TRIP_START"
    TRIP_END    = "TRIP_END"
    DELAY       = "DELAY"
    GENERAL     = "GENERAL"


class NotificationStatus(str, enum.Enum):
    """
    Maps to: notification_status_enum
    Lifecycle: PENDING → SENT | FAILED; SENT → READ
    """
    PENDING = "PENDING"
    SENT    = "SENT"
    FAILED  = "FAILED"
    READ    = "READ"


class NotificationChannel(str, enum.Enum):
    """
    Maps to: channel_enum
    The delivery channel for a notification_log row.
    """
    PUSH      = "PUSH"
    SMS       = "SMS"
    EMAIL     = "EMAIL"
    WHATSAPP  = "WHATSAPP"


class LeaveRequestStatus(str, enum.Enum):
    """
    Maps to: student_leave_request_status_enum
    Lifecycle: PENDING → APPROVED | REJECTED
    Cancel = set to REJECTED, never hard-delete.
    """
    PENDING  = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ---------------------------------------------------------------------------
# Helper sets — used in service layer for state-transition validation
# ---------------------------------------------------------------------------

# Valid transitions for TripStatus
TRIP_STATUS_TRANSITIONS: dict[TripStatus, set[TripStatus]] = {
    TripStatus.SCHEDULED:   {TripStatus.IN_PROGRESS, TripStatus.CANCELLED},
    TripStatus.IN_PROGRESS: {TripStatus.COMPLETED,   TripStatus.CANCELLED},
    TripStatus.COMPLETED:   set(),   # terminal
    TripStatus.CANCELLED:   set(),   # terminal
}

# Valid transitions for LeaveRequestStatus
LEAVE_STATUS_TRANSITIONS: dict[LeaveRequestStatus, set[LeaveRequestStatus]] = {
    LeaveRequestStatus.PENDING:  {LeaveRequestStatus.APPROVED, LeaveRequestStatus.REJECTED},
    LeaveRequestStatus.APPROVED: {LeaveRequestStatus.REJECTED},  # can be revoked
    LeaveRequestStatus.REJECTED: set(),  # terminal
}

# Roles that require branch-level scoping
BRANCH_SCOPED_ROLES: frozenset[RoleName] = frozenset({
    RoleName.BRANCH_ADMIN,
    RoleName.DRIVER,
    RoleName.PARENT,
    RoleName.STUDENT,
})

# Roles that operate at school level only (no branch)
SCHOOL_SCOPED_ROLES: frozenset[RoleName] = frozenset({
    RoleName.SCHOOL_ADMIN,
})