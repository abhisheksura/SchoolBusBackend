# 🗄️ School Bus Tracker — Database Schema Reference

> **Engine:** PostgreSQL
> **Last Updated:** March 2026
> **Changes from original:**
> - All `TIMESTAMP` columns migrated to `TIMESTAMPTZ` (timezone-aware)
> - `schools.name` renamed to `schools.school_name`
> - `refresh_tokens` table added (new — not in original schema)
> - Multi-tenant architecture — every resource is scoped to `school_id` and `branch_id`

---

## Tables Overview

| Table | PK Type | Notes |
|---|---|---|
| `schools` | serial | Top-level tenant |
| `branches` | serial | Branch/campus under a school |
| `users` | bigserial | Every login account — no role stored here |
| `roles` | serial | Seeded once, never changes |
| `user_roles` | bigserial | RBAC join table — one user can hold multiple scoped roles |
| `refresh_tokens` | bigserial | **New** — JWT refresh token store (hashed) |
| `drivers` | serial | Scoped to `branch_id + school_id` |
| `buses` | serial | Scoped to `branch_id + school_id` |
| `gps_devices` | serial | Scoped to `branch_id + school_id` |
| `routes` | serial | Logical route — no PICKUP/DROP split at this level |
| `stops` | serial | Physical GPS-tagged locations, scoped to branch |
| `route_stops` | serial | Ordered stop list per route **and** trip_type |
| `students` | serial | Scoped to `branch_id + school_id` |
| `parents` | serial | Scoped to `school_id` — 1:1 with users |
| `student_parents` | serial | M:N link between students and parents |
| `trips` | serial | 1 per route per day per trip_type |
| `trip_live_status` | serial | 1:1 with trips — live GPS snapshot |
| `student_route_assignments` | serial | Links student → route + stop (per PICKUP or DROP) |
| `student_attendance` | serial | Per-trip attendance record per student |
| `notification_logs` | serial | Append-only notification records |
| `gps_logs` | bigserial | Append-only, high-volume GPS ping stream |
| `bus_device_assignments` | serial | Device swap history |
| `student_leave_requests` | serial | Date-range leave requests per student |

---

## ENUMs

```sql
CREATE TYPE role_name_enum AS ENUM ('SUPER_ADMIN', 'SCHOOL_ADMIN', 'BRANCH_ADMIN', 'DRIVER', 'PARENT', 'STUDENT');
CREATE TYPE trip_type_enum AS ENUM ('PICKUP', 'DROPOFF');
CREATE TYPE trip_status_enum AS ENUM ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED');
CREATE TYPE attendance_status_enum AS ENUM ('BOARDED', 'DROPPED', 'NO_SHOW');
CREATE TYPE notification_status_enum AS ENUM ('PENDING', 'SENT', 'FAILED', 'READ');
CREATE TYPE notification_type_enum AS ENUM ('ATTENDANCE', 'TRIP_START', 'TRIP_END', 'DELAY', 'GENERAL');
CREATE TYPE channel_enum AS ENUM ('PUSH', 'SMS', 'EMAIL', 'WHATSAPP');
CREATE TYPE student_leave_request_status_enum AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
```

---

## Table: `schools`
Top-level tenant. Every other resource traces back to a school.
> **Change:** `name` → `school_name`, `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS schools (
    school_id   SERIAL      PRIMARY KEY,
    school_name VARCHAR(255) NOT NULL,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

---

## Table: `branches`
Branch or campus under a school. Most resources scoped at `(branch_id, school_id)`.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS branches (
    branch_id      SERIAL       PRIMARY KEY,
    school_id      INT          NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_name    VARCHAR(150) NOT NULL,
    branch_address TEXT,
    branch_phone   VARCHAR(20),
    branch_email   VARCHAR(255),
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (branch_id, school_id)
);

CREATE INDEX IF NOT EXISTS idx_branches_school_id ON branches(school_id);
```

---

## Table: `users`
Authentication table. Every login goes through here.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id       BIGSERIAL    PRIMARY KEY,
    user_name     VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(255) UNIQUE,
    phone         VARCHAR(20)  UNIQUE,
    password_hash TEXT         NOT NULL,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

**Rules:**
- Soft delete only — set `is_active = false`
- Never expose `password_hash` in any API response
- No `role_id` column here — roles managed through `user_roles`

---

## Table: `roles`
Seeded once. Maps role names to descriptions.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS roles (
    role_id     SERIAL         PRIMARY KEY,
    role_name   role_name_enum NOT NULL UNIQUE,
    description TEXT,
    is_active   BOOLEAN        NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);
```

**Seed values:** `SUPER_ADMIN`, `SCHOOL_ADMIN`, `BRANCH_ADMIN`, `DRIVER`, `PARENT`, `STUDENT`

---

## Table: `user_roles`
RBAC join table. A single user can hold multiple roles across different schools/branches.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS user_roles (
    user_role_id BIGSERIAL      PRIMARY KEY,
    user_id      BIGINT         NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id      INT            NOT NULL REFERENCES roles(role_id),
    school_id    INT            REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id    INT,
    role_name    role_name_enum NOT NULL,
    is_active    BOOLEAN        NOT NULL DEFAULT TRUE,
    assigned_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    CHECK (
        (role_name = 'SUPER_ADMIN'  AND school_id IS NULL     AND branch_id IS NULL) OR
        (role_name = 'SCHOOL_ADMIN' AND school_id IS NOT NULL AND branch_id IS NULL) OR
        (role_name IN ('BRANCH_ADMIN', 'DRIVER', 'PARENT', 'STUDENT')
            AND school_id IS NOT NULL AND branch_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
```

**Rules:**
- `SUPER_ADMIN` — no school or branch scope
- `SCHOOL_ADMIN` — school scope only, `branch_id IS NULL`
- `BRANCH_ADMIN`, `DRIVER`, `PARENT`, `STUDENT` — must have both `school_id` and `branch_id`

---

## Table: `refresh_tokens`
**New table** — not in original schema. Stores hashed JWT refresh tokens.
> All timestamps use `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_id    BIGSERIAL    PRIMARY KEY,
    user_id     BIGINT       NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash  TEXT         NOT NULL UNIQUE,
    issued_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ  NOT NULL,
    revoked_at  TIMESTAMPTZ  DEFAULT NULL,
    device_info VARCHAR(512) DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_active  ON refresh_tokens(user_id, revoked_at);
```

**Rules:**
- `token_hash` is SHA-256 of the raw JWT — never store the raw token
- `revoked_at IS NULL` = active token, `revoked_at IS NOT NULL` = revoked
- No `updated_at` — tokens are append-only; only `revoked_at` is ever set

---

## Table: `drivers`
Scoped to a specific branch within a school.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS drivers (
    driver_id      SERIAL       PRIMARY KEY,
    user_id        BIGINT       UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    school_id      INT          NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id      INT          NOT NULL,
    first_name     VARCHAR(100) NOT NULL,
    last_name      VARCHAR(100),
    phone          VARCHAR(20),
    license_number VARCHAR(100),
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (driver_id, branch_id, school_id)
);
```

---

## Table: `buses`
Scoped to a specific branch within a school.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS buses (
    bus_id     SERIAL      PRIMARY KEY,
    school_id  INT         NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id  INT         NOT NULL,
    bus_number VARCHAR(50) NOT NULL,
    capacity   INT         NOT NULL CHECK (capacity > 0),
    is_active  BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (bus_id, branch_id, school_id)
);
```

---

## Table: `gps_devices`
Hardware GPS units, scoped to a branch.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS gps_devices (
    device_id   SERIAL       PRIMARY KEY,
    school_id   INT          NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id   INT          NOT NULL,
    device_imei VARCHAR(100) NOT NULL UNIQUE,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (device_id, branch_id, school_id)
);
```

---

## Table: `routes`
Logical route — no PICKUP/DROP distinction at this level.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS routes (
    route_id    SERIAL       PRIMARY KEY,
    school_id   INT          NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id   INT          NOT NULL,
    route_code  VARCHAR(50)  NOT NULL,
    route_name  VARCHAR(100) NOT NULL,
    description TEXT,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (route_code, branch_id, school_id),
    UNIQUE (route_id,   branch_id, school_id)
);
```

---

