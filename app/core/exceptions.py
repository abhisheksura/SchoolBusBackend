from fastapi import HTTPException, status


# -----------------------------------------------------------------------------
# Base Application Exception
# All custom exceptions inherit from this.
# Allows catching all app-level exceptions in one place if needed.
# -----------------------------------------------------------------------------
class AppException(HTTPException):
    def __init__(self, status_code: int, detail: str, headers: dict | None = None):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


# =============================================================================
# 400 — Bad Request
# =============================================================================
class BadRequestError(AppException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class InvalidStatusTransitionError(BadRequestError):
    def __init__(self, current: str, requested: str):
        super().__init__(
            detail=f"Cannot transition from '{current}' to '{requested}'."
        )


class DuplicateEntryError(BadRequestError):
    def __init__(self, field: str, value: str):
        super().__init__(detail=f"'{value}' is already taken for field '{field}'.")


class InvalidDateRangeError(BadRequestError):
    def __init__(self, detail: str = "start_date must be before end_date."):
        super().__init__(detail=detail)


# =============================================================================
# 401 — Unauthorized
# =============================================================================
class UnauthorizedError(AppException):
    def __init__(self, detail: str = "Authentication required."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class InvalidCredentialsError(UnauthorizedError):
    def __init__(self):
        super().__init__(detail="Invalid username or password.")


class InvalidTokenError(UnauthorizedError):
    def __init__(self, detail: str = "Token is invalid or has expired."):
        super().__init__(detail=detail)


class TokenExpiredError(UnauthorizedError):
    def __init__(self):
        super().__init__(detail="Token has expired. Please log in again.")


class RefreshTokenRevokedError(UnauthorizedError):
    def __init__(self):
        super().__init__(detail="Refresh token has been revoked.")


# =============================================================================
# 403 — Forbidden
# =============================================================================
class ForbiddenError(AppException):
    def __init__(self, detail: str = "You do not have permission to perform this action."):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class InsufficientRoleError(ForbiddenError):
    def __init__(self, required_role: str):
        super().__init__(
            detail=f"This action requires the '{required_role}' role."
        )


class BranchScopeError(ForbiddenError):
    def __init__(self):
        super().__init__(
            detail="You do not have access to this branch."
        )


class SchoolScopeError(ForbiddenError):
    def __init__(self):
        super().__init__(
            detail="You do not have access to this school."
        )


# =============================================================================
# 404 — Not Found
# =============================================================================
class NotFoundError(AppException):
    def __init__(self, resource: str, identifier: int | str | None = None):
        detail = (
            f"{resource} with id '{identifier}' was not found."
            if identifier is not None
            else f"{resource} was not found."
        )
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class UserNotFoundError(NotFoundError):
    def __init__(self, identifier: int | str | None = None):
        super().__init__(resource="User", identifier=identifier)


class SchoolNotFoundError(NotFoundError):
    def __init__(self, identifier: int | str | None = None):
        super().__init__(resource="School", identifier=identifier)


class BranchNotFoundError(NotFoundError):
    def __init__(self, identifier: int | str | None = None):
        super().__init__(resource="Branch", identifier=identifier)


class DriverNotFoundError(NotFoundError):
    def __init__(self, identifier: int | str | None = None):
        super().__init__(resource="Driver", identifier=identifier)


class BusNotFoundError(NotFoundError):
    def __init__(self, identifier: int | str | None = None):
        super().__init__(resource="Bus", identifier=identifier)


class DeviceNotFoundError(NotFoundError):
    def __init__(self, identifier: int | str | None = None):
        super().__init__(resource="GPS Device", identifier=identifier)


class RouteNotFoundError(NotFoundError):
    def __init__(self, identifier: int | str | None = None):
        super().__init__(resource="Route", identifier=identifier)


class StopNotFoundError(NotFoundError):
    def __init__(self, identifier: int | str | None = None):
        super().__init__(resource="Stop", identifier=identifier)


class TripNotFoundError(NotFoundError):
    def __init__(self, identifier: int | str | None = None):
        super().__init__(resource="Trip", identifier=identifier)


class StudentNotFoundError(NotFoundError):
    def __init__(self, identifier: int | str | None = None):
        super().__init__(resource="Student", identifier=identifier)


class ParentNotFoundError(NotFoundError):
    def __init__(self, identifier: int | str | None = None):
        super().__init__(resource="Parent", identifier=identifier)


class AttendanceNotFoundError(NotFoundError):
    def __init__(self, identifier: int | str | None = None):
        super().__init__(resource="Attendance record", identifier=identifier)


class LeaveRequestNotFoundError(NotFoundError):
    def __init__(self, identifier: int | str | None = None):
        super().__init__(resource="Leave request", identifier=identifier)


# =============================================================================
# 409 — Conflict
# =============================================================================
class ConflictError(AppException):
    def __init__(self, detail: str = "Resource conflict."):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class TripAlreadyExistsError(ConflictError):
    def __init__(self):
        super().__init__(
            detail="A trip for this route, date, and trip type already exists."
        )


class DeviceAlreadyAssignedError(ConflictError):
    def __init__(self):
        super().__init__(
            detail="This GPS device is already assigned to an active bus."
        )


class BusAlreadyHasDeviceError(ConflictError):
    def __init__(self):
        super().__init__(
            detail="This bus already has an active GPS device assigned."
        )


class StudentAlreadyAssignedError(ConflictError):
    def __init__(self):
        super().__init__(
            detail="Student is already assigned to a route for this trip type."
        )


# =============================================================================
# 422 — Unprocessable Entity
# Pydantic validation errors are handled automatically by FastAPI,
# but this is for domain-level validation that Pydantic can't catch.
# =============================================================================
class UnprocessableError(AppException):
    def __init__(self, detail: str = "Unprocessable request."):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail
        )


# =============================================================================
# 500 — Internal Server Error
# =============================================================================
class InternalServerError(AppException):
    def __init__(self, detail: str = "An unexpected error occurred."):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )
