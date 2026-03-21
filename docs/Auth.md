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
    issued_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMP NOT NULL,
    revoked_at  TIMESTAMP DEFAULT NULL,
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
created_at    TIMESTAMP
updated_at    TIMESTAMP
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
created_at  TIMESTAMP
updated_at  TIMESTAMP
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
assigned_at  TIMESTAMP
updated_at   TIMESTAMP
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
issued_at   TIMESTAMP DEFAULT NOW()
expires_at  TIMESTAMP NOT NULL
revoked_at  TIMESTAMP nullable (NULL = active)
device_info VARCHAR(512) nullable
```
- `is_active` and `is_expired` exposed as `@property` — computed from existing columns
- `lazy="noload"` on all relationships

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
get_user_by_email_or_none(db, email) -> User | None
get_user_by_phone_or_none(db, phone) -> User | None
create_user(db, user_name, password_hash, email, phone) -> User
update_user_password_by_user_id(db, user_id, new_hash) -> User
deactivate_user_by_user_id(db, user_id) -> User
```

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

---

## ⚙️ Service (`auth/service.py`)

### `login(db, user_name, password, device_info) -> TokenResponse`
1. `get_user_by_user_name` → catch all exceptions, raise `InvalidCredentialsError`
2. `verify_password` → raise `InvalidCredentialsError` if wrong
3. Check `user.is_active` → raise `InvalidCredentialsError` if inactive
4. `get_all_active_roles_by_user_id` → build roles payload
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

### `logout(db, raw_refresh_token) -> None`
1. SHA-256 hash raw token
2. `revoke_refresh_token_by_token_hash` → silently ignore `InvalidTokenError`
3. Idempotent — always succeeds

### `logout_all(db, user_id) -> LogoutAllResponse`
1. `revoke_all_refresh_tokens_by_user_id`
2. Return `LogoutAllResponse` with revoked count

### `get_me(db, user_id) -> MeResponse`
1. `get_user_by_user_id`
2. `get_all_active_roles_by_user_id`
3. Return `MeResponse` built explicitly field by field

---

## 🌐 Routes (`api/v1/auth.py`)

| Method | Path | Auth | Status | Handler |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/login` | None | `200` | `login()` |
| `POST` | `/api/v1/auth/refresh` | None | `200` | `refresh_token()` |
| `POST` | `/api/v1/auth/logout` | Bearer | `204` | `logout()` |
| `POST` | `/api/v1/auth/logout-all` | Bearer | `200` | `logout_all()` |
| `GET` | `/api/v1/auth/me` | Bearer | `200` | `get_me()` |

---

## 🔑 Key Design Decisions

| Decision | Rationale |
|---|---|
| Store SHA-256 hash of refresh token | Raw token in DB = same risk as plain-text password |
| No token rotation on refresh | Simpler for now — tracked in Open Decisions |
| `device_info` on refresh tokens | Enables per-device logout UX in future |
| `logout` silently ignores unknown tokens | Idempotent — client can always safely call logout |
| `get_me` in auth domain | Tightly coupled to auth — returns user + active roles |
| `InvalidCredentialsError` for both bad username AND bad password | Never reveal which one is wrong — security best practice |
| `lazy="noload"` on all ORM relationships | Prevents `MissingGreenlet` errors in async SQLAlchemy |
| `ENUM(..., create_type=False)` on role_name | Type already exists in PG — prevents `CREATE TYPE` conflict |
| `datetime.utcnow()` throughout (not `datetime.now(timezone.utc)`) | DB columns are `TIMESTAMP WITHOUT TIME ZONE` — naive datetimes only |
| `ForeignKeyConstraint` for composite FK in `UserRole` | Declared in model — Alembic autogenerates it correctly |
| Import repository as module (`import repository as auth_repo`) | Cleaner call sites, easier to mock in tests |
| `MeResponse` built explicitly field by field | Prevents accidentally exposing new model fields added in future |

---

## ❓ Open Decisions

| # | Decision | Status | Notes |
|---|---|---|---|
| 1 | Refresh token rotation on every refresh | ⏳ Not decided | Issue new token + revoke old on each refresh |
| 2 | `is_active` check on every request via DB | ⏳ Not decided | Currently token presence is sufficient |
| 3 | `ChangePasswordRequest` endpoint | ⏳ Not implemented | Future — add to auth routes |
| 4 | Rate limiting on `/login` endpoint | ⏳ Not decided | `slowapi` library likely |

---

## 🐛 Known Issues / Fixes Applied

| Issue | Fix |
|---|---|
| `can't subtract offset-naive and offset-aware datetimes` on refresh token insert | Changed `datetime.now(timezone.utc)` → `datetime.utcnow()` in `service.py` and `models.py` to match `TIMESTAMP WITHOUT TIME ZONE` DB columns |
