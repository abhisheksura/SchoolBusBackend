# 🚌 School Bus Tracker — AI Context File
> Attach this file at the start of every new conversation to resume from where we left off.
> Last Updated: March 2026

---

## 📌 Project Overview

**Project:** School Bus Tracker — Multi-tenant REST API
**Engine:** PostgreSQL (multi-tenant via `school_id` + `branch_id` composite FKs)
**Framework:** FastAPI (async-first)
**ORM:** SQLAlchemy (async) + asyncpg driver
**Auth:** JWT (access + refresh tokens), refresh tokens stored in PostgreSQL
**Schema Reference:** `DatabaseSchema.md` (already discussed and understood in full)

---

## ✅ Tech Stack Decisions (Finalized)

| Concern | Decision |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy async (`create_async_engine`) |
| Driver | `asyncpg` |
| Session | `async_sessionmaker` + `AsyncSession` |
| Auth | JWT — short-lived access tokens (30 min) + long-lived refresh tokens (30 days) |
| Refresh token storage | PostgreSQL (`refresh_tokens` table — to be created in `auth/models.py`) |
| Password hashing | `bcrypt` via `passlib`, wrapped in `run_in_executor` (non-blocking) |
| JWT library | `python-jose[cryptography]` |
| Config | `pydantic-settings` v2 (`model_config = SettingsConfigDict(...)`) |
| Migrations | Alembic |
| Models | Individual `models.py` per domain (not a single shared models file) |
| ORM loading | `selectinload` / `joinedload` only — no lazy loading (incompatible with async) |
| Queries | SQLAlchemy Core-style `select()` — never `session.query()` (legacy sync API) |
| Background tasks | FastAPI `BackgroundTasks` or `asyncio` — no threading |

---

## 🏗️ Folder Structure (Finalized)

```
app/
├── core/                        # Pure shared infrastructure — zero FastAPI imports
│   ├── config.py                ✅ Done
│   ├── enums.py                 ✅ Done
│   ├── exceptions.py            ✅ Done
│   ├── security.py              ✅ Done
│   └── db/
│       ├── __init__.py          ✅ Done
│       ├── base.py              ✅ Done
│       ├── engine.py            ✅ Done
│       └── session.py           ✅ Done
│
├── api/                         # FastAPI-specific layer
│   └── v1/
│       ├── __init__.py          ✅ Done
│       ├── dependencies.py      ✅ Done  ← CurrentUser, require_roles, scope guards
│       └── router.py            ✅ Done  ← aggregates all domain routers as api_router
│
├── auth/                        ⏳ Next
│   ├── __init__.py
│   ├── models.py                ← User, Role, UserRole, RefreshToken ORM models
│   ├── schemas.py               ← Pydantic request/response models
│   ├── service.py               ← login, refresh, logout business logic
│   └── router.py                ← FastAPI routes
│
├── schools/                     ⏳ Pending
│   ├── __init__.py
│   ├── models.py
│   ├── schemas.py
│   ├── service.py
│   └── router.py
│
├── branches/                    ⏳ Pending
│   ├── __init__.py
│   ├── models.py
│   ├── schemas.py
│   ├── service.py
│   └── router.py
│
├── fleet/                       ⏳ Pending
│   ├── __init__.py
│   ├── models.py                ← Bus, Driver, GPSDevice, BusDeviceAssignment
│   ├── schemas.py
│   ├── service.py
│   └── router.py
│
├── routes/                      ⏳ Pending
│   ├── __init__.py
│   ├── models.py                ← Route, Stop, RouteStop
│   ├── schemas.py
│   ├── service.py
│   └── router.py
│
├── trips/                       ⏳ Pending
│   ├── __init__.py
│   ├── models.py                ← Trip, TripLiveStatus, GPSLog
│   ├── schemas.py
│   ├── service.py
│   └── router.py
│
├── students/                    ⏳ Pending
│   ├── __init__.py
│   ├── models.py                ← Student, Parent, StudentParent, StudentLeaveRequest
│   ├── schemas.py
│   ├── service.py
│   └── router.py
│
├── attendance/                  ⏳ Pending
│   ├── __init__.py
│   ├── models.py                ← StudentAttendance, StudentRouteAssignment
│   ├── schemas.py
│   ├── service.py
│   └── router.py
│
├── notifications/               ⏳ Pending
│   ├── __init__.py
│   ├── models.py                ← NotificationLog
│   ├── schemas.py
│   ├── service.py
│   └── router.py
│
└── main.py                      ✅ Done
```