## Table: `stops`
Physical GPS-tagged bus stops, scoped to a branch.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS stops (
    stop_id    SERIAL        PRIMARY KEY,
    school_id  INT           NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id  INT           NOT NULL,
    stop_name  VARCHAR(255)  NOT NULL,
    latitude   DECIMAL(9,6),
    longitude  DECIMAL(9,6),
    is_active  BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (stop_name, branch_id, school_id),
    UNIQUE (stop_id,   branch_id, school_id),

    CONSTRAINT valid_latitude  CHECK (latitude  BETWEEN -90  AND 90),
    CONSTRAINT valid_longitude CHECK (longitude BETWEEN -180 AND 180)
);

CREATE INDEX IF NOT EXISTS idx_stops_school_branch ON stops(school_id, branch_id);
CREATE INDEX IF NOT EXISTS idx_stops_lat_lng        ON stops(latitude, longitude);
```

---

## Table: `route_stops`
Ordered list of stops per route, split by `trip_type`.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS route_stops (
    route_stop_id  SERIAL         PRIMARY KEY,
    route_id       INT            NOT NULL REFERENCES routes(route_id) ON DELETE CASCADE,
    stop_id        INT            NOT NULL REFERENCES stops(stop_id)   ON DELETE RESTRICT,
    school_id      INT            NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id      INT            NOT NULL,
    trip_type      trip_type_enum NOT NULL,
    stop_sequence  INT            NOT NULL CHECK (stop_sequence > 0),
    estimated_time TIME,
    created_at     TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (route_id, trip_type, stop_id),
    UNIQUE (route_id, trip_type, stop_sequence)
);

CREATE INDEX IF NOT EXISTS idx_route_stops_route_type ON route_stops(route_id, trip_type);
```

---

## Table: `students`
Scoped to a specific branch. Login via `users` — `user_id` is mandatory.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS students (
    student_id       SERIAL       PRIMARY KEY,
    school_id        INT          NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id        INT          NOT NULL,
    user_id          BIGINT       NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    first_name       VARCHAR(100) NOT NULL,
    last_name        VARCHAR(100),
    admission_number VARCHAR(50),
    grade            VARCHAR(20),
    section          VARCHAR(10),
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (school_id, branch_id, first_name, last_name, grade, section),
    UNIQUE (student_id, branch_id, school_id)
);

CREATE INDEX IF NOT EXISTS idx_students_school_branch ON students(school_id, branch_id);
```

---

## Table: `parents`
Scoped to `school_id` only. 1:1 with `users`.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS parents (
    parent_id       SERIAL       PRIMARY KEY,
    user_id         BIGINT       NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    school_id       INT          NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100),
    phone           VARCHAR(20),
    alternate_phone VARCHAR(20),
    email           VARCHAR(150),
    address         TEXT,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_parents_school ON parents(school_id);
```

---

## Table: `student_parents`
M:N link between students and parents.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS student_parents (
    id           SERIAL      PRIMARY KEY,
    student_id   INT         NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    parent_id    INT         NOT NULL REFERENCES parents(parent_id)   ON DELETE CASCADE,
    relationship VARCHAR(50),
    is_primary   BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (student_id, parent_id)
);
```

---

## Table: `trips`
1 per route per day per trip_type.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS trips (
    trip_id      SERIAL           PRIMARY KEY,
    school_id    INT              NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id    INT              NOT NULL,
    route_id     INT              NOT NULL REFERENCES routes(route_id),
    driver_id    INT              REFERENCES drivers(driver_id),
    bus_id       INT              REFERENCES buses(bus_id),
    trip_type    trip_type_enum   NOT NULL,
    trip_status  trip_status_enum NOT NULL DEFAULT 'SCHEDULED',
    service_date DATE             NOT NULL,
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ      NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (school_id, branch_id, route_id, service_date, trip_type)
);
```

---

