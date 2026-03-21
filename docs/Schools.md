# 🏫 Schools Domain — Design Document
> Last Updated: March 2026
> Status: ✅ Design finalized — Ready to code

---

## 📌 Overview

The schools domain manages the top two levels of the multi-tenant hierarchy:
- **Schools** — top-level tenant, every resource traces back to `school_id`
- **Branches** — campus under a school, most resources are scoped at `(branch_id, school_id)`

Branches live in this domain (not a separate `branches/` domain) because a branch
cannot exist without a school — tight coupling is correct here.

---

## 🗄️ Tables Involved

| Table | Notes |
|---|---|
| `schools` | Top-level tenant. `school_name` used instead of `name` for consistency |
| `branches` | Scoped to school via `school_id` FK + composite unique `(branch_id, school_id)` |

### Important: `school_name` rename
The DB column in `schools` is `name` in `DatabaseSchema.md` but we use `school_name`
throughout the codebase for consistent fully-qualified naming. The Alembic migration
will create the column as `school_name`.

---

## 📁 File Structure

```
app/
├── schools/
│   ├── __init__.py
│   ├── models.py       ← School, Branch ORM models
│   ├── schemas.py      ← Pydantic request/response models
│   ├── repository.py   ← all DB queries
│   └── service.py      ← business logic
├── core/
│   └── schemas.py      ← PaginatedResponse[T] created here (Open Decision #1)
└── api/
    └── v1/
        └── schools.py  ← FastAPI HTTP routes
```

---

## 🧩 Models (`schools/models.py`)

### `School`
```
school_id   : SERIAL PK
school_name : VARCHAR(255) NOT NULL
is_active   : BOOLEAN NOT NULL DEFAULT TRUE
created_at  : TIMESTAMP DEFAULT NOW()
updated_at  : TIMESTAMP DEFAULT NOW()
```
- Soft delete only — `is_active = False`
- Relationships: `branches` (one-to-many, `lazy="noload"`)

### `Branch`
```
branch_id      : SERIAL PK
school_id      : INT NOT NULL FK → schools (CASCADE)
branch_name    : VARCHAR(150) NOT NULL
branch_address : TEXT nullable
branch_phone   : VARCHAR(20) nullable
branch_email   : VARCHAR(255) nullable
is_active      : BOOLEAN NOT NULL DEFAULT TRUE
created_at     : TIMESTAMP DEFAULT NOW()
updated_at     : TIMESTAMP DEFAULT NOW()
UNIQUE (branch_id, school_id)
INDEX idx_branches_school_id ON branches(school_id)
```
- Soft delete only — `is_active = False`
- Relationships: `school` (many-to-one, `lazy="noload"`)

---

## 📬 Schemas (`schools/schemas.py`)

### Request Schemas
| Schema | Fields | Validation |
|---|---|---|
| `SchoolCreate` | `school_name` | min 3, max 255 chars, strip whitespace |
| `SchoolUpdate` | `school_name \| None`, `is_active \| None` | at least one field required |
| `BranchCreate` | `branch_name`, `branch_address \| None`, `branch_phone \| None`, `branch_email \| None` | `branch_name` min 3 max 150 |
| `BranchUpdate` | all fields optional | at least one field required |

### Response Schemas
| Schema | Fields |
|---|---|
| `SchoolResponse` | `school_id`, `school_name`, `is_active`, `created_at`, `updated_at` |
| `SchoolDetailResponse` | All `SchoolResponse` fields + `branches: list[BranchResponse]` |
| `BranchResponse` | `branch_id`, `school_id`, `branch_name`, `branch_address`, `branch_phone`, `branch_email`, `is_active`, `created_at`, `updated_at` |
| `PaginatedSchoolResponse` | `items: list[SchoolResponse]`, `total`, `page`, `page_size`, `pages` |
| `PaginatedBranchResponse` | `items: list[BranchResponse]`, `total`, `page`, `page_size`, `pages` |

