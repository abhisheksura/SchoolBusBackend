# 🗄️ School Bus Tracker — Database Schema Reference

> **Engine:** PostgreSQL
> **Last Updated:** March 2026
> Multi-tenant architecture — every resource is scoped to `school_id` and `branch_id`.
> All tables, columns, constraints, indexes, and relationships in one place.

---

## Tables Overview

| Table                        | PK Type    | Notes                                                        |
|------------------------------|------------|--------------------------------------------------------------|
| `schools`                    | serial     | Top-level tenant                                             |
| `branches`                   | serial     | Branch/campus under a school                                 |
| `users`                      | bigserial  | Every login account — no role stored here                    |
| `roles`                      | serial     | Seeded once, never changes                                   |
| `user_roles`                 | bigserial  | RBAC join table — one user can hold multiple scoped roles    |
| `drivers`                    | serial     | Scoped to `branch_id + school_id`                            |
| `buses`                      | serial     | Scoped to `branch_id + school_id`                            |
| `gps_devices`                | serial     | Scoped to `branch_id + school_id`                            |
| `routes`                     | serial     | Logical route — no PICKUP/DROP split at this level           |
| `stops`                      | serial     | Physical GPS-tagged locations, scoped to branch              |
| `route_stops`                | serial     | Ordered stop list per route **and** trip_type                |
| `students`                   | serial     | Scoped to `branch_id + school_id`                            |
| `parents`                    | serial     | Scoped to `school_id` — 1:1 with users                       |
| `student_parents`            | serial     | M:N link between students and parents with relationship type |
| `trips`                      | serial     | 1 per route per day per trip_type                            |
| `trip_live_status`           | serial     | 1:1 with trips — live GPS snapshot                          |
| `student_route_assignments`  | serial     | Links student → route + stop (per PICKUP or DROP)            |
| `student_attendance`         | serial     | Per-trip attendance record per student                       |
| `notification_logs`          | serial     | Append-only notification records                             |
| `gps_logs`                   | bigserial  | Append-only, high-volume GPS ping stream                     |
| `bus_device_assignments`     | serial     | Device swap history — active = `unassigned_at IS NULL`       |
| `student_leave_requests`     | serial     | Date-range leave requests per student                        |

---

### ENUMs

```sql
CREATE TYPE role_name_enum AS ENUM ('SUPER_ADMIN', 'SCHOOL_ADMIN', 'BRANCH_ADMIN', 'DRIVER', 'PARENT', 'STUDENT');
CREATE TYPE trip_type_enum AS ENUM ('PICKUP', 'DROP');
CREATE TYPE trip_status_enum AS ENUM ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED');
CREATE TYPE attendance_status_enum AS ENUM ('BOARDED', 'DROPPED', 'NO_SHOW');
CREATE TYPE notification_status_enum AS ENUM ('PENDING', 'SENT', 'FAILED', 'READ');
CREATE TYPE notification_type_enum AS ENUM ('ATTENDANCE', 'TRIP_START', 'TRIP_END', 'DELAY', 'GENERAL');
CREATE TYPE channel_enum AS ENUM ('PUSH', 'SMS', 'EMAIL', 'WHATSAPP');
CREATE TYPE student_leave_request_status_enum AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
```

---

### Table: `schools`
Top-level tenant. Every other resource traces back to a school.

```sql
CREATE TABLE IF NOT EXISTS schools (
    school_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### Table: `branches`
Branch or campus under a school. Most resources are scoped at the `(branch_id, school_id)` level.

```sql
CREATE TABLE IF NOT EXISTS branches (
    branch_id     SERIAL PRIMARY KEY,
    school_id     INT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_name   VARCHAR(150) NOT NULL,
    branch_address TEXT,
    branch_phone  VARCHAR(20),
    branch_email  VARCHAR(255),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (branch_id, school_id)
);