## Table: `trip_live_status`
1:1 with trips — live GPS snapshot.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS trip_live_status (
    id           SERIAL       PRIMARY KEY,
    trip_id      INT          NOT NULL UNIQUE REFERENCES trips(trip_id) ON DELETE CASCADE,
    school_id    INT          NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id    INT          NOT NULL,
    latitude     DECIMAL(9,6),
    longitude    DECIMAL(9,6),
    speed        DECIMAL(5,2),
    last_stop_id INT          REFERENCES stops(stop_id),
    recorded_at  TIMESTAMPTZ,
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE
);
```

---

## Table: `student_route_assignments`
Links student → route + stop (per PICKUP or DROP).
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS student_route_assignments (
    id              SERIAL         PRIMARY KEY,
    student_id      INT            NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    route_id        INT            NOT NULL REFERENCES routes(route_id),
    stop_id         INT            NOT NULL REFERENCES stops(stop_id),
    school_id       INT            NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id       INT            NOT NULL,
    assignment_type trip_type_enum NOT NULL,
    is_active       BOOLEAN        NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (student_id, route_id, assignment_type, school_id, branch_id)
);
```

---

## Table: `student_attendance`
Per-trip attendance record per student.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS student_attendance (
    id                  SERIAL                 PRIMARY KEY,
    student_id          INT                    NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    trip_id             INT                    NOT NULL REFERENCES trips(trip_id),
    stop_id             INT                    REFERENCES stops(stop_id),
    school_id           INT                    NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id           INT                    NOT NULL,
    assignment_type     trip_type_enum         NOT NULL,
    attendance_status   attendance_status_enum NOT NULL,
    marked_by_driver_id INT                    REFERENCES drivers(driver_id),
    marked_at           TIMESTAMPTZ,
    created_at          TIMESTAMPTZ            NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ            NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (student_id, trip_id, assignment_type, school_id, branch_id)
);
```

---

## Table: `notification_logs`
Append-only notification records.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS notification_logs (
    id                  SERIAL                   PRIMARY KEY,
    user_id             BIGINT                   NOT NULL REFERENCES users(user_id),
    student_id          INT                      REFERENCES students(student_id),
    trip_id             INT                      REFERENCES trips(trip_id),
    school_id           INT                      NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id           INT                      NOT NULL,
    notification_type   notification_type_enum   NOT NULL,
    notification_status notification_status_enum NOT NULL DEFAULT 'PENDING',
    channel             channel_enum             NOT NULL,
    message             TEXT,
    event_key           VARCHAR(255),
    sent_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ              NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ              NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_notification_logs_event_key
    ON notification_logs(user_id, event_key)
    WHERE event_key IS NOT NULL;
```

---