---

---

## 📐 Code Conventions

### General
- All files use **4-space indentation** — no tabs
- Max line length: **100 characters**
- All functions and classes must have **docstrings** (at minimum a one-liner)
- **No magic numbers** — all constants go in `config.py` or as module-level named constants
- **No `print()`** — use Python `logging` module only
- Type hints are **mandatory** on all function signatures (args + return type)

### Naming
| Construct | Convention | Example |
|---|---|---|
| Files | `snake_case` | `student_service.py` |
| Classes | `PascalCase` | `StudentService` |
| Functions / methods | `snake_case` | `get_student_by_id()` |
| Variables | `snake_case` | `school_id` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_PAGE_SIZE` |
| Pydantic schemas | `PascalCase` + suffix | `StudentCreate`, `StudentResponse` |
| ORM models | `PascalCase` singular | `Student`, `Bus`, `Trip` |
| Enums | `PascalCase` | `TripStatus`, `RoleName` |
| Router prefix | `kebab-case` | `/student-route-assignments` |

### Import Order (enforced per file)
```python
# 1. Standard library
import asyncio
from datetime import datetime

# 2. Third-party
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

# 3. Internal — core
from app.core.config import settings
from app.core.enums import TripStatus
from app.core.exceptions import StudentNotFoundError

# 4. Internal — domain
from app.students.models import Student
from app.students.schemas import StudentResponse
```

### Domain File Responsibilities
| File | Responsibility |
|---|---|
| `models.py` | SQLAlchemy ORM models only — no business logic |
| `schemas.py` | Pydantic request/response models only — no DB access |
| `repository.py` | All DB queries (select, insert, update, delete) — no business logic |
| `service.py` | Business logic + orchestration — calls repository, raises exceptions |
| `router.py` | FastAPI routes only — thin layer, delegates to service |

### Router Conventions
- All routers defined as `router = APIRouter()`
- Route functions are thin — validate input, call service, return response
- Never put DB queries directly in router functions
- Always use `status_code` explicitly on every route decorator

```python
# correct
@router.post("/", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    payload: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(RoleName.BRANCH_ADMIN)),
) -> StudentResponse:
    return await student_service.create_student(db, payload, current_user)
```

### Repository Conventions
- Repository functions always take `db: AsyncSession` as first argument
- Only raw DB operations here — no business logic, no exception raising for business rules
- Raise `NotFoundError` variants directly from repository when a required record is missing
- Return `None` for optional lookups (suffix `_or_none`) — let service decide what to do
- **Always use fully qualified method names** — never generic names like `get_by_id` or `get_by_name`

```python
# WRONG — too generic, ambiguous across repositories
async def get_by_id(db, id): ...
async def get_all(db): ...
async def get_by_name(db, name): ...

# CORRECT — fully qualified, self-documenting
async def get_student_by_student_id(db, student_id): ...
async def get_all_students_by_branch(db, school_id, branch_id): ...
async def get_user_by_user_name(db, user_name): ...
async def get_bus_by_bus_id(db, bus_id): ...
async def get_route_by_route_code(db, route_code, school_id, branch_id): ...
async def get_trip_by_trip_id_or_none(db, trip_id): ...     # optional lookup
async def get_refresh_token_by_token_hash(db, token_hash): ...
async def get_all_refresh_tokens_by_user_id(db, user_id): ...
async def get_active_device_assignment_by_bus_id(db, bus_id): ...
```

Full example:
```python
# correct — repository is pure DB access with fully qualified names
async def get_student_by_student_id(db: AsyncSession, student_id: int) -> Student:
    result = await db.execute(
        select(Student).where(Student.student_id == student_id)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise StudentNotFoundError(identifier=student_id)
    return student

async def get_all_students_by_branch(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    limit: int,
    offset: int,
) -> tuple[list[Student], int]:
    query = select(Student).where(
        Student.school_id == school_id,
        Student.branch_id == branch_id,
        Student.is_active == True,
    )
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.limit(limit).offset(offset))
    return result.scalars().all(), total
