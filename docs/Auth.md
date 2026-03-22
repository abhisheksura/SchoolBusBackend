# 🔐 Auth Domain — Design Document
> Last Updated: March 2026
> Status: ✅ Fully implemented

---

## 📌 Overview

The auth domain handles all authentication and authorization concerns:
- User login / logout
- JWT access + refresh token lifecycle
- Role-based access control (RBAC) with school/branch scoping
- Current user profile (`/me`)

---

## 🗄️ Tables Involved

| Table | Type | Notes |
|---|---|---|
| `users` | Existing | Central auth table — every login goes through here |
| `roles` | Existing | Seeded once — never changes at runtime |
| `user_roles` | Existing | RBAC join — one user, multiple scoped roles |
| `refresh_tokens` | **New** | Not in `DatabaseSchema.md` — created for this project |

---

## 🗃️ Database

### `refresh_tokens` table (new)
```sql
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_id    BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    issued_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked_at  TIMESTAMPTZ DEFAULT NULL,
    device_info VARCHAR(512) DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id
    ON refresh_tokens(user_id);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_active
    ON refresh_tokens(user_id, revoked_at);
```

**Column notes:**
| Column | Notes |
|---|---|
| `token_hash` | SHA-256 of raw JWT — `UNIQUE` to prevent collision acceptance |
| `revoked_at` | `NULL` = active, set = revoked. No `updated_at` — tokens are append-only |
| `issued_at` | Replaces `created_at` — semantically more precise for a token table |
| `device_info` | Optional user-agent or device label — enables per-device logout UX |

> All timestamp columns use `TIMESTAMPTZ` — see Key Design Decisions for rationale.

---

## 📁 File Structure

```
app/
├── auth/
│   ├── __init__.py
│   ├── models.py       ← User, Role, UserRole, RefreshToken ORM models
│   ├── schemas.py      ← Pydantic request/response models
│   ├── repository.py   ← all DB queries
│   └── service.py      ← business logic
├── core/
│   ├── utils.py        ← utcnow() helper
│   └── db/
│       └── base.py     ← TZDateTime = DateTime(timezone=True)
└── api/
    └── v1/
        └── auth.py     ← FastAPI HTTP routes
```

---

## 🧩 Models (`auth/models.py`)

### `User`
```
user_id       BIGSERIAL PK
user_name     VARCHAR(50) UNIQUE NOT NULL
email         VARCHAR(255) UNIQUE nullable
phone         VARCHAR(20) UNIQUE nullable
password_hash TEXT NOT NULL
is_active     BOOLEAN DEFAULT TRUE
created_at    TIMESTAMPTZ NOT NULL
updated_at    TIMESTAMPTZ NOT NULL
```
- Soft delete only — set `is_active = False`, never hard delete
- Never expose `password_hash` in any response
- Relationships: `user_roles` (one-to-many), `refresh_tokens` (one-to-many)
- All relationships use `lazy="noload"` — must use `selectinload` / `joinedload` explicitly

### `Role`
```
role_id     SERIAL PK
role_name   role_name_enum UNIQUE NOT NULL
description TEXT nullable
is_active   BOOLEAN DEFAULT TRUE
created_at  TIMESTAMPTZ NOT NULL
updated_at  TIMESTAMPTZ NOT NULL
```
- Seeded once at DB init — never mutated at runtime
- Seed values: `SUPER_ADMIN`, `SCHOOL_ADMIN`, `BRANCH_ADMIN`, `DRIVER`, `PARENT`, `STUDENT`

### `UserRole`
```
user_role_id BIGSERIAL PK
user_id      BIGINT FK → users
role_id      INT FK → roles
school_id    INT FK → schools (nullable)
branch_id    INT nullable
role_name    role_name_enum NOT NULL
is_active    BOOLEAN DEFAULT TRUE
assigned_at  TIMESTAMPTZ NOT NULL
updated_at   TIMESTAMPTZ NOT NULL
```
- Composite FK: `(branch_id, school_id)` → `branches(branch_id, school_id)` via `ForeignKeyConstraint`
- CHECK constraint mirrors DB scoping rules exactly:
  - `SUPER_ADMIN` → `school_id IS NULL`, `branch_id IS NULL`
  - `SCHOOL_ADMIN` → `school_id IS NOT NULL`, `branch_id IS NULL`
  - others → `school_id IS NOT NULL`, `branch_id IS NOT NULL`

### `RefreshToken`
```
token_id    BIGSERIAL PK
user_id     BIGINT FK → users (CASCADE DELETE)
token_hash  TEXT UNIQUE NOT NULL
issued_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
expires_at  TIMESTAMPTZ NOT NULL
revoked_at  TIMESTAMPTZ nullable (NULL = active)
device_info VARCHAR(512) nullable
```
- `is_active` and `is_expired` exposed as `@property` — computed from existing columns
- `lazy="noload"` on all relationships
- All timestamps use `TZDateTime` (`TIMESTAMPTZ`) — aware datetime comparisons are always correct
  
---

## 📬 Schemas (`auth/schemas.py`)

