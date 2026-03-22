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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM

from app.core.db.base import Base, TZDateTime
from app.core.enums import RoleName
from app.core.utils import utcnow


# -----------------------------------------------------------------------------
# User
# Maps to: users table
# Central authentication table — every login goes through here.
# No role stored here — roles are managed through user_roles.
# Rules:
#   - Soft delete only — set is_active = False, never hard delete
#   - Never expose password_hash in any API response
# -----------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_name: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    email: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True, unique=True
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
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
    # Users are soft-deleted (is_active = False), never hard-deleted via ORM.
    # DB-level ON DELETE CASCADE handles physical cleanup if a raw SQL DELETE
    # is ever run directly — that is a conscious DBA action, not app code.
    # -------------------------------------------------------------------------
    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="user",
        cascade="save-update, merge",
        lazy="noload",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="save-update, merge",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<User user_id={self.user_id} user_name={self.user_name}>"


# -----------------------------------------------------------------------------
# Role
# Maps to: roles table
# Seeded once at DB init — never changes at runtime.
# Seed values: SUPER_ADMIN, SCHOOL_ADMIN, BRANCH_ADMIN, DRIVER, PARENT, STUDENT
# -----------------------------------------------------------------------------
class Role(Base):
    __tablename__ = "roles"

    role_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    role_name: Mapped[RoleName] = mapped_column(
        ENUM(RoleName, name="role_name_enum", create_type=False),
        nullable=False,
        unique=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    # -------------------------------------------------------------------------
    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="role",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Role role_id={self.role_id} role_name={self.role_name}>"


# -----------------------------------------------------------------------------
# UserRole
# Maps to: user_roles table
# RBAC join table — one user can hold multiple roles across different
# schools and branches.
#
# Scoping rules (mirrors DB CHECK constraint):
#   SUPER_ADMIN  → school_id IS NULL,     branch_id IS NULL
#   SCHOOL_ADMIN → school_id IS NOT NULL, branch_id IS NULL
#   others       → school_id IS NOT NULL, branch_id IS NOT NULL
# -----------------------------------------------------------------------------
class UserRole(Base):
    __tablename__ = "user_roles"

    user_role_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("roles.role_id"),
        nullable=False,
    )
    school_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("schools.school_id", ondelete="CASCADE"),
        nullable=True,
    )
    branch_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    role_name: Mapped[RoleName] = mapped_column(
        ENUM(RoleName, name="role_name_enum", create_type=False),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    assigned_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # -------------------------------------------------------------------------
    # Constraints — mirrors DB CHECK constraint exactly
    # -------------------------------------------------------------------------
    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "school_id"],
            ["branches.branch_id", "branches.school_id"],
            ondelete="CASCADE",
            name="fk_user_roles_branch_id_school_id_branches",
        ),
        CheckConstraint(
            """
            (role_name = 'SUPER_ADMIN'  AND school_id IS NULL     AND branch_id IS NULL) OR
            (role_name = 'SCHOOL_ADMIN' AND school_id IS NOT NULL AND branch_id IS NULL) OR
            (role_name IN ('BRANCH_ADMIN', 'DRIVER', 'PARENT', 'STUDENT')
                AND school_id IS NOT NULL AND branch_id IS NOT NULL)
            """,
            name="ck_user_roles_scope",
        ),
        Index("idx_user_roles_user_id", "user_id"),
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user: Mapped["User"] = relationship(
        "User",
        back_populates="user_roles",
        lazy="noload",
    )
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="user_roles",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<UserRole user_role_id={self.user_role_id} "
            f"user_id={self.user_id} role_name={self.role_name}>"
        )


# -----------------------------------------------------------------------------
# RefreshToken
# New table — not in DatabaseSchema.md.
# Stores SHA-256 hash of the raw refresh token — never the raw token itself.
# Active token: revoked_at IS NULL
# Revoked token: revoked_at IS NOT NULL
# -----------------------------------------------------------------------------
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    token_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        Text, nullable=False, unique=True
    )
    issued_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        TZDateTime, nullable=True, default=None
    )
    device_info: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    __table_args__ = (
        Index("idx_refresh_tokens_user_id", "user_id"),
        Index("idx_refresh_tokens_active", "user_id", "revoked_at"),
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user: Mapped["User"] = relationship(
        "User",
        back_populates="refresh_tokens",
        lazy="noload",
    )

    @property
    def is_active(self) -> bool:
        """Return True if the token has not been revoked."""
        return self.revoked_at is None

    @property
    def is_expired(self) -> bool:
        """
        Return True if the token has passed its expiry time.
        Both utcnow() and expires_at are timezone-aware (TIMESTAMPTZ) —
        comparison is always correct regardless of server timezone.
        """
        return utcnow() > self.expires_at

    def __repr__(self) -> str:
        return (
            f"<RefreshToken token_id={self.token_id} "
            f"user_id={self.user_id} active={self.is_active}>"
        )