### `core/schemas.py` — Shared Generic (created here)
```python
class PaginatedResponse(BaseModel, Generic[T]):
    items     : list[T]
    total     : int
    page      : int
    page_size : int
    pages     : int  # ceil(total / page_size)
```

---

## 🗂️ Repository (`schools/repository.py`)

### School Queries
```python
get_school_by_school_id(db, school_id) -> School                     # raises SchoolNotFoundError
get_school_by_school_id_or_none(db, school_id) -> School | None
get_all_schools(db, limit, offset, active_only) -> tuple[list[School], int]
get_schools_by_school_ids(db, school_ids, limit, offset, active_only) -> tuple[list[School], int]
create_school(db, school_name) -> School
update_school_by_school_id(db, school_id, **kwargs) -> School
deactivate_school_by_school_id(db, school_id) -> School
```

### Branch Queries
```python
get_branch_by_branch_id(db, branch_id, school_id) -> Branch          # raises BranchNotFoundError
get_branch_by_branch_id_or_none(db, branch_id, school_id) -> Branch | None
get_all_branches_by_school_id(db, school_id, limit, offset, active_only) -> tuple[list[Branch], int]
get_branches_by_branch_ids(db, branch_ids, school_id, limit, offset, active_only) -> tuple[list[Branch], int]
create_branch(db, school_id, branch_name, branch_address, branch_phone, branch_email) -> Branch
update_branch_by_branch_id(db, branch_id, school_id, **kwargs) -> Branch
deactivate_branch_by_branch_id(db, branch_id, school_id) -> Branch
```

---

## ⚙️ Service (`schools/service.py`)

### School Functions

**`create_school(db, payload, current_user) -> SchoolResponse`**
1. Require `SUPER_ADMIN` → `403` if not
2. `create_school` in repo
3. Return `SchoolResponse`

**`get_school(db, school_id, current_user) -> SchoolResponse`**
1. `get_school_by_school_id` → `404` if not found
2. `not has_school_access` → `404` (not `403` — never reveal existence)
3. Return `SchoolResponse`

**`get_all_schools(db, page, page_size, current_user) -> PaginatedSchoolResponse`**
1. `SUPER_ADMIN` → `get_all_schools` (no filter)
   others → `get_schools_by_school_ids(accessible_school_ids)`
2. Return `PaginatedSchoolResponse`

**`update_school(db, school_id, payload, current_user) -> SchoolResponse`**
1. Require `SUPER_ADMIN` → `403` if not
2. `get_school_by_school_id` → `404` if not found
3. `update_school_by_school_id`
4. Return `SchoolResponse`

**`deactivate_school(db, school_id, current_user) -> SchoolResponse`**
1. Require `SUPER_ADMIN` → `403` if not
2. `get_school_by_school_id` → `404` if not found
3. `deactivate_school_by_school_id`
4. Return `SchoolResponse`

### Branch Functions

**`create_branch(db, school_id, payload, current_user) -> BranchResponse`**
1. Require `SUPER_ADMIN` or `SCHOOL_ADMIN` scoped to `school_id` → `403` if not
2. `get_school_by_school_id` → `404` if school not found or inactive
3. `create_branch` in repo
4. Return `BranchResponse`

**`get_branch(db, school_id, branch_id, current_user) -> BranchResponse`**
1. `get_branch_by_branch_id` → `404` if not found
2. `not has_branch_access` → `404` (not `403`)
3. Return `BranchResponse`

**`get_all_branches(db, school_id, page, page_size, current_user) -> PaginatedBranchResponse`**
1. `get_school_by_school_id` → `404` if school not found
2. `not has_school_access` → `404` (not `403`)
3. `SUPER_ADMIN`/`SCHOOL_ADMIN` → `get_all_branches_by_school_id`
   others → `get_branches_by_branch_ids(accessible_branch_ids)`
4. Return `PaginatedBranchResponse`