### Request Schemas
| Schema | Fields |
|---|---|
| `LoginRequest` | `user_name` (3-50 chars, lowercased), `password` (8-128 chars), `device_info` (optional, max 512) |
| `RefreshTokenRequest` | `refresh_token` (non-empty string) |
| `LogoutRequest` | `refresh_token` (non-empty string) |

### Response Schemas
| Schema | Fields |
|---|---|
| `RoleResponse` | `role_id`, `role_name`, `school_id`, `branch_id`, `is_active`, `assigned_at` |
| `UserResponse` | `user_id`, `user_name`, `email`, `phone`, `is_active`, `created_at`, `updated_at` |
| `MeResponse` | All `UserResponse` fields + `roles: list[RoleResponse]` |
| `TokenResponse` | `access_token`, `refresh_token`, `token_type="bearer"`, `expires_in` (seconds) |
| `LogoutAllResponse` | `revoked_count`, `message` |

**Schema rules:**
- All response schemas have `from_attributes=True`
- `str_strip_whitespace=True` on all request schemas
- `user_name` normalized to lowercase via `@field_validator`
- `expires_in` computed as `JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60`
- `password_hash` never included in any response schema

---

## 🗂️ Repository (`auth/repository.py`)

### User Queries
```python
get_user_by_user_name(db, user_name) -> User               # raises UserNotFoundError
get_user_by_user_id(db, user_id) -> User                   # raises UserNotFoundError
get_user_with_roles_by_user_name(db, user_name) -> User            # user + active roles via selectinload
get_user_with_roles_by_user_id(db, user_id) -> User                # user + active roles via selectinload
get_user_by_email_or_none(db, email) -> User | None
get_user_by_phone_or_none(db, phone) -> User | None
create_user(db, user_name, password_hash, email, phone) -> User
update_user_password_by_user_id(db, user_id, new_hash) -> User     # uses RETURNING
deactivate_user_by_user_id(db, user_id) -> User                    # uses RETURNING
```
### `get_user_by_*` vs `get_user_with_roles_by_*`
| Function | Returns | Use when |
|---|---|---|
| `get_user_by_user_id` | `User` (roles empty) | Only need user data — password check, active check |
| `get_user_with_roles_by_user_id` | `User` with `user_roles` populated | Need user + roles together — `get_me`, admin views |
| `get_user_by_user_name` | `User` (roles empty) | Rarely needed directly |
| `get_user_with_roles_by_user_name` | `User` with `user_roles` populated | `login()` — avoids second query for roles |

### Role Queries
```python
get_all_active_roles_by_user_id(db, user_id) -> list[UserRole]
get_user_role_by_user_role_id(db, user_role_id) -> UserRole
assign_role_to_user(db, user_id, role_id, role_name, school_id, branch_id) -> UserRole
revoke_user_role_by_user_role_id(db, user_role_id) -> UserRole
```

### Refresh Token Queries
```python
create_refresh_token(db, user_id, token_hash, expires_at, device_info) -> RefreshToken
get_refresh_token_by_token_hash(db, token_hash) -> RefreshToken    # raises InvalidTokenError
get_all_active_refresh_tokens_by_user_id(db, user_id) -> list[RefreshToken]
revoke_refresh_token_by_token_hash(db, token_hash) -> RefreshToken
revoke_all_refresh_tokens_by_user_id(db, user_id) -> int           # returns count revoked
```

### RETURNING pattern (all update functions)
```python
result = await db.execute(
    update(Model).where(...).values(...).returning(Model)
)
await db.flush()
obj = result.scalar_one_or_none()
if not obj:
    raise ModelNotFoundError(identifier=pk)
return obj
```

---

## ⚙️ Service (`auth/service.py`)

### `login(db, user_name, password, device_info) -> TokenResponse`
1. `get_user_with_roles_by_user_name` → catch all, raise `InvalidCredentialsError` (single call — user + roles)
2. `verify_password` → raise `InvalidCredentialsError` if wrong (never reveal which field failed)
3. Check `user.is_active` → raise `InvalidCredentialsError` if inactive
4. `_build_roles_payload(user.user_roles)` → roles already loaded, no second DB query
5. `create_access_token(user_id, user_name, roles)`
6. `create_refresh_token(user_id)` → raw JWT
7. SHA-256 hash raw token → `create_refresh_token` in DB
8. Return `TokenResponse`

### `refresh(db, raw_refresh_token) -> TokenResponse`
1. `decode_refresh_token` → validate JWT, extract `user_id`
2. SHA-256 hash → `get_refresh_token_by_token_hash`
3. Check `db_token.is_active` → raise `RefreshTokenRevokedError`
4. Check `db_token.is_expired` → raise `TokenExpiredError`
5. `get_user_by_user_id` → raise `UnauthorizedError` if inactive
6. `get_all_active_roles_by_user_id` → build fresh roles payload
7. `create_access_token` → new access token
8. Return `TokenResponse` with same refresh token (no rotation — see Open Decisions)

   
### `logout(db, raw_refresh_token, user_id) -> None`
1. SHA-256 hash raw token
2. `get_refresh_token_by_token_hash` → silently ignore `InvalidTokenError`
3. Check `token.user_id == user_id` → silently return if mismatch (ownership check)
4. `revoke_refresh_token_by_token_hash`
- Fully idempotent — always returns `None`, never raises
- Ownership mismatch returns silently — never reveals token exists for another user
 