CREATE INDEX idx_branches_school_id ON branches(school_id);
```

---

### Table: `users`
Authentication table. Every login goes through here. Roles are stored in `user_roles`, not here.

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id       BIGSERIAL PRIMARY KEY,
    user_name     VARCHAR(50) NOT NULL UNIQUE,
    email         VARCHAR(255) UNIQUE,
    phone         VARCHAR(20) UNIQUE,
    password_hash TEXT NOT NULL,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Rules:**
- Soft delete only — set `is_active = false`
- Never expose `password_hash` in any API response
- No `role_id` column here — roles are managed through `user_roles`

---

### Table: `roles`
Seeded once. Maps role names to descriptions.

```sql
CREATE TABLE IF NOT EXISTS roles (
    role_id     SERIAL PRIMARY KEY,
    role_name   role_name_enum UNIQUE NOT NULL,
    description TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Seed values:** `SUPER_ADMIN`, `SCHOOL_ADMIN`, `BRANCH_ADMIN`, `DRIVER`, `PARENT`, `STUDENT`

---

### Table: `user_roles`
RBAC join table. A single user can hold multiple roles across different schools/branches.

```sql
CREATE TABLE IF NOT EXISTS user_roles (
    user_role_id BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id      INT NOT NULL REFERENCES roles(role_id),
    school_id    INT REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id    INT, -- NULL = school-level role
    role_name    role_name_enum NOT NULL,
    is_active    BOOLEAN DEFAULT TRUE,
    assigned_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    CHECK (
        (role_name = 'SUPER_ADMIN' AND school_id IS NULL AND branch_id IS NULL) OR
        (role_name = 'SCHOOL_ADMIN' AND school_id IS NOT NULL AND branch_id IS NULL) OR
        (role_name IN ('BRANCH_ADMIN','DRIVER','PARENT','STUDENT') AND school_id IS NOT NULL AND branch_id IS NOT NULL)
    )
);

CREATE INDEX idx_user_roles_user_id ON user_roles(user_id);
```

**Rules:**
- `SUPER_ADMIN` — no school or branch scope
- `SCHOOL_ADMIN` — school scope only, `branch_id IS NULL`
- `BRANCH_ADMIN`, `DRIVER`, `PARENT`, `STUDENT` — must have both `school_id` and `branch_id`

---

### Table: `drivers`
Scoped to a specific branch within a school.

```sql
CREATE TABLE IF NOT EXISTS drivers (
    driver_id      SERIAL PRIMARY KEY,
    user_id        BIGINT UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    school_id      INT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id      INT NOT NULL,
    first_name     VARCHAR(100) NOT NULL,
    last_name      VARCHAR(100),
    phone          VARCHAR(20),
    license_number VARCHAR(100),
    is_active      BOOLEAN DEFAULT TRUE,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE(driver_id, branch_id, school_id)
);
```

---

### Table: `buses`
Scoped to a specific branch within a school.

```sql
CREATE TABLE IF NOT EXISTS buses (
    bus_id     SERIAL PRIMARY KEY,
    school_id  INT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id  INT NOT NULL,
    bus_number VARCHAR(50) NOT NULL,
    capacity   INT NOT NULL CHECK (capacity > 0),
    is_active  BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (bus_id, branch_id, school_id)
);
```

---

### Table: `gps_devices`
Hardware GPS units, scoped to a branch.

```sql
CREATE TABLE IF NOT EXISTS gps_devices (
    device_id   SERIAL PRIMARY KEY,
    school_id   INT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id   INT NOT NULL,
    device_imei VARCHAR(100) UNIQUE NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (device_id, branch_id, school_id)
);
```

---

### Table: `routes`
Logical route — no PICKUP/DROP distinction at this level. That is handled in `route_stops` and `trips`.

```sql
CREATE TABLE IF NOT EXISTS routes (
    route_id    SERIAL PRIMARY KEY,
    school_id   INT NOT NULL,
    branch_id   INT NOT NULL,
    route_code  VARCHAR(50) NOT NULL,
    route_name  VARCHAR(100) NOT NULL,
    description TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE(route_code, branch_id, school_id),
    UNIQUE(route_id, branch_id, school_id)
);
```

> ⚠️ Unlike the previous schema, PICKUP and DROP are **not** separate route rows. A single route has stops ordered per `trip_type` inside `route_stops`.

---

### Table: `stops`
Physical GPS-tagged bus stops, scoped to a branch.

```sql
CREATE TABLE IF NOT EXISTS stops (
    stop_id    SERIAL PRIMARY KEY,
    school_id  INT NOT NULL,
    branch_id  INT NOT NULL,
    stop_name  VARCHAR(255) NOT NULL,
    latitude   DECIMAL(9,6),
    longitude  DECIMAL(9,6),
    is_active  BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (stop_name, branch_id, school_id),
    UNIQUE (stop_id, branch_id, school_id),

    CONSTRAINT valid_latitude  CHECK (latitude  BETWEEN -90  AND 90),
    CONSTRAINT valid_longitude CHECK (longitude BETWEEN -180 AND 180)
);

CREATE INDEX IF NOT EXISTS idx_stops_school_branch ON stops(school_id, branch_id);
CREATE INDEX IF NOT EXISTS idx_stops_lat_lng        ON stops(latitude, longitude);
```

---

### Table: `route_stops`
Ordered list of stops per route, split by `trip_type` (PICKUP / DROP).

```sql
CREATE TABLE IF NOT EXISTS route_stops (
    route_stop_id  SERIAL PRIMARY KEY,
    route_id       INT NOT NULL,
    stop_id        INT NOT NULL,
    school_id      INT NOT NULL,
    branch_id      INT NOT NULL,
    trip_type      trip_type_enum NOT NULL,
    stop_sequence  INT NOT NULL CHECK (stop_sequence > 0),
    estimated_time TIME,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (route_id)  REFERENCES routes(route_id) ON DELETE CASCADE,
    FOREIGN KEY (stop_id)   REFERENCES stops(stop_id)   ON DELETE RESTRICT,
    FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE(route_id, trip_type, stop_id),
    UNIQUE(route_id, trip_type, stop_sequence)
);

CREATE INDEX IF NOT EXISTS idx_route_stops_route_type ON route_stops(route_id, trip_type);
```

**Rules:**
- A stop cannot appear twice on the same route + trip_type combination
- Sequence must be unique per route + trip_type

---

### Table: `students`
Scoped to a specific branch. Login via `users` — `user_id` is mandatory.

```sql
CREATE TABLE IF NOT EXISTS students (
    student_id       SERIAL PRIMARY KEY,
    school_id        INT NOT NULL,
    branch_id        INT NOT NULL,
    user_id          BIGINT NOT NULL UNIQUE,
    first_name       VARCHAR(100) NOT NULL,
    last_name        VARCHAR(100),
    admission_number VARCHAR(50),
    grade            VARCHAR(20),
    section          VARCHAR(10),
    is_active        BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,

    UNIQUE (school_id, branch_id, first_name, last_name, grade, section),
    UNIQUE (student_id, branch_id, school_id)
);

CREATE INDEX IF NOT EXISTS idx_students_school_branch ON students(school_id, branch_id);
```

**Rules:**
- `is_active = false` excludes student from all trip/attendance queries
- Unlike the previous schema, `user_id` is **NOT** nullable — every student must have a login

---

### Table: `parents`
Scoped to `school_id` only (not branch). 1:1 with `users`.

```sql
CREATE TABLE IF NOT EXISTS parents (
    parent_id       SERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL UNIQUE,
    school_id       INT NOT NULL,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100),
    phone           VARCHAR(20),
    alternate_phone VARCHAR(20),
    email           VARCHAR(150),
    address         TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)   REFERENCES users(user_id)     ON DELETE CASCADE,
    FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_parents_school ON parents(school_id);
```

---

### Table: `student_parents`
M:N link between students and parents. Supports multiple parents/guardians per student.

```sql
CREATE TABLE IF NOT EXISTS student_parents (
    student_parent_id SERIAL PRIMARY KEY,
    student_id        INT NOT NULL,
    parent_id         INT NOT NULL,
    relationship      VARCHAR(50) NOT NULL, -- e.g. FATHER, MOTHER, GUARDIAN
    is_primary        BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id)  REFERENCES parents(parent_id)   ON DELETE CASCADE,

    UNIQUE(student_id, parent_id)
);

CREATE INDEX IF NOT EXISTS idx_student_parents_student ON student_parents(student_id);
CREATE INDEX IF NOT EXISTS idx_student_parents_parent  ON student_parents(parent_id);
```

---

### Table: `trips`
One trip per route per service date per trip_type. Links bus and driver at execution time.

```sql
CREATE TABLE IF NOT EXISTS trips (
    trip_id           SERIAL PRIMARY KEY,
    school_id         INT NOT NULL,
    branch_id         INT NOT NULL,
    route_id          INT NOT NULL,
    bus_id            INT,
    driver_id         INT,
    service_date      DATE NOT NULL,
    trip_type         trip_type_enum NOT NULL,
    trip_status       trip_status_enum DEFAULT 'SCHEDULED',
    actual_start_time TIMESTAMP,
    actual_end_time   TIMESTAMP,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (route_id)  REFERENCES routes(route_id)   ON DELETE CASCADE,
    FOREIGN KEY (bus_id)    REFERENCES buses(bus_id)      ON DELETE SET NULL,
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id) ON DELETE SET NULL,
    FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (school_id, branch_id, route_id, service_date, trip_type)
);

CREATE INDEX IF NOT EXISTS idx_trips_lookup ON trips(school_id, service_date, route_id);
```

**Rules:**
- `bus_id` and `driver_id` are nullable — SET NULL on delete to preserve historical records
- One trip per route per day per trip_type (UNIQUE enforced)
- Admin must cancel and recreate to reschedule

---

### Table: `trip_live_status`
Live GPS snapshot for an active trip. 1:1 with `trips`.

```sql
CREATE TABLE IF NOT EXISTS trip_live_status (
    live_status_id        SERIAL PRIMARY KEY,
    school_id             INT NOT NULL,
    branch_id             INT NOT NULL,
    trip_id               INT NOT NULL UNIQUE,
    current_latitude      DECIMAL(9,6) NOT NULL,
    current_longitude     DECIMAL(9,6) NOT NULL,
    speed                 DECIMAL(5,2),
    heading               DECIMAL(5,2),
    last_stop_id          INT,
    last_stop_arrival_time TIMESTAMP,
    last_updated          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (trip_id)   REFERENCES trips(trip_id)     ON DELETE CASCADE,
    FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,
    FOREIGN KEY (last_stop_id, branch_id, school_id)
        REFERENCES stops(stop_id, branch_id, school_id)
);

CREATE INDEX IF NOT EXISTS idx_live_status_trip    ON trip_live_status(trip_id);
CREATE INDEX IF NOT EXISTS idx_live_status_updated ON trip_live_status(last_updated);
```

**Rules:**
- Deleted automatically when the trip is deleted (CASCADE)
- Always query live position from here — **never** from `gps_logs`

---

### Table: `student_route_assignments`
Links a student to a specific route and boarding stop, separately for PICKUP and DROP.

```sql
CREATE TABLE IF NOT EXISTS student_route_assignments (
    assignment_id   SERIAL PRIMARY KEY,
    school_id       INT NOT NULL,
    branch_id       INT NOT NULL,
    student_id      INT NOT NULL,
    route_id        INT NOT NULL,
    stop_id         INT NOT NULL,
    assignment_type VARCHAR(10) NOT NULL CHECK (assignment_type IN ('PICKUP', 'DROP')),
    is_active       BOOLEAN DEFAULT TRUE,
    assigned_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (student_id, branch_id, school_id)
        REFERENCES students(student_id, branch_id, school_id) ON DELETE CASCADE,
    FOREIGN KEY (route_id, branch_id, school_id)
        REFERENCES routes(route_id, branch_id, school_id)     ON DELETE CASCADE,
    FOREIGN KEY (stop_id, branch_id, school_id)
        REFERENCES stops(stop_id, branch_id, school_id)       ON DELETE RESTRICT,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)             ON DELETE CASCADE,
    FOREIGN KEY (school_id)
        REFERENCES schools(school_id)                         ON DELETE CASCADE,

    UNIQUE (student_id, route_id, assignment_type, school_id, branch_id)
);

CREATE INDEX IF NOT EXISTS idx_sra_student  ON student_route_assignments(student_id);
CREATE INDEX IF NOT EXISTS idx_sra_route    ON student_route_assignments(route_id);
CREATE INDEX IF NOT EXISTS idx_sra_branch   ON student_route_assignments(branch_id, school_id);
```

> ⚠️ Students are assigned to `routes` directly. A separate row is required for PICKUP and DROP.

---

### Table: `student_attendance`
Per-trip attendance for each student.

```sql
CREATE TABLE IF NOT EXISTS student_attendance (
    attendance_id       SERIAL PRIMARY KEY,
    school_id           INT NOT NULL,
    branch_id           INT NOT NULL,
    student_id          INT NOT NULL,
    trip_id             INT NOT NULL,
    assignment_type     trip_type_enum NOT NULL,
    attendance_status   attendance_status_enum NOT NULL,
    stop_id             INT,
    marked_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    marked_by_driver_id INT,

    FOREIGN KEY (student_id, branch_id, school_id)
        REFERENCES students(student_id, branch_id, school_id) ON DELETE CASCADE,
    FOREIGN KEY (trip_id)   REFERENCES trips(trip_id)     ON DELETE CASCADE,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)             ON DELETE CASCADE,
    FOREIGN KEY (school_id) REFERENCES schools(school_id)     ON DELETE CASCADE,
    FOREIGN KEY (stop_id, branch_id, school_id)
        REFERENCES stops(stop_id, branch_id, school_id)       ON DELETE SET NULL,
    FOREIGN KEY (marked_by_driver_id, branch_id, school_id)
        REFERENCES drivers(driver_id, branch_id, school_id)   ON DELETE SET NULL,

    UNIQUE (student_id, trip_id, assignment_type, school_id, branch_id)
);

CREATE INDEX IF NOT EXISTS idx_attendance_trip    ON student_attendance(trip_id);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON student_attendance(student_id);
CREATE INDEX IF NOT EXISTS idx_attendance_branch  ON student_attendance(branch_id, school_id);
CREATE INDEX IF NOT EXISTS idx_attendance_driver  ON student_attendance(marked_by_driver_id);
```

**Attendance status values:** `BOARDED`, `DROPPED`, `NO_SHOW`

---

### Table: `notification_logs`
Append-only log of all notifications sent to users.

```sql
CREATE TABLE IF NOT EXISTS notification_logs (
    notification_id     SERIAL PRIMARY KEY,
    school_id           INT NOT NULL,
    branch_id           INT,
    user_id             BIGINT NOT NULL,
    student_id          INT,
    trip_id             INT,
    title               TEXT NOT NULL,
    message             TEXT NOT NULL,
    notification_type   notification_type_enum NOT NULL,
    notification_status notification_status_enum NOT NULL DEFAULT 'PENDING',
    event_key           VARCHAR(255),
    channel             channel_enum,
    sent_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id, branch_id, school_id)
        REFERENCES students(student_id, branch_id, school_id) ON DELETE SET NULL,
    FOREIGN KEY (trip_id)   REFERENCES trips(trip_id)     ON DELETE CASCADE,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)             ON DELETE CASCADE,
    FOREIGN KEY (school_id) REFERENCES schools(school_id)     ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notifications_user     ON notification_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_trip     ON notification_logs(trip_id);
CREATE INDEX IF NOT EXISTS idx_notifications_status   ON notification_logs(notification_status);
CREATE INDEX IF NOT EXISTS idx_notifications_sent_at  ON notification_logs(sent_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_user_event
ON notification_logs(user_id, event_key)
WHERE event_key IS NOT NULL;
```

**Notification types:** `ATTENDANCE`, `TRIP_START`, `TRIP_END`, `DELAY`, `GENERAL`
**Channels:** `PUSH`, `SMS`, `EMAIL`, `WHATSAPP`

**Rules:**
- Append-only — never UPDATE or DELETE
- `event_key` prevents duplicate notifications for the same logical event per user
- Status: `PENDING` → `SENT | FAILED | READ`

---

### Table: `gps_logs`
High-volume raw GPS stream. Every ping from a device is stored here.

```sql
CREATE TABLE IF NOT EXISTS gps_logs (
    gps_log_id  BIGSERIAL PRIMARY KEY,
    school_id   INT NOT NULL,
    branch_id   INT NOT NULL,
    device_id   INT NOT NULL,
    trip_id     INT,
    latitude    DECIMAL(9,6) NOT NULL,
    longitude   DECIMAL(9,6) NOT NULL,
    speed       DECIMAL(5,2),
    heading     DECIMAL(5,2),
    accuracy    DECIMAL(5,2),
    ignition_on BOOLEAN,
    recorded_at TIMESTAMP NOT NULL,

    FOREIGN KEY (device_id, branch_id, school_id)
        REFERENCES gps_devices(device_id, branch_id, school_id) ON DELETE CASCADE,
    FOREIGN KEY (trip_id)   REFERENCES trips(trip_id)       ON DELETE SET NULL,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)               ON DELETE CASCADE,
    FOREIGN KEY (school_id) REFERENCES schools(school_id)       ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_gps_logs_device_time  ON gps_logs(device_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_gps_logs_trip_time    ON gps_logs(trip_id,   recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_gps_logs_branch_time  ON gps_logs(branch_id, school_id, recorded_at DESC);
```

**Rules:**
- `trip_id` SET NULL on trip delete — preserves GPS history
- **Append-only — NEVER UPDATE or DELETE**
- Includes `accuracy` and `ignition_on` fields (new vs previous schema)
- **Never query for live position — use `trip_live_status` instead**
- **Purpose:** Historical audit trail, route replay, speed analytics

---

### Table: `bus_device_assignments`
Tracks which GPS device is assigned to which bus. Supports device swap history.

```sql
CREATE TABLE IF NOT EXISTS bus_device_assignments (
    bus_device_id  SERIAL PRIMARY KEY,
    school_id      INT NOT NULL,
    branch_id      INT NOT NULL,
    bus_id         INT NOT NULL,
    device_id      INT NOT NULL,
    assigned_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    unassigned_at  TIMESTAMP,

    FOREIGN KEY (bus_id, branch_id, school_id)
        REFERENCES buses(bus_id, branch_id, school_id)           ON DELETE CASCADE,
    FOREIGN KEY (device_id, branch_id, school_id)
        REFERENCES gps_devices(device_id, branch_id, school_id)  ON DELETE CASCADE,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)                ON DELETE CASCADE,
    FOREIGN KEY (school_id)
        REFERENCES schools(school_id)                            ON DELETE CASCADE,

    CHECK (unassigned_at IS NULL OR unassigned_at > assigned_at)
);

-- Only one active device per bus
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_device_per_bus
ON bus_device_assignments(bus_id)
WHERE unassigned_at IS NULL;

-- Only one active bus per device
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_bus_per_device
ON bus_device_assignments(device_id)
WHERE unassigned_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_bus_device_history ON bus_device_assignments(bus_id, assigned_at DESC);
```

**Rules:**
- Active assignment = `unassigned_at IS NULL`
- On reassignment: set `unassigned_at = now()` on old row, insert new row
- Partial unique indexes enforce one active device per bus and one active bus per device simultaneously

---

### Table: `student_leave_requests`
Date-range absence requests submitted by a parent or admin.

```sql
CREATE TABLE IF NOT EXISTS student_leave_requests (
    leave_id     SERIAL PRIMARY KEY,
    school_id    INT NOT NULL,
    branch_id    INT NOT NULL,
    student_id   INT NOT NULL,
    requested_by BIGINT,
    start_date   DATE NOT NULL,
    end_date     DATE NOT NULL,
    reason       TEXT,
    status       student_leave_request_status_enum DEFAULT 'PENDING',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (end_date >= start_date),

    FOREIGN KEY (student_id)   REFERENCES students(student_id)   ON DELETE CASCADE,
    FOREIGN KEY (requested_by) REFERENCES users(user_id)         ON DELETE SET NULL,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)                ON DELETE CASCADE,
    FOREIGN KEY (school_id)    REFERENCES schools(school_id)     ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_leave_student    ON student_leave_requests(student_id);
CREATE INDEX IF NOT EXISTS idx_leave_status     ON student_leave_requests(status);
CREATE INDEX IF NOT EXISTS idx_leave_date_range ON student_leave_requests(start_date, end_date);
```

**Rules:**
- Supports multi-day leaves via `start_date` / `end_date` range (unlike the previous schema's single `leave_date`)
- `requested_by` (user_id) is SET NULL on user delete — preserves the leave record
- Cancel via `status = REJECTED` — never hard-delete
- Defaults to `PENDING` — requires explicit approval

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

| Table                        | Unique Constraint                                                          |
|------------------------------|----------------------------------------------------------------------------|
| `branches`                   | `(branch_id, school_id)`                                                   |
| `users`                      | `user_name`, `email`, `phone`                                              |
| `roles`                      | `role_name`                                                                |
| `drivers`                    | `user_id`, `(driver_id, branch_id, school_id)`                             |
| `buses`                      | `(bus_id, branch_id, school_id)`                                           |
| `gps_devices`                | `device_imei`, `(device_id, branch_id, school_id)`                         |
| `routes`                     | `(route_code, branch_id, school_id)`, `(route_id, branch_id, school_id)`  |
| `stops`                      | `(stop_name, branch_id, school_id)`, `(stop_id, branch_id, school_id)`    |
| `route_stops`                | `(route_id, trip_type, stop_id)`, `(route_id, trip_type, stop_sequence)`  |
| `students`                   | `user_id`, `(school_id, branch_id, first_name, last_name, grade, section)`, `(student_id, branch_id, school_id)` |
| `parents`                    | `user_id`                                                                  |
| `student_parents`            | `(student_id, parent_id)`                                                  |
| `trips`                      | `(school_id, branch_id, route_id, service_date, trip_type)`               |
| `trip_live_status`           | `trip_id`                                                                  |
| `student_route_assignments`  | `(student_id, route_id, assignment_type, school_id, branch_id)`           |
| `student_attendance`         | `(student_id, trip_id, assignment_type, school_id, branch_id)`            |
| `notification_logs`          | `(user_id, event_key)` WHERE `event_key IS NOT NULL`                       |
| `bus_device_assignments`     | `bus_id` WHERE `unassigned_at IS NULL`, `device_id` WHERE `unassigned_at IS NULL` |

---

## Enum Values

| Column                                   | Values                                                              |
|------------------------------------------|---------------------------------------------------------------------|
| `roles.role_name`                        | `SUPER_ADMIN`, `SCHOOL_ADMIN`, `BRANCH_ADMIN`, `DRIVER`, `PARENT`, `STUDENT` |
| `route_stops.trip_type`                  | `PICKUP`, `DROP`                                                    |
| `trips.trip_type`                        | `PICKUP`, `DROP`                                                    |
| `trips.trip_status`                      | `SCHEDULED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`               |
| `student_attendance.attendance_status`   | `BOARDED`, `DROPPED`, `NO_SHOW`                                     |
| `student_route_assignments.assignment_type` | `PICKUP`, `DROP`                                                 |
| `notification_logs.notification_type`    | `ATTENDANCE`, `TRIP_START`, `TRIP_END`, `DELAY`, `GENERAL`         |
| `notification_logs.notification_status`  | `PENDING`, `SENT`, `FAILED`, `READ`                                 |
| `notification_logs.channel`              | `PUSH`, `SMS`, `EMAIL`, `WHATSAPP`                                  |
| `student_leave_requests.status`          | `PENDING`, `APPROVED`, `REJECTED`                                   |

---

## 🧩 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Multi-tenant via `(branch_id, school_id)` composite FKs | Every resource is scoped to a branch. Composite foreign keys enforce cross-table tenant isolation at the DB level. |
| `routes` has no `trip_type` — split happens in `route_stops` and `trips` | A route is a physical path. PICKUP and DROP ordering is defined in `route_stops.trip_type` and executed via a `trips` row per direction. |
| Students assigned to `routes` directly. Each direction requires a separate `student_route_assignments` row with `assignment_type = PICKUP` or `DROP`. |
| `student_parents` M:N table | Supports multiple guardians per student with relationship labels and a primary-contact flag, rather than the old single `parent_id` FK on students. |
| `trip_live_status` separate from `gps_logs` | Avoids expensive `ORDER BY recorded_at DESC LIMIT 1` queries at high ping volume. |
| Leave requests use date range (`start_date` / `end_date`) | Supports multi-day or holiday absences with a single record instead of one row per day. |
| `bus_device_assignments` uses partial unique indexes | `WHERE unassigned_at IS NULL` allows unlimited historical rows while enforcing only one active device per bus and one active bus per device simultaneously. |
| `event_key` deduplication on `notification_logs` | Prevents duplicate push/SMS for the same logical event (e.g. bus arriving at stop) per user, using a partial unique index. |
| GPS logs include `accuracy` and `ignition_on` | Enables filtering out low-quality pings and detecting engine state for smarter trip lifecycle management. |
