# 🚌 School Bus Tracker — AI Context File
> Attach this file at the start of every new conversation to resume from where we left off.
> Last Updated: March 2026

---

## 📌 Project Overview
|   |   |
|---|---|
| **Project:** | School Bus Tracker — Multi-tenant REST API |
| **Engine:** | PostgreSQL (multi-tenant via `school_id` + `branch_id` composite FKs) |
| **Framework:** | FastAPI (async-first) |
| **ORM:** | SQLAlchemy (async) + asyncpg driver |
| **Auth:** | JWT (access + refresh tokens), refresh tokens stored in PostgreSQL |
| **Schema Reference:** | `DatabaseSchema.md` (already discussed and understood in full) |

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
| Data access pattern | Repository pattern — dedicated `repository.py` per domain |
| Multi-tenancy | PostgreSQL RLS + ORM auto-filter + JWT-derived scope — three-layer isolation |

---

## 🏗️ Folder Structure (Finalized)
```
app/
├── core/                        # Pure shared infrastructure — zero FastAPI imports
│   ├── config.py                ✅ Done
│   ├── enums.py                 ✅ Done
│   ├── exceptions.py            ✅ Done
|   ├── schemas.py               ✅ Done
│   ├── security.py              ✅ Done
│   ├── utils.py                 ✅ Done  ← utcnow()
│   └── db/
│       ├── __init__.py          ✅ Done
│       ├── base.py              ✅ Done
│       ├── engine.py            ✅ Done
│       ├── session.py           ✅ Done  ← get_db() for auth routes ONLY
│       └── tenant.py            ✅ Done  ← TenantContext, get_tenant_db, build_tenant_dep, ORM filter
│
├── api/                         # FastAPI-specific layer
│   └── v1/
│       ├── __init__.py          ✅ Done
│       ├── dependencies.py      ✅ Done  ← CurrentUser, require_roles, scope guards
│       ├── router.py            ✅ Done  ← aggregates all domain routers as api_router
│       ├── auth.py              ✅ Done  ← auth HTTP routes
│       ├── schools.py           ⏳ Pending
│       ├── fleet.py             ⏳ Pending
│       ├── drivers.py           ✅ Done
│       ├── gps.py               ✅ Done
│       ├── routes.py            ⏳ Pending
│       ├── trips.py             ⏳ Pending
│       ├── students.py          ⏳ Pending
│       ├── assignments.py       ✅ Done
│       ├── attendance.py        ⏳ Pending
│       └── notifications.py     ⏳ Pending
│
├── auth/                        ✅ Done
│   ├── __init__.py
│   ├── models.py                ← User, Role, UserRole, RefreshToken ORM models
│   ├── schemas.py               ← LoginRequest (platform+role fields), TokenResponse, MeResponse
│   ├── repository.py            ← all auth DB queries
│   └── service.py               ← login() validates platform+role against PLATFORM_ROLES
│
├── schools/                     ✅ Done
│   ├── __init__.py
│   ├── models.py                ← School, Branch
│   ├── schemas.py
│   ├── repository.py
│   └── service.py
│
├── fleet/                       ✅ Done
│   ├── __init__.py
│   ├── models.py                ← Bus
│   ├── schemas.py
│   ├── repository.py
│   └── service.py
│
├── drivers/                     ✅ Done  ← split out from fleet
│   ├── __init__.py
│   ├── models.py                ← Driver
│   ├── schemas.py
│   ├── repository.py
│   └── service.py
│
├── gps/                         ✅ Done  ← split out from fleet
│   ├── __init__.py
│   ├── models.py                ← GPSDevice, BusDeviceAssignment
│   ├── schemas.py
│   ├── repository.py
│   └── service.py
│
├── routes/                      ⏳ Pending
│   ├── __init__.py
│   ├── models.py                ← Route, Stop, RouteStop
│   ├── schemas.py
│   ├── repository.py
│   └── service.py
│
├── trips/                       ⏳ Pending
│   ├── __init__.py
│   ├── models.py                ← Trip, TripLiveStatus
│   ├── schemas.py
│   ├── repository.py
│   └── service.py
│
├── students/                    ⏳ Pending
│   ├── __init__.py
│   ├── models.py                ← Student, Parent, StudentParent, StudentLeaveRequest
│   ├── schemas.py
│   ├── repository.py
│   └── service.py
│
├── assignments/                 ✅ Done  ← StudentRouteAssignment ONLY
│   ├── __init__.py
│   ├── models.py
│   ├── schemas.py
│   ├── repository.py
│   └── service.py
│
├── attendance/                  ⏳ Pending
│   ├── __init__.py
│   ├── models.py                ← StudentAttendance, StudentRouteAssignment
│   ├── schemas.py
│   ├── repository.py
│   └── service.py
│
├── notifications/               ⏳ Pending
│   ├── __init__.py
│   ├── models.py                ← NotificationLog
│   ├── schemas.py
│   ├── repository.py
│   └── service.py
│
└── main.py                      ✅ Done

alembic/
└── versions/
    └── rls_policies.py          ✅ Done  ← RLS for all 20+ tables + partial unique indexes
```

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
| `{domain}/models.py` | SQLAlchemy ORM models only — no business logic |
| `{domain}/schemas.py` | Pydantic request/response models only — no DB access |
| `{domain}/repository.py` | All DB queries (select, insert, update, delete) — no business logic |
| `{domain}/service.py` | Business logic + orchestration — calls repository, raises exceptions |
| `api/v1/{domain}.py` | FastAPI routes only — thin layer, delegates to service |
 