## Table: `gps_logs`
Append-only, high-volume GPS ping stream.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS gps_logs (
    log_id      BIGSERIAL    PRIMARY KEY,
    device_id   INT          NOT NULL REFERENCES gps_devices(device_id),
    trip_id     INT          REFERENCES trips(trip_id) ON DELETE SET NULL,
    school_id   INT          NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id   INT          NOT NULL,
    latitude    DECIMAL(9,6) NOT NULL,
    longitude   DECIMAL(9,6) NOT NULL,
    speed       DECIMAL(5,2),
    accuracy    DECIMAL(6,2),
    ignition_on BOOLEAN,
    recorded_at TIMESTAMPTZ  NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_gps_logs_device_id   ON gps_logs(device_id);
CREATE INDEX IF NOT EXISTS idx_gps_logs_trip_id     ON gps_logs(trip_id);
CREATE INDEX IF NOT EXISTS idx_gps_logs_recorded_at ON gps_logs(recorded_at);
```

---

## Table: `bus_device_assignments`
Device swap history.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS bus_device_assignments (
    id            SERIAL      PRIMARY KEY,
    bus_id        INT         NOT NULL REFERENCES buses(bus_id),
    device_id     INT         NOT NULL REFERENCES gps_devices(device_id),
    school_id     INT         NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id     INT         NOT NULL,
    assigned_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    unassigned_at TIMESTAMPTZ DEFAULT NULL,

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_bus_device_active_bus
    ON bus_device_assignments(bus_id)
    WHERE unassigned_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_bus_device_active_device
    ON bus_device_assignments(device_id)
    WHERE unassigned_at IS NULL;
```

---

## Table: `student_leave_requests`
Date-range leave requests per student.
> **Change:** `TIMESTAMP` → `TIMESTAMPTZ`

```sql
CREATE TABLE IF NOT EXISTS student_leave_requests (
    id           SERIAL                            PRIMARY KEY,
    student_id   INT                               NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    school_id    INT                               NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id    INT                               NOT NULL,
    requested_by BIGINT                            REFERENCES users(user_id) ON DELETE SET NULL,
    start_date   DATE                              NOT NULL,
    end_date     DATE                              NOT NULL,
    reason       TEXT,
    status       student_leave_request_status_enum NOT NULL DEFAULT 'PENDING',
    created_at   TIMESTAMPTZ                       NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ                       NOT NULL DEFAULT NOW(),

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_leave_student    ON student_leave_requests(student_id);
CREATE INDEX IF NOT EXISTS idx_leave_status     ON student_leave_requests(status);
CREATE INDEX IF NOT EXISTS idx_leave_date_range ON student_leave_requests(start_date, end_date);
```

---

## 🔗 Foreign Key Map

```
schools.school_id              ← branches.school_id
schools.school_id              ← users (via user_roles)
schools.school_id              ← drivers.school_id
schools.school_id              ← buses.school_id
schools.school_id              ← gps_devices.school_id
schools.school_id              ← routes.school_id
schools.school_id              ← stops.school_id
schools.school_id              ← students.school_id
schools.school_id              ← parents.school_id
schools.school_id              ← trips.school_id
branches(branch_id, school_id) ← user_roles(branch_id, school_id)
branches(branch_id, school_id) ← drivers(branch_id, school_id)
branches(branch_id, school_id) ← buses(branch_id, school_id)
branches(branch_id, school_id) ← gps_devices(branch_id, school_id)
branches(branch_id, school_id) ← routes(branch_id, school_id)
branches(branch_id, school_id) ← stops(branch_id, school_id)
branches(branch_id, school_id) ← route_stops(branch_id, school_id)
branches(branch_id, school_id) ← students(branch_id, school_id)
branches(branch_id, school_id) ← trips(branch_id, school_id)
branches(branch_id, school_id) ← trip_live_status(branch_id, school_id)
branches(branch_id, school_id) ← student_route_assignments(branch_id, school_id)
branches(branch_id, school_id) ← student_attendance(branch_id, school_id)
branches(branch_id, school_id) ← notification_logs(branch_id, school_id)
branches(branch_id, school_id) ← gps_logs(branch_id, school_id)
branches(branch_id, school_id) ← bus_device_assignments(branch_id, school_id)
branches(branch_id, school_id) ← student_leave_requests(branch_id, school_id)
users.user_id                  ← user_roles.user_id
users.user_id                  ← refresh_tokens.user_id
users.user_id                  ← drivers.user_id
users.user_id                  ← students.user_id
users.user_id                  ← parents.user_id
users.user_id                  ← notification_logs.user_id
users.user_id                  ← student_leave_requests.requested_by
roles.role_id                  ← user_roles.role_id
drivers.driver_id              ← trips.driver_id
drivers.driver_id              ← student_attendance.marked_by_driver_id
buses.bus_id                   ← trips.bus_id
buses.bus_id                   ← bus_device_assignments.bus_id
gps_devices.device_id          ← bus_device_assignments.device_id
gps_devices.device_id          ← gps_logs.device_id
routes.route_id                ← route_stops.route_id
routes.route_id                ← trips.route_id
routes.route_id                ← student_route_assignments.route_id
stops.stop_id                  ← route_stops.stop_id
stops.stop_id                  ← student_route_assignments.stop_id
stops.stop_id                  ← student_attendance.stop_id
stops.stop_id                  ← trip_live_status.last_stop_id
students.student_id            ← student_parents.student_id
students.student_id            ← student_route_assignments.student_id
students.student_id            ← student_attendance.student_id
students.student_id            ← notification_logs.student_id
students.student_id            ← student_leave_requests.student_id
parents.parent_id              ← student_parents.parent_id
trips.trip_id                  ← trip_live_status.trip_id       (CASCADE DELETE)
trips.trip_id                  ← student_attendance.trip_id
trips.trip_id                  ← notification_logs.trip_id
trips.trip_id                  ← gps_logs.trip_id               (SET NULL on delete)
```

---

## 📊 Unique Constraints Summary

| Table | Unique Constraint |
|---|---|
| `branches` | `(branch_id, school_id)` |
| `users` | `user_name`, `email`, `phone` |
| `roles` | `role_name` |
| `refresh_tokens` | `token_hash` |
| `drivers` | `user_id`, `(driver_id, branch_id, school_id)` |
| `buses` | `(bus_id, branch_id, school_id)` |
| `gps_devices` | `device_imei`, `(device_id, branch_id, school_id)` |
| `routes` | `(route_code, branch_id, school_id)`, `(route_id, branch_id, school_id)` |
| `stops` | `(stop_name, branch_id, school_id)`, `(stop_id, branch_id, school_id)` |
| `route_stops` | `(route_id, trip_type, stop_id)`, `(route_id, trip_type, stop_sequence)` |
| `students` | `user_id`, `(school_id, branch_id, first_name, last_name, grade, section)`, `(student_id, branch_id, school_id)` |
| `parents` | `user_id` |
| `student_parents` | `(student_id, parent_id)` |
| `trips` | `(school_id, branch_id, route_id, service_date, trip_type)` |
| `trip_live_status` | `trip_id` |
| `student_route_assignments` | `(student_id, route_id, assignment_type, school_id, branch_id)` |
| `student_attendance` | `(student_id, trip_id, assignment_type, school_id, branch_id)` |
| `notification_logs` | `(user_id, event_key)` WHERE `event_key IS NOT NULL` |
| `bus_device_assignments` | `bus_id` WHERE `unassigned_at IS NULL`, `device_id` WHERE `unassigned_at IS NULL` |

---

## Enum Values

| Column | Values |
|---|---|
| `roles.role_name` | `SUPER_ADMIN`, `SCHOOL_ADMIN`, `BRANCH_ADMIN`, `DRIVER`, `PARENT`, `STUDENT` |
| `route_stops.trip_type` | `PICKUP`, `DROPOFF` |
| `trips.trip_type` | `PICKUP`, `DROPOFF` |
| `trips.trip_status` | `SCHEDULED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED` |
| `student_attendance.attendance_status` | `BOARDED`, `DROPPED`, `NO_SHOW` |
| `student_route_assignments.assignment_type` | `PICKUP`, `DROPOFF` |
| `notification_logs.notification_type` | `ATTENDANCE`, `TRIP_START`, `TRIP_END`, `DELAY`, `GENERAL` |
| `notification_logs.notification_status` | `PENDING`, `SENT`, `FAILED`, `READ` |
| `notification_logs.channel` | `PUSH`, `SMS`, `EMAIL`, `WHATSAPP` |
| `student_leave_requests.status` | `PENDING`, `APPROVED`, `REJECTED` |

---

## 🧩 Key Design Decisions

| Decision | Rationale |
|---|---|
| All timestamps use `TIMESTAMPTZ` | Correct across server timezones and DST — eliminates naive datetime risks |
| `schools.school_name` instead of `name` | Consistent fully-qualified naming across the codebase |
| `refresh_tokens` added | JWT refresh token storage — hashed, never raw |
| Multi-tenant via `(branch_id, school_id)` composite FKs | Every resource scoped to a branch — cross-table isolation at DB level |
| `routes` has no `trip_type` — split in `route_stops` and `trips` | A route is a physical path — PICKUP/DROP ordering defined in `route_stops.trip_type` |
| Students assigned to `routes` directly | Each direction requires a separate `student_route_assignments` row with `assignment_type` |
| `student_parents` M:N table | Multiple guardians per student with relationship labels and primary-contact flag |
| `trip_live_status` separate from `gps_logs` | Avoids expensive `ORDER BY recorded_at DESC LIMIT 1` at high ping volume |
| Leave requests use date range (`start_date` / `end_date`) | Supports multi-day absences with a single record |
| `bus_device_assignments` uses partial unique indexes | `WHERE unassigned_at IS NULL` allows historical rows while enforcing one active device per bus |
| `event_key` deduplication on `notification_logs` | Prevents duplicate push/SMS for the same logical event per user |
| GPS logs include `accuracy` and `ignition_on` | Enables filtering low-quality pings and detecting engine state |