```

### Service Conventions
- Service functions always take `db: AsyncSession` as first argument
- Services call repository functions — never write raw queries in service
- Services call `await session.flush()` — never `await session.commit()` (handled by `get_db`)
- All business logic, validation, and orchestration lives here

```python
# correct — service orchestrates, repository fetches with fully qualified names
async def assign_student_to_route(
    db: AsyncSession,
    student_id: int,
    route_id: int,
    current_user: CurrentUser,
) -> StudentRouteAssignment:
    student = await student_repo.get_student_by_student_id(db, student_id)
    route = await route_repo.get_route_by_route_id(db, route_id)
    existing = await attendance_repo.get_assignment_by_student_and_route_or_none(db, student_id, route_id)
    if existing:
        raise StudentAlreadyAssignedError()
    return await attendance_repo.create_student_route_assignment(db, student_id, route_id)
```

### Schema Conventions
- Every domain has at minimum: `{Model}Create`, `{Model}Update`, `{Model}Response`
- `Response` schemas always have `model_config = ConfigDict(from_attributes=True)`
- Never expose: `password_hash`, internal FKs not needed by client
- Timestamps (`created_at`, `updated_at`) always included in `Response` schemas

---

## 📬 API Response Format

### Success — Single Object
FastAPI returns the `response_model` directly — no wrapper envelope.
```json
{
    "student_id": 42,
    "school_id": 1,
    "branch_id": 3,
    "first_name": "Aanya",
    "last_name": "Sharma",
    "grade": "5",
    "section": "A",
    "is_active": true,
    "created_at": "2026-01-15T08:30:00Z",
    "updated_at": "2026-01-15T08:30:00Z"
}
```

### Success — Paginated List
All list endpoints return a consistent paginated envelope via shared `PaginatedResponse[T]`:
```json
{
    "items": [ "...array of objects..." ],
    "total": 143,
    "page": 1,
    "page_size": 20,
    "pages": 8
}
```

### Auth Token Response
```json
{
    "access_token": "eyJhbGci...",
    "refresh_token": "eyJhbGci...",
    "token_type": "bearer",
    "expires_in": 1800
}
```

### Error Response (all errors)
```json
{ "detail": "Student with id '42' was not found." }
```

### Validation Error (Pydantic — FastAPI default)
```json
{
    "detail": [
        {
            "type": "missing",
            "loc": ["body", "first_name"],
            "msg": "Field required",
            "input": {}
        }
    ]
}
```

### HTTP Status Codes
| Scenario | Code |
|---|---|
| Successful fetch | `200 OK` |
| Successful create | `201 Created` |
| Successful delete | `204 No Content` |
| Bad request / logic error | `400 Bad Request` |
| Unauthenticated | `401 Unauthorized` |
| Insufficient permissions | `403 Forbidden` |
| Resource not found | `404 Not Found` |
| State conflict | `409 Conflict` |
| Validation error | `422 Unprocessable Entity` |
| Server error | `500 Internal Server Error` |

---

## 🚨 Error Handling Patterns

### The Flow
```
Router → Service → Repository → DB
                ↓
          raises AppException → FastAPI catches → JSON error response
```
Repositories raise `NotFoundError` variants. Services raise business logic exceptions. Routers never catch — FastAPI handles all `HTTPException` subclasses automatically.

### In Service Layer — raise domain exceptions
```python
async def get_bus(db: AsyncSession, bus_id: int, school_id: int, branch_id: int) -> Bus:
    result = await db.execute(
        select(Bus).where(
            Bus.bus_id == bus_id,
            Bus.school_id == school_id,
            Bus.branch_id == branch_id,
        )
    )
    bus = result.scalar_one_or_none()
    if not bus:
        raise BusNotFoundError(identifier=bus_id)
    return bus