> Note: `router.py` no longer lives inside domain folders.
> All HTTP route files live in `app/api/v1/` named after their domain (e.g. `auth.py`, `schools.py`).

### Router Conventions
- All routers defined as `router = APIRouter()`
- Route functions are thin — validate input, call service, return response
- Never put DB queries directly in router functions
- Always use `status_code` explicitly on every route decorator

```python
# Non-auth route — CORRECT: uses build_tenant_dep for RLS
from app.core.db.tenant import build_tenant_dep
from app.api.v1.dependencies import AnyAuthenticated, require_roles
 
TenantDB = build_tenant_dep(AnyAuthenticated)
 
@router.get("/buses/", response_model=PaginatedBusResponse, status_code=status.HTTP_200_OK)
async def list_buses(
    school_id: int = Query(...),
    branch_id: int = Query(...),
    db: AsyncSession = TenantDB,
    current_user: CurrentUser = AnyAuthenticated,
) -> PaginatedBusResponse:
    return await fleet_service.get_all_buses(db, current_user, school_id, branch_id)
 
# Auth route — CORRECT: uses plain get_db (no tenant context yet)
@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await auth_service.login(db, payload.user_name, payload.password, payload.platform, payload.role)
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

### Multi-Tenant Repository Pattern (CRITICAL)
All list/lookup repository functions that scope by tenant follow this pattern:
 
```python
async def get_all_buses(
    db: AsyncSession,
    school_id: int | None,              # None = SUPER_ADMIN (no school filter)
    branch_id: int | None,              # None = SUPER_ADMIN or SCHOOL_ADMIN
    accessible_branch_ids: list[int] | None,  # None = no filter, [] = no access
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Bus], int]:
    query = select(Bus)
    if school_id is not None:
        query = query.where(Bus.school_id == school_id)
    # 🔐 Branch-level security filter
    if accessible_branch_ids is not None:
        query = query.where(Bus.branch_id.in_(accessible_branch_ids))
    elif branch_id is not None:
        query = query.where(Bus.branch_id == branch_id)
    if active_only:
        query = query.where(Bus.is_active == True)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(Bus.bus_number).limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0
```
 
Tenant context values come from `current_user` in the service layer — **never from client request body**.
 

### Service Conventions
- Service functions always take `db: AsyncSession` as first argument
- Services accept **primitives only** — no `CurrentUser` objects, no HTTP objects
- Services call repository functions — never write raw queries in service
- All business logic, validation, orchestration, and scope checks live here
- **Scope check BEFORE DB hit** — never fetch a row then reject based on tenant


```python
async def get_bus(
    db: AsyncSession,
    bus_id: int,
    school_id: int | None,
    branch_id: int | None,
    accessible_branch_ids: list[int] | None,
) -> BusResponse:
    # Scope check first — no DB hit if user has no access
    if accessible_branch_ids is not None and (branch_id is None or branch_id not in accessible_branch_ids):
        raise BusNotFoundError(identifier=bus_id)  # 404, not 403 — don't reveal existence
    bus = await fleet_repo.get_bus_by_bus_id(db, bus_id, school_id, branch_id)
    return BusResponse.model_validate(bus)
```

### Schema Conventions
- Every domain has at minimum: `{Model}Create`, `{Model}Update`, `{Model}Response`
- `Response` schemas always have `model_config = ConfigDict(from_attributes=True)`
- Never expose: `password_hash`, internal FKs not needed by client
- Timestamps (`created_at`, `updated_at`) always included in `Response` schemas
- `PATCH` schemas use `exclude_unset=True` — never `exclude_none`

---
## 🔐 Authentication & Login
 
### Login Request (Updated)
`POST /api/v1/auth/login` requires `platform` **and** `role`:
 
```json
{
    "user_name": "john",
    "password": "secret",
    "platform": "web",
    "role": "SCHOOL_ADMIN",
    "device_info": "Chrome/125 Windows"
}
```
 
**Two-layer validation:**
 
**Layer 1 — Pydantic (422, before DB):**
- `platform` must be `"web"` or `"mobile"` (regex pattern)
- `role` must be a valid `RoleName` enum value
- `@model_validator` cross-checks: `role` must be in `PLATFORM_ROLES[platform]`
  - `"web"` → `{SUPER_ADMIN, SCHOOL_ADMIN, BRANCH_ADMIN}`
  - `"mobile"` → `{DRIVER, STUDENT}`
**Layer 2 — Service (401, after DB):**
- Correct credentials but declared role not held by user → `401 "This account does not have the specified role."`
- Correct credentials, correct role, wrong platform → already caught by Layer 1
**Examples rejected:**
- SUPER_ADMIN logging in with `role="SCHOOL_ADMIN"` → 401 (doesn't hold that role)
- SCHOOL_ADMIN logging in with `role="SUPER_ADMIN"` → 401 (doesn't hold that role)
- DRIVER on `platform="web"` with `role="DRIVER"` → 422 (DRIVER not in web platform roles)
**Token contains only the declared role's assignments** — a SCHOOL_ADMIN user who manages two schools gets both assignments embedded, but no other role types.
 
### JWT Payload Structure
```json
{
    "sub": "42",
    "user_name": "john",
    "role": "SCHOOL_ADMIN",
    "school_id": 3,
    "branch_id": null,
    "roles": [
        { "role_name": "SCHOOL_ADMIN", "school_id": 3, "branch_id": null }
    ],
    "type": "access",
    "iat": 1710000000,
    "exp": 1710001800
}
```
 
| Claim | SUPER_ADMIN | SCHOOL_ADMIN | BRANCH_ADMIN / DRIVER / STUDENT |
|---|---|---|---|
| `role` | `"SUPER_ADMIN"` | `"SCHOOL_ADMIN"` | their role |
| `school_id` | `null` | their school PK | their school PK |
| `branch_id` | `null` | `null` | their branch PK |
 
> **RULE:** Never trust client-provided `school_id` or `branch_id` for security decisions. Always derive from JWT (`current_user.school_id`, `current_user.branch_id`).
 
---
 
## 🔒 Multi-Tenancy — Three Isolation Layers
 
### Layer 1: Application (service + repository)
Scope derived from JWT via `CurrentUser`. Service passes `accessible_branch_ids` from `current_user.get_accessible_branch_ids(school_id)` to repository.
 
`get_accessible_branch_ids(school_id)`:
- `None` → SUPER_ADMIN or SCHOOL_ADMIN — no branch filter
- `[branch_id]` → BRANCH_ADMIN/DRIVER/STUDENT — single branch
- `[]` → user has no access to this school — raise 404
### Layer 2: ORM Auto-filter (defence in depth)
`_attach_orm_filter` in `core/db/tenant.py` listens on `do_orm_execute` and transparently appends `WHERE school_id = X [AND branch_id = Y]` to every ORM SELECT. Prevents accidental data leaks even if service code forgets a filter.
 
### Layer 3: PostgreSQL RLS
Every tenant-aware table has `ENABLE ROW LEVEL SECURITY` + policies. SET LOCAL session variables per transaction:
```sql
set_config('app.user_id',   '42',           true)  -- LOCAL to transaction
set_config('app.user_role', 'SCHOOL_ADMIN', true)
set_config('app.school_id', '3',            true)
set_config('app.branch_id', '0',            true)   -- '0' when null
```
`true` = LOCAL — auto-cleared when transaction ends. Safe with pgBouncer/asyncpg pools.
 
### Session Dependency — which to use
| Route type | Dependency | Reason |
|---|---|---|
| Auth routes (`/login`, `/refresh`, `/logout`, `/me`) | `get_db` | No tenant context yet |
| All other routes | `build_tenant_dep(auth_dep)` | Sets RLS variables before any query |
 
```python
# In router.py for non-auth domains:
from app.core.db.tenant import build_tenant_dep
from app.api.v1.dependencies import AnyAuthenticated, require_roles
 
TenantDB      = build_tenant_dep(AnyAuthenticated)
AdminTenantDB = build_tenant_dep(require_roles(RoleName.BRANCH_ADMIN))
```
 
### DB User (CRITICAL)
Application must connect as a **non-superuser**. Superusers bypass RLS.
```sql
CREATE ROLE app_user LOGIN PASSWORD '...';
-- GRANT SELECT, INSERT, UPDATE, DELETE on all tables to app_user
-- Do NOT grant BYPASSRLS
```
 
> Full guide: `docs/MultiTenancy.md`

---

## 📬 API Response Format
 
### Success — Single Object
FastAPI returns the `response_model` directly — no wrapper envelope.
```json
{
    "bus_id": 1,
    "school_id": 1,
    "branch_id": 3,
    "bus_number": "TN01AB1234",
    "capacity": 40,
    "is_active": true,
    "created_at": "2026-01-15T08:30:00Z",
    "updated_at": "2026-01-15T08:30:00Z"
}
```
 
### Success — Paginated List
All list endpoints return a consistent paginated envelope via `PaginatedResponse[T]`:
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
        { "type": "missing", "loc": ["body", "first_name"], "msg": "Field required", "input": {} }
    ]
}
```