### `logout_all(db, user_id) -> LogoutAllResponse`
1. `revoke_all_refresh_tokens_by_user_id` → single `UPDATE ... RETURNING` query
2. Return `LogoutAllResponse` with revoked count
 
### `get_me(db, user_id) -> MeResponse`
1. `get_user_with_roles_by_user_id` → user + roles in one efficient call
2. Build `MeResponse` explicitly field by field from `user.user_roles`

---

## 🌐 Routes (`api/v1/auth.py`)


| Method | Path | Auth | Status | Notes |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/login` | None | `200` | `device_info` falls back to `User-Agent` header |
| `POST` | `/api/v1/auth/refresh` | None | `200` | Returns same refresh token — rotation tracked in Open Decisions |
| `POST` | `/api/v1/auth/logout` | Bearer | `204` | Ownership verified — only revokes caller's own tokens |
| `POST` | `/api/v1/auth/logout-all` | Bearer | `200` | Revokes all sessions, returns count |
| `GET` | `/api/v1/auth/me` | Bearer | `200` | Returns user + active roles |
 
> `POST` for logout is correct — it mutates server state (revokes DB record). `GET` for logout is wrong per HTTP spec.
---
## 🔑 Key Design Decisions
 
| Decision | Rationale |
|---|---|
| Store SHA-256 hash of refresh token | Raw token in DB = same risk as plain-text password |
| No token rotation on refresh (for now) | Simpler — tracked in Open Decisions |
| `device_info` on refresh tokens | Enables per-device logout UX in future |
| `logout` ownership check — silently ignores mismatched tokens | Never reveals token existence for another user |
| `logout` fully idempotent — silently ignores unknown tokens | Client can always safely call logout |
| `get_me` uses `get_user_with_roles_by_user_id` | One call — user + roles via `selectinload`, no second query |
| `login` uses `get_user_with_roles_by_user_name` | Reduces login from 3 queries to 2 (user+roles + insert token) |
| `InvalidCredentialsError` for bad username AND bad password | Never reveal which one is wrong — security best practice |
| `lazy="noload"` on all ORM relationships | Prevents `MissingGreenlet` errors in async SQLAlchemy |
| `get_user_by_*` vs `get_user_with_roles_by_*` naming | Makes it explicit at the call site whether roles are loaded |
| `ENUM(..., create_type=False)` on `role_name` | Type already exists in PG — prevents `CREATE TYPE` conflict |
| All timestamps use `TIMESTAMPTZ` + `TZDateTime` in SQLAlchemy | Correct across server timezones and DST — eliminates naive datetime risks |
| `utcnow()` from `app.core.utils` — never `datetime.utcnow()` | Deprecated in Python 3.12 — `utcnow()` wraps `datetime.now(timezone.utc)` |
| `RETURNING` clause on all UPDATE functions | Single DB round-trip — eliminates stale identity map risk, replaces `expire_all()` + re-fetch |
| `ForeignKeyConstraint` for composite FK in `UserRole` | Declared in model — Alembic autogenerates it correctly |
| Import repository as module (`import repository as auth_repo`) | Cleaner call sites, easier to mock in tests |
| `MeResponse` built explicitly field by field | Prevents accidentally exposing new model fields in future |
 
---
 
## ❓ Open Decisions
 
| # | Decision | Status | Notes |
|---|---|---|---|
| 1 | Refresh token rotation on every refresh | ⏳ Not decided | Issue new token + revoke old on each refresh — change in `api/v1/auth.py` `/refresh` endpoint |
| 2 | `is_active` check on every request via DB | ⏳ Not decided | Currently token presence is sufficient |
| 3 | `ChangePasswordRequest` endpoint | ⏳ Not implemented | Future — add to auth routes |
| 4 | Rate limiting on `/login` endpoint | ⏳ Not decided | `slowapi` library likely |
 
---
 
## 🐛 Known Issues / Fixes Applied
 
| Issue | Fix Applied | File |
|---|---|---|
| `can't subtract offset-naive and offset-aware datetimes` | Migrated all DB columns to `TIMESTAMPTZ`, `utcnow()` returns aware datetime | `app/core/utils.py`, `app/core/db/base.py`, all models |
| Stale identity map after Core `UPDATE` | Replaced `expire_all()` + re-fetch with `UPDATE ... RETURNING` | `app/auth/repository.py`, `app/schools/repository.py` |
| `login()` making 2 separate DB queries for user + roles | Replaced `get_user_by_user_name` + `get_all_active_roles_by_user_id` with `get_user_with_roles_by_user_name` | `app/auth/service.py` |
| `logout` could revoke tokens belonging to other users | Added ownership check: `token.user_id != user_id → return silently` | `app/auth/service.py` |
| `lazy="noload"` on relationships returned empty list silently | Added `get_user_with_roles_by_*` using `selectinload` for when roles are needed | `app/auth/repository.py` |
