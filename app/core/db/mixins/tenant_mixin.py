class TenantInfoMixin:
    """
    Reusable tenant display helper mixin.

    Provides flattened tenant fields for API responses.

    Requires models to define:
        - self.school relationship
        - self.branch relationship

    Works with:
        Pydantic model_config = ConfigDict(from_attributes=True)
    """

    @property
    def school_name(self) -> str | None:
        """Flatten school.school_name for API responses."""
        return (
            self.school.school_name
            if getattr(self, "school", None)
            else None
        )

    @property
    def branch_name(self) -> str | None:
        """Flatten branch.branch_name for API responses."""
        return (
            self.branch.branch_name
            if getattr(self, "branch", None)
            else None
        )