### HTTP Status Codes
| Scenario | Code |
|---|---|
| Successful fetch | `200 OK` |
| Successful create | `201 Created` |
| Successful soft-delete | `200 OK` + deactivated object |
| Successful unlink (hard delete link row) | `204 No Content` |
| Bad request / logic error | `400 Bad Request` |
| Unauthenticated | `401 Unauthorized` |
| Insufficient permissions | `403 Forbidden` |
| Resource not found / scope violation on GET | `404 Not Found` |
| Scope violation on POST/PATCH/DELETE | `403 Forbidden` |
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


```python
# GET — scope violation returns 404
async def get_school(db, school_id, accessible_school_ids):
    if accessible_school_ids is not None and school_id not in accessible_school_ids:
        raise SchoolNotFoundError(identifier=school_id)  # 404, not 403
    return await school_repo.get_school_by_school_id(db, school_id)
 
# POST/PATCH/DELETE — scope violation returns 403
async def update_school(db, school_id, payload, accessible_school_ids):
    if accessible_school_ids is not None and school_id not in accessible_school_ids:
        raise ForbiddenError()  # 403
```

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
- **Read endpoints** (`GET`) → return `404` on scope violation — never reveals existence of other tenants' data
- **Write endpoints** (`POST`, `PATCH`, `DELETE`) → return `403` on scope violation — admin already knows the resource exists
 
```python
# GET — scope violation returns 404
async def get_school(db, school_id, current_user):
    school = await school_repo.get_school_by_school_id(db, school_id)  # 404 if not found
    if not current_user.has_school_access(school_id):
        raise SchoolNotFoundError(identifier=school_id)  # 404, not 403
    return school
 
# POST/PATCH/DELETE — scope violation returns 403
async def update_school(db, school_id, payload, current_user):
    if not current_user.has_role(RoleName.SUPER_ADMIN):
        raise ForbiddenError()  # 403
    ...
```
---
 
## 🔑 Key Rules (Enforce in Every File)
 
| Concern | Rule |
|---|---|
| Route functions | Always `async def` |
| Service functions | Always `async def` |
| Repository functions | Always `async def` |
| DB operations | `await session.execute(select(...))` — never `session.query()` |
| ORM loading | `selectinload` / `joinedload` — never lazy load (`lazy="noload"` on all relationships) |
| Blocking I/O | Always wrap in `asyncio.get_event_loop().run_in_executor()` |
| Session commits | Handled by `get_db` / `get_tenant_db` — repositories call `await session.flush()` only |
| Password hashing | `await hash_password()` / `await verify_password()` (non-blocking) |
| Datetime | Always use `utcnow()` from `app.core.utils` — never `datetime.utcnow()` or `datetime.now()` |
| Timestamps | All DB columns use `TIMESTAMPTZ` — `TZDateTime = TIMESTAMP(timezone=True)` from `app.core.db.base` |
| UPDATE queries | Use `UPDATE ... RETURNING Model` — single round-trip, no stale identity map |
| ORM cascade | Always `cascade="save-update, merge"` only — NEVER `"all"`, `"delete"`, or `"delete-orphan"` |
| Soft deletes | Always `is_active = False` — never `db.delete(obj)` in application code |
| Scope check order | Always check scope BEFORE hitting the DB — never fetch then reject |
| Service layer | Services accept primitives only — no `CurrentUser`, no HTTP objects |
| Role enforcement | `require_roles()` at the router — services never check roles directly |
| Tenant context | ALWAYS derive from JWT (`current_user`) — never trust client-provided `school_id`/`branch_id` |
| Non-auth sessions | Use `build_tenant_dep()` — never use plain `get_db()` on tenant-aware routes |
| DB user | Application DB user must NOT be superuser — superusers bypass RLS |
| PATCH updates | Use `model_dump(exclude_unset=True)` — not `exclude_none` |

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
 
### Key Design Decisions
 
| Decision | Rationale |
|---|---|
| `school_name` instead of `name` | Consistent fully-qualified naming across entire project |
| `branches` lives in `schools/` domain | Branch cannot exist without a school — tight coupling is correct |
| `GET` scope violations return `404` | Never reveal existence of other tenants' data |
| `POST/PATCH/DELETE` scope violations return `403` | Admin already knows resource exists |
| `DELETE` soft-deletes, returns `200` + object | Client gets confirmation of what was deactivated |
| Branch routes nested under `/schools/{school_id}` | Enforces school scope at URL level |
| `PATCH` not `PUT` | Partial updates — only send fields you want to change |
| `core/schemas.py` created before this domain | `PaginatedResponse[T]` needed for list endpoints |
 
---
 
### Implementation Order
1. `core/schemas.py`                              ⏳ First — shared `PaginatedResponse[T]`
2. `schools/models.py`                            ⏳
3. `schools/schemas.py`                           ⏳
4. `schools/repository.py`                        ⏳
5. `schools/service.py`                           ⏳
6. `api/v1/schools.py`                            ⏳
7. Uncomment schools router in `api/v1/router.py` ⏳

---

## 🗄️ Database Schema Reference

All 21 tables are defined in `DatabaseSchema.md`. Key tables per domain:

 
| Domain (Package) | Table(s) | URL Prefix | Status |
|---|---|---|---|
| `auth/` | `users`, `roles`, `user_roles`, `refresh_tokens` | `/api/v1/auth/` | ✅ |
| `schools/` | `schools`, `branches` | `/api/v1/schools/` | ✅ |
| `fleet/` | `buses` | `/api/v1/fleet/buses/` | ✅ |
| `drivers/` | `drivers` | `/api/v1/drivers/` | ✅ |
| `gps/` | `gps_devices`, `bus_device_assignments` | `/api/v1/gps/` | ✅ |
| `routes/` | `routes`, `stops`, `route_stops` | `/api/v1/routes/` | ✅ |
| `trips/` | `trips`, `trip_live_status` | `/api/v1/trips/` | ✅ |
| `students/` | `students`, `parents`, `student_parents`, `student_leave_requests` | `/api/v1/students/` | ✅ |
| `assignments/` | `student_route_assignments` | `/api/v1/assignments/` | ✅ |
| `attendance/` | `student_attendance` | `/api/v1/attendance/` | ✅ |
| `notifications/` | `notification_logs` | `/api/v1/notifications/` | ✅ |
 

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
| 10 | Refresh token rotation on every refresh | ⏳ Not decided | Currently reusing same token — rotation = issue new token + revoke old on each refresh |

---

## 📁 Completed Files — Key Details
 
### `app/core/config.py`
- Uses `pydantic-settings` v2 with `model_config = SettingsConfigDict(...)`
- `DATABASE_URL` is a `@property` composing individual `DB_*` fields into async DSN
- DSN format: `postgresql+asyncpg://user:password@host:port/dbname`
- `JWT_SECRET_KEY` falls back to `secrets.token_urlsafe(64)` if not set in `.env`
- `ALLOWED_ORIGINS` validator splits comma-separated string into list
- Singleton: `settings = Settings()` — import and use everywhere
- Notable settings: `DB_POOL_PRE_PING=True`, `GPS_STALE_THRESHOLD_SECONDS=60`, `GPS_MIN_ACCURACY_METERS=50.0`
- Also includes: `DEFAULT_PAGE_SIZE`, `MAX_PAGE_SIZE`
  
### `app/core/enums.py`
- All 8 DB enums mirrored as `str, enum.Enum` (serializes to string in Pydantic/SQLAlchemy)
- Enums: `RoleName`, `TripType`, `TripStatus`, `AttendanceStatus`, `NotificationType`, `NotificationStatus`, `NotificationChannel`, `LeaveRequestStatus`
- Helper maps: `TRIP_STATUS_TRANSITIONS`, `LEAVE_STATUS_TRANSITIONS`, `NOTIFICATION_STATUS_TRANSITIONS`
- Helper sets: `BRANCH_SCOPED_ROLES`, `SCHOOL_SCOPED_ROLES`
- **NEW:** `PLATFORM_ROLES` — maps `"web"` / `"mobile"` to permitted `RoleName` sets — used in login validation
  
### `app/core/exceptions.py`
- Three-level hierarchy: `AppException → HTTPException` (FastAPI handles natively)
- `NotFoundError` is generic — takes `resource` name + optional `identifier`
- Domain-specific errors: `StudentNotFoundError`, `TripNotFoundError`, `BusNotFoundError`, `DriverNotFoundError`, `DeviceNotFoundError`, `AttendanceNotFoundError`, `LeaveRequestNotFoundError`, etc.
- `UnauthorizedError` includes `WWW-Authenticate: Bearer` header (HTTP spec)
- **Updated:** `InvalidCredentialsError(detail=...)` — accepts optional detail override for platform mismatch message
- Covers: 400, 401, 403, 404, 409, 422, 500
  
### `app/core/security.py`
- `hash_password` / `verify_password` — bcrypt in `run_in_executor` (non-blocking)
- `create_access_token(user_id, user_name, roles)` — embeds top-level `role`, `school_id`, `branch_id` claims (in addition to full `roles[]` list) for fast RLS variable extraction
- `create_refresh_token(user_id)` — contains only `user_id`, no role data
- `decode_access_token` / `decode_refresh_token` — validates signature, expiry, token type
- `extract_user_id(payload)` — parses `sub` claim (string → int)
- **Access token payload:** `sub`, `user_name`, `role` (primary), `school_id`, `branch_id`, `roles[]`, `type`, `iat`, `exp`
- **Refresh token payload:** `sub`, `type`, `iat`, `exp`
  
### `app/core/schemas.py`
- `PaginatedResponse[T]` — generic paginated envelope: `items`, `total`, `page`, `page_size`, `pages`
- `paginate(items, total, page, page_size)` — helper that builds `PaginatedResponse`
- `pagination_params(page, page_size, max_page_size)` — returns `(limit, offset)`
  
### `app/core/utils.py`
- `utcnow()` — returns timezone-aware UTC datetime — use everywhere instead of `datetime.utcnow()`
  
### `app/core/db/base.py`
- `NAMING_CONVENTION` dict for consistent Alembic constraint names
- `Base(DeclarativeBase)` with `MetaData(naming_convention=...)`
- `TZDateTime = DateTime(timezone=True)` — use on all timestamp columns
  
### `app/core/db/engine.py`
- `create_async_engine` with all pool settings from `settings`
- `AsyncSessionFactory` — `async_sessionmaker` with `expire_on_commit=False`, `autoflush=False`
  
### `app/core/db/session.py`
- `get_db()` — plain async session generator, NO RLS context
- **Use ONLY for auth routes** (`/login`, `/refresh`, `/logout`, `/me`)
- All other routes must use `build_tenant_dep` from `core/db/tenant.py`
  
### `app/core/db/tenant.py` ← NEW
- `TenantContext` — carries `user_id`, `role`, `school_id`, `branch_id` from JWT
- `_set_rls_vars(session, ctx)` — runs `set_config('app.*', ..., true)` for RLS activation
- `_attach_orm_filter(session, ctx)` — `do_orm_execute` listener, appends WHERE clauses to all ORM SELECTs
- `get_tenant_db(ctx)` — core async generator (set vars → attach filter → yield → commit/rollback)
- `build_tenant_dep(require_auth_dep)` — FastAPI `Depends()` factory for use in routers
  
### `app/core/db/__init__.py`
- Re-exports: `Base`, `TZDateTime`, `engine`, `AsyncSessionFactory`, `get_db`, `TenantContext`, `build_tenant_dep`, `get_tenant_db`
  
### `app/api/v1/dependencies.py`
- `bearer_scheme = HTTPBearer(auto_error=False)` — raises own 401 not FastAPI's 403
- `CurrentUser` class — populated from JWT payload, **no DB hit**
  - `has_role(role)`, `has_any_role(*roles)` — primary role checks
  - `has_school_access(school_id)` — SUPER_ADMIN passes all
  - `has_branch_access(school_id, branch_id)` — SUPER_ADMIN + SCHOOL_ADMIN pass all
  - `get_accessible_school_ids()` → `None` (SUPER_ADMIN) or `[school_id]`
  - `get_accessible_branch_ids(school_id)` → `None` (super/school admin), `[branch_id]` (branch-scoped), `[]` (wrong school)
- `get_current_user()` — core auth dependency
- `require_roles(*roles)` — factory returning a dependency that enforces role
- `check_school_access()` / `check_branch_access()` — scope guard helpers
- Pre-built: `SuperAdminRequired`, `SchoolAdminRequired`, `BranchAdminRequired`, `AnyAuthenticated`
  
### `app/api/v1/router.py`
- `api_router = APIRouter(prefix="/api/v1")`
- All 11 domain routers imported and registered
- **Current registrations:** auth, schools, fleet, drivers, gps, routes, trips, students, assignments, attendance, notifications
---
 
## ✅ Completed — `auth/` Domain
 
> Full design document: `docs/Auth.md`
 
### Tables Involved
| Table | Notes |
|---|---|
| `users` | Authentication — login, password, is_active |
| `roles` | Seeded once — `SUPER_ADMIN`, `SCHOOL_ADMIN`, etc. |
| `user_roles` | RBAC join — one user, multiple scoped roles |
| `refresh_tokens` | New table — hashed tokens with expiry + revocation |
 
### `auth/schemas.py` — Key Models
```
LoginRequest → user_name, password, platform ("web"|"mobile"), role (RoleName), device_info
               @model_validator: role must be in PLATFORM_ROLES[platform] — 422 before DB
RefreshTokenRequest → refresh_token
LogoutRequest → refresh_token
RoleResponse → role_id, role_name, school_id, branch_id, is_active, assigned_at
MeResponse → UserResponse + roles: list[RoleResponse]
TokenResponse → access_token, refresh_token, token_type="bearer", expires_in (int, seconds)
LogoutAllResponse → revoked_count, message
```
 
### `auth/service.py` — login() flow
```
1. get_user_with_roles_by_user_name → raise InvalidCredentialsError on any failure
2. verify_password                  → raise InvalidCredentialsError if wrong
3. check user.is_active             → raise InvalidCredentialsError if inactive
4. exact role check: user must hold the declared role (active)
   → raise InvalidCredentialsError("This account does not have the specified role.")
5. Build roles payload — only matching_roles (declared role only)
6. create_access_token(user_id, user_name, roles_payload)
7. create_refresh_token(user_id) → raw JWT
8. SHA-256 hash → create_refresh_token in DB
9. return TokenResponse
```
 
### `api/v1/auth.py` — Routes
```
POST   /api/v1/auth/login           public
POST   /api/v1/auth/refresh         public
POST   /api/v1/auth/logout          AnyAuthenticated
POST   /api/v1/auth/logout-all      AnyAuthenticated
GET    /api/v1/auth/me              AnyAuthenticated
```
---
## ✅ Completed — All Other Domains
---

### Domain Summary
 
| Domain | Model(s) | Key Notes |
|---|---|---|
| `schools/` | `School`, `Branch` | Branches nested under schools in URL; `school_name` not `name` |
| `fleet/` | `Bus` | `capacity > 0` CHECK; RESTRICT FKs |
| `drivers/` | `Driver` | `user_id` nullable (BIGINT); phone regex validation |
| `gps/` | `GPSDevice`, `BusDeviceAssignment` | IMEI globally unique; append-only assignment history; partial unique indexes via Alembic |
| `routes/` | `Route`, `Stop`, `RouteStop` | Stops RESTRICT (in-use); route_stop hard-delete is correct |
| `trips/` | `Trip`, `TripLiveStatus` | One per route+date+type; status transitions; live status upsert IN_PROGRESS only |
| `students/` | `Student`, `Parent`, `StudentParent`, `StudentLeaveRequest` | `user_id` NOT NULL (BIGINT); `relationship_type` (renamed from `relationship`); parents school-scoped |
| `assignments/` | `StudentRouteAssignment` | Separate row per PICKUP/DROPOFF; soft-delete |
| `attendance/` | `StudentAttendance` | Immutable once created; status correction BRANCH_ADMIN+; trip must be IN_PROGRESS |
| `notifications/` | `NotificationLog` | Append-only; event_key deduplication; SENT→READ user-facing; `log_notification()` helper |

---

### Full API URL Map
 
```
# Auth
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
POST   /api/v1/auth/logout-all
GET    /api/v1/auth/me
 
# Schools + Branches
POST   /api/v1/schools/
GET    /api/v1/schools/
GET    /api/v1/schools/{school_id}
PATCH  /api/v1/schools/{school_id}
DELETE /api/v1/schools/{school_id}
POST   /api/v1/schools/{school_id}/branches/
GET    /api/v1/schools/{school_id}/branches/
GET    /api/v1/schools/{school_id}/branches/{branch_id}
PATCH  /api/v1/schools/{school_id}/branches/{branch_id}
DELETE /api/v1/schools/{school_id}/branches/{branch_id}
 
# Fleet (Buses only)
POST   /api/v1/fleet/buses/
GET    /api/v1/fleet/buses/
GET    /api/v1/fleet/buses/{bus_id}
PATCH  /api/v1/fleet/buses/{bus_id}
DELETE /api/v1/fleet/buses/{bus_id}
 
# Drivers
POST   /api/v1/drivers/
GET    /api/v1/drivers/
GET    /api/v1/drivers/{driver_id}
PATCH  /api/v1/drivers/{driver_id}
DELETE /api/v1/drivers/{driver_id}
 
# GPS (devices + bus-device assignments)
POST   /api/v1/gps/devices/
GET    /api/v1/gps/devices/
GET    /api/v1/gps/devices/{device_id}
PATCH  /api/v1/gps/devices/{device_id}
DELETE /api/v1/gps/devices/{device_id}
POST   /api/v1/gps/devices/{device_id}/assign
POST   /api/v1/gps/devices/{device_id}/unassign
GET    /api/v1/gps/buses/{bus_id}/device
 
# Routes + Stops
POST   /api/v1/routes/routes/
GET    /api/v1/routes/routes/
GET    /api/v1/routes/routes/{route_id}
PATCH  /api/v1/routes/routes/{route_id}
DELETE /api/v1/routes/routes/{route_id}
GET    /api/v1/routes/routes/{route_id}/detail
POST   /api/v1/routes/routes/{route_id}/stops
GET    /api/v1/routes/routes/{route_id}/stops
PATCH  /api/v1/routes/routes/{route_id}/stops/{route_stop_id}
DELETE /api/v1/routes/routes/{route_id}/stops/{route_stop_id}
POST   /api/v1/routes/stops/
GET    /api/v1/routes/stops/
GET    /api/v1/routes/stops/{stop_id}
PATCH  /api/v1/routes/stops/{stop_id}
DELETE /api/v1/routes/stops/{stop_id}
 
# Trips + LiveStatus
POST   /api/v1/trips/trips/
GET    /api/v1/trips/trips/
GET    /api/v1/trips/trips/{trip_id}
PATCH  /api/v1/trips/trips/{trip_id}/assign
PATCH  /api/v1/trips/trips/{trip_id}/status
GET    /api/v1/trips/trips/{trip_id}/live-status
PUT    /api/v1/trips/trips/{trip_id}/live-status
 
# Students + Parents + Links + Leave
POST   /api/v1/students/students/
GET    /api/v1/students/students/
GET    /api/v1/students/students/{student_id}
PATCH  /api/v1/students/students/{student_id}
DELETE /api/v1/students/students/{student_id}
POST   /api/v1/students/students/{student_id}/parents
GET    /api/v1/students/students/{student_id}/parents
PATCH  /api/v1/students/students/{student_id}/parents/{student_parent_id}
DELETE /api/v1/students/students/{student_id}/parents/{student_parent_id}
POST   /api/v1/students/students/{student_id}/leave-requests
GET    /api/v1/students/students/{student_id}/leave-requests
PATCH  /api/v1/students/students/{student_id}/leave-requests/{leave_id}
POST   /api/v1/students/parents/
GET    /api/v1/students/parents/
GET    /api/v1/students/parents/{parent_id}
PATCH  /api/v1/students/parents/{parent_id}
DELETE /api/v1/students/parents/{parent_id}
 
# Assignments (student → route)
POST   /api/v1/assignments/
GET    /api/v1/assignments/student/{student_id}
GET    /api/v1/assignments/route/{route_id}
DELETE /api/v1/assignments/{assignment_id}
 
# Attendance
POST   /api/v1/attendance/trips/{trip_id}
GET    /api/v1/attendance/trips/{trip_id}
GET    /api/v1/attendance/students/{student_id}
PATCH  /api/v1/attendance/trips/{trip_id}/{attendance_id}
 
# Notifications
GET    /api/v1/notifications/
GET    /api/v1/notifications/{notification_id}
PATCH  /api/v1/notifications/{notification_id}/read
GET    /api/v1/notifications/admin/
POST   /api/v1/notifications/admin/
PATCH  /api/v1/notifications/admin/{notification_id}/status
```

