"""
app/core/db/mixins/tenant_mixin.py
===================================
Reusable tenant display helper mixin.

Provides flattened school_name and branch_name properties for API responses,
so callers don't have to traverse nested objects.

Requirements for any model that uses this mixin:
    1. Define a `school` relationship  (selectinload-friendly)
    2. Define a `branch` relationship  (selectinload-friendly)

Both relationships must be loaded before accessing these properties.
If the relationships were not eager-loaded, the properties return None
rather than raising AttributeError — safe for partial loads (e.g. list views
that don't join school/branch for performance).

Works automatically with:
    Pydantic model_config = ConfigDict(from_attributes=True)
    — Pydantic reads @property as a regular attribute during serialization.
"""

from __future__ import annotations


class TenantInfoMixin:
    """
    Adds school_name and branch_name computed properties to any ORM model.

    Usage:
        class Bus(TenantInfoMixin, Base):
            __tablename__ = "buses"
            ...
            school: Mapped["School"] = relationship("School", lazy="noload")
            branch: Mapped["Branch"] = relationship("Branch", lazy="noload")

    Then in repository — load with selectinload before serializing:
        select(Bus).options(
            selectinload(Bus.school),
            selectinload(Bus.branch),
        )

    In Pydantic response schema — declare as optional str:
        school_name: str | None = None
        branch_name: str | None = None
    """

    @property
    def school_name(self) -> str | None:
        """
        Flatten school.school_name for API responses.
        Returns None if the school relationship was not loaded.
        """
        school = getattr(self, "school", None)
        if school is None:
            return None
        return getattr(school, "school_name", None)

    @property
    def branch_name(self) -> str | None:
        """
        Flatten branch.branch_name for API responses.
        Returns None if the branch relationship was not loaded.
        """
        branch = getattr(self, "branch", None)
        if branch is None:
            return None
        return getattr(branch, "branch_name", None)