**`update_branch(db, school_id, branch_id, payload, current_user) -> BranchResponse`**
1. Require `SUPER_ADMIN` or `SCHOOL_ADMIN` scoped to `school_id` → `403` if not
2. `get_branch_by_branch_id` → `404` if not found
3. `update_branch_by_branch_id`
4. Return `BranchResponse`

**`deactivate_branch(db, school_id, branch_id, current_user) -> BranchResponse`**
1. Require `SUPER_ADMIN` or `SCHOOL_ADMIN` scoped to `school_id` → `403` if not
2. `get_branch_by_branch_id` → `404` if not found
3. `deactivate_branch_by_branch_id`
4. Return `BranchResponse`

---

## 🌐 Routes (`api/v1/schools.py`)

### School Routes
| Method | Path | Auth | Status | Scope violation |
|---|---|---|---|---|
| `POST` | `/api/v1/schools/` | `SUPER_ADMIN` | `201` | `403` |
| `GET` | `/api/v1/schools/` | Bearer + tenant filter | `200` | filtered at query level |
| `GET` | `/api/v1/schools/{school_id}` | Bearer + school scope | `200` | `404` |
| `PATCH` | `/api/v1/schools/{school_id}` | `SUPER_ADMIN` | `200` | `403` |
| `DELETE` | `/api/v1/schools/{school_id}` | `SUPER_ADMIN` | `200` | `403` |

### Branch Routes
| Method | Path | Auth | Status | Scope violation |
|---|---|---|---|---|
| `POST` | `/api/v1/schools/{school_id}/branches/` | `SUPER_ADMIN` or `SCHOOL_ADMIN` | `201` | `403` |
| `GET` | `/api/v1/schools/{school_id}/branches/` | Bearer + tenant filter | `200` | `404` on school, filtered at query level for branches |
| `GET` | `/api/v1/schools/{school_id}/branches/{branch_id}` | Bearer + branch scope | `200` | `404` |
| `PATCH` | `/api/v1/schools/{school_id}/branches/{branch_id}` | `SUPER_ADMIN` or `SCHOOL_ADMIN` | `200` | `403` |
| `DELETE` | `/api/v1/schools/{school_id}/branches/{branch_id}` | `SUPER_ADMIN` or `SCHOOL_ADMIN` | `200` | `403` |

---

## 🔑 Key Design Decisions

| Decision | Rationale |
|---|---|
| `school_name` instead of `name` | Consistent fully-qualified naming across entire project |
| `branches` lives in `schools/` domain | Branch cannot exist without a school — tight coupling is correct |
| `GET` scope violations return `404` | Never reveal existence of other tenants' data |
| `POST/PATCH/DELETE` scope violations return `403` | Admin already knows resource exists |
| `DELETE` soft-deletes, returns `200` + object | Client gets confirmation of what was deactivated |
| Branch routes nested under `/schools/{school_id}` | Enforces school scope at URL level |
| `PATCH` not `PUT` | Partial updates — only send fields you want to change |
| `core/schemas.py` created before this domain | `PaginatedResponse[T]` needed for all list endpoints |
| `get_schools_by_school_ids` + `get_branches_by_branch_ids` in repo | Needed for tenant-filtered list queries for non-SUPER_ADMIN users |

---

## ❓ Open Decisions

| # | Decision | Status | Notes |
|---|---|---|---|
| 1 | `SchoolDetailResponse` — when to use vs `SchoolResponse` | ⏳ Not decided | Could be a query param `?include_branches=true` |
| 2 | Pagination defaults | ⏳ Not decided | Using `settings.DEFAULT_PAGE_SIZE` and `settings.MAX_PAGE_SIZE` |

---

## 📋 Implementation Order
1. `core/schemas.py`                              ⏳ First — shared `PaginatedResponse[T]`
2. `schools/models.py`                            ⏳
3. `schools/schemas.py`                           ⏳
4. `schools/repository.py`                        ⏳
5. `schools/service.py`                           ⏳
6. `api/v1/schools.py`                            ⏳
7. Uncomment schools router in `api/v1/router.py` ⏳