```

### In Router Layer — no try/except, no error handling
```python
@router.get("/{bus_id}", response_model=BusResponse)
async def get_bus(
    bus_id: int,
    school_id: int,
    branch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BusResponse:
    check_branch_access(current_user, school_id, branch_id)
    return await fleet_service.get_bus(db, bus_id, school_id, branch_id)
```

### Database Integrity Errors — catch in service, convert to domain exception
```python
from sqlalchemy.exc import IntegrityError

try:
    db.add(new_bus)
    await db.flush()
except IntegrityError:
    raise DuplicateEntryError(field="bus_number", value=payload.bus_number)
```

### State Transition Validation — use transition maps from `core/enums.py`
```python
if new_status not in TRIP_STATUS_TRANSITIONS[trip.trip_status]:
    raise InvalidStatusTransitionError(
        current=trip.trip_status.value,
        requested=new_status.value,
    )
```

### Tenant Scope Validation — always at the start of route handlers
```python
check_school_access(current_user, school_id)   # school-scoped routes
check_branch_access(current_user, school_id, branch_id)  # branch-scoped routes
```

---

## ❓ Open Decisions / TODOs

| # | Decision | Status | Notes |
|---|---|---|---|
| 1 | `core/schemas.py` — shared `PaginatedResponse[T]` + `TimestampMixin` | ⏳ To be created | Needed before first list endpoint |
| 2 | Alembic setup — `alembic.ini` + `env.py` async config | ⏳ To be done | Do after all models are written |
| 3 | Logging setup — format, level, handlers | ⏳ Not decided | Will add to `main.py` lifespan |
| 4 | Rate limiting — login endpoint especially | ⏳ Not decided | `slowapi` library likely |
| 5 | GPS log ingestion — dedicated endpoint or WebSocket? | ⏳ Not decided | High-volume, needs benchmarking |
| 6 | Push notification provider — FCM, OneSignal, other? | ⏳ Not decided | Affects `notifications/service.py` |
| 7 | `is_active` enforcement on every request | ⏳ Not decided | Currently token presence is sufficient |
| 8 | Soft delete pattern — consistent `is_active` flag across all domains | ⏳ Not decided | All tables have `is_active` |
| 9 | Dockerfile + docker-compose setup | ⏳ Pending | Do after all domains complete |

---

## 📁 Completed Files — Key Details

### `app/core/config.py`
- Uses `pydantic-settings` v2 with `model_config = SettingsConfigDict(...)`
- `DATABASE_URL` is a `@property` that composes individual `DB_*` fields into async DSN
- DSN format: `postgresql+asyncpg://user:password@host:port/dbname`
- `JWT_SECRET_KEY` falls back to `secrets.token_urlsafe(64)` if not set in `.env`
- `ALLOWED_ORIGINS` validator splits comma-separated string into list
- Singleton: `settings = Settings()` — import and use everywhere
- Notable settings: `DB_POOL_PRE_PING=True`, `GPS_STALE_THRESHOLD_SECONDS=60`, `GPS_MIN_ACCURACY_METERS=50.0`

### `app/core/enums.py`
- All 8 DB enums mirrored as `str, enum.Enum` (serializes to string in Pydantic/SQLAlchemy)
- Enums: `RoleName`, `TripType`, `TripStatus`, `AttendanceStatus`, `NotificationType`, `NotificationStatus`, `NotificationChannel`, `LeaveRequestStatus`
- Helper sets at bottom: `TRIP_STATUS_TRANSITIONS`, `LEAVE_STATUS_TRANSITIONS`, `BRANCH_SCOPED_ROLES`, `SCHOOL_SCOPED_ROLES`
- Used by service layer for state-transition validation

### `app/core/exceptions.py`
- Three-level hierarchy: `AppException → HTTPException` (FastAPI handles natively)
- `NotFoundError` is generic — takes `resource` name + optional `identifier`
- Domain-specific errors: `StudentNotFoundError`, `TripNotFoundError`, etc.
- `UnauthorizedError` includes `WWW-Authenticate: Bearer` header (HTTP spec requirement)
- 400 (Bad Request), 401 (Unauthorized), 403 (Forbidden), 404 (Not Found), 409 (Conflict), 422 (Unprocessable), 500 (Internal Server Error)

### `app/core/security.py`
- `hash_password` / `verify_password` — bcrypt wrapped in `run_in_executor` (non-blocking)
- `create_access_token(user_id, user_name, roles)` — embeds full role list with school/branch scope
- `create_refresh_token(user_id)` — contains only `user_id`, no role data
- `decode_access_token` / `decode_refresh_token` — validates signature, expiry, and token type
- `extract_user_id(payload)` — parses `sub` claim (stored as string) back to int
- Access token payload includes: `sub`, `user_name`, `roles[]`, `type`, `iat`, `exp`
- Refresh token payload includes: `sub`, `type`, `iat`, `exp`

### `app/core/db/base.py`
- `NAMING_CONVENTION` dict for consistent Alembic constraint names
- `Base(DeclarativeBase)` with `MetaData(naming_convention=...)` — imported by all domain models

### `app/core/db/engine.py`
- `create_async_engine` with all pool settings from `settings`
- `AsyncSessionFactory` — `async_sessionmaker` with `expire_on_commit=False`, `autoflush=False`

### `app/core/db/session.py`
- `get_db()` — async generator, yields `AsyncSession`
- try/commit → except/rollback → finally/close pattern
- Return type: `AsyncGenerator[AsyncSession, None]`

### `app/core/db/__init__.py`
- Re-exports: `Base`, `engine`, `AsyncSessionFactory`, `get_db`
- All other files import from `app.core.db` (not internal submodules)

### `app/api/v1/dependencies.py`
- `bearer_scheme = HTTPBearer(auto_error=False)` — raises own 401 not FastAPI's 403
- `CurrentUser` class — populated from JWT payload, no DB hit
  - `has_role()`, `has_any_role()` — role checks
  - `has_school_access(school_id)` — SUPER_ADMIN passes all
  - `has_branch_access(school_id, branch_id)` — SUPER_ADMIN + SCHOOL_ADMIN pass all
  - `get_accessible_school_ids()` — returns `None` for SUPER_ADMIN (means all)
  - `get_accessible_branch_ids(school_id)` — returns `None` for SUPER_ADMIN + SCHOOL_ADMIN
- `get_current_user()` — core auth dependency
- `require_roles(*roles)` — factory returning a dependency
- `check_school_access()` / `check_branch_access()` — helpers for use inside route handlers
- Pre-built: `SuperAdminRequired`, `SchoolAdminRequired`, `BranchAdminRequired`, `AnyAuthenticated`

### `app/api/v1/router.py`
- `api_router = APIRouter(prefix="/api/v1")`
- All domain routers are commented out — uncomment as each domain is built
- Imported in `main.py` as `from app.api.v1.router import api_router`

### `app/main.py`
- `lifespan` context manager — replaces deprecated `@app.on_event`
- `Base.metadata.create_all` only runs in `ENVIRONMENT=development`
- `create_app()` factory pattern — clean for testing
- Docs (`/docs`, `/redoc`, `/openapi.json`) disabled in production
- CORS middleware configured from `settings.ALLOWED_ORIGINS`
- Health check at `GET /health`
- `engine.dispose()` on shutdown — graceful connection pool cleanup
- Uvicorn target: `app.main:app`

---

## ⏭️ Next Up — `auth/` Domain

### Order of implementation:
1. `auth/models.py` — ORM models:
   - `User` (maps to `users` table)
   - `Role` (maps to `roles` table)
   - `UserRole` (maps to `user_roles` table — RBAC join table)
   - `RefreshToken` (new table — stores hashed refresh tokens with expiry)

2. `auth/schemas.py` — Pydantic models:
   - `LoginRequest`, `TokenResponse`, `RefreshRequest`
   - `UserCreate`, `UserResponse`

3. `auth/service.py` — Business logic:
   - `login()` — verify credentials, issue access + refresh tokens
   - `refresh()` — validate refresh token, issue new access token
   - `logout()` — revoke refresh token
   - `logout_all()` — revoke all refresh tokens for a user

4. `auth/router.py` — FastAPI routes:
   - `POST /auth/login`
   - `POST /auth/refresh`
   - `POST /auth/logout`
   - `POST /auth/logout-all`

---

## 📦 Dependencies to Install

```txt
fastapi
uvicorn[standard]
sqlalchemy[asyncio]
asyncpg
alembic
pydantic-settings
python-jose[cryptography]
passlib[bcrypt]
```

---

## 🔑 Key Async Rules (Enforce in Every File)

| Concern | Rule |
|---|---|
| Route functions | Always `async def` |
| Service functions | Always `async def` |
| Repository functions | Always `async def` |
| DB operations | `await session.execute(select(...))` — never `session.query()` |
| ORM loading | `selectinload` / `joinedload` — never lazy load |
| Blocking I/O | Always wrap in `asyncio.get_event_loop().run_in_executor()` |
| Session commits | Handled by `get_db()` — repositories call `await session.flush()` only |
| Password hashing | `await hash_password()` / `await verify_password()` (non-blocking) |

---

## 🗄️ Database Schema Reference

All 21 tables are defined in `DatabaseSchema.md`. Key tables per domain:

| Domain | Tables |
|---|---|
| auth | `users`, `roles`, `user_roles` + new `refresh_tokens` |
| schools | `schools` |
| branches | `branches` |
| fleet | `buses`, `drivers`, `gps_devices`, `bus_device_assignments` |
| routes | `routes`, `stops`, `route_stops` |
| trips | `trips`, `trip_live_status`, `gps_logs` |
| students | `students`, `parents`, `student_parents`, `student_leave_requests` |
| attendance | `student_attendance`, `student_route_assignments` |
| notifications | `notification_logs` |