---
## ❓ Open Decisions / TODOs
 
| # | Decision | Status | Notes |
|---|---|---|---|
| 1 | `core/schemas.py` — shared `PaginatedResponse[T]` | ✅ Resolved | `app/core/schemas.py` — `PaginatedResponse[T]`, `paginate()`, `pagination_params()` |
| 2 | Alembic setup — `alembic.ini` + `env.py` async config | ⏳ Pending | All models done — ready to generate. `rls_policies.py` migration written |
| 3 | Logging setup — format, level, handlers | ⏳ Not decided | Structured JSON logging recommended; add to `main.py` lifespan |
| 4 | Rate limiting — login endpoint especially | ⏳ Not decided | `slowapi` library likely |
| 5 | GPS log ingestion — dedicated endpoint or WebSocket? | ⏳ Not decided | High-volume, needs benchmarking; separate from `TripLiveStatus` |
| 6 | Push notification provider — FCM, OneSignal? | ⏳ Not decided | Affects `notifications/service.py`; FCM via `firebase_messaging` in Flutter |
| 7 | `is_active` re-check on every request | ⏳ Not decided | Currently token presence is sufficient |
| 8 | Soft delete — `is_active` flag consistent across all domains | ✅ Resolved | All tables soft-delete via `is_active = False` — never `db.delete()` |
| 9 | Dockerfile + docker-compose setup | ⏳ Pending | After all domains complete |
| 10 | Refresh token rotation on every refresh | ⏳ Not decided | Currently reusing same token — rotation = issue new + revoke old on each refresh |
| 11 | Fleet / other domain — role-aware query (SUPER_ADMIN null school_id) | ⏳ In Progress | `get_all_buses` repository pattern designed — apply to all list endpoints |
| 12 | Keyset pagination for high-volume tables | ⏳ Pending | `gps_logs`, `student_attendance` — offset pagination gets slow at scale |
 
---
 
## 📚 Reference Documents
 
| Document | Location | Contents |
|---|---|---|
| Auth design | `docs/Auth.md` | Login flow, JWT structure, refresh/logout, token storage |
| Schools design | `docs/Schools.md` | Schools + branches domain design |
| Multi-tenancy guide | `docs/MultiTenancy.md` | RLS policies, `build_tenant_dep`, DB user setup, background jobs |
| React frontend context | `docs/FrontendContext_React.md` | Admin dashboard (SCHOOL_ADMIN, BRANCH_ADMIN) — React + TypeScript |
| Flutter app context | `docs/FrontendContext_Flutter.md` | Mobile app (DRIVER, STUDENT) — Flutter + Dart |
| Database schema | `DatabaseSchema.md` | All 21 tables with SQL |
