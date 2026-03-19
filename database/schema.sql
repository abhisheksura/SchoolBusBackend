-- ========== ENUMS ==========

CREATE TYPE role_name_enum AS ENUM ('SUPER_ADMIN', 'SCHOOL_ADMIN', 'BRANCH_ADMIN', 'DRIVER', 'PARENT', 'STUDENT');
CREATE TYPE trip_type_enum AS ENUM ('PICKUP', 'DROP');
CREATE TYPE trip_status_enum AS ENUM ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED');
CREATE TYPE attendance_status_enum AS ENUM ('BOARDED', 'DROPPED', 'NO_SHOW');
CREATE TYPE notification_status_enum AS ENUM ('PENDING', 'SENT', 'FAILED', 'READ');
CREATE TYPE notification_type_enum AS ENUM ('ATTENDANCE', 'TRIP_START', 'TRIP_END', 'DELAY', 'GENERAL');
CREATE TYPE channel_enum AS ENUM ('PUSH', 'SMS', 'EMAIL', 'WHATSAPP');
CREATE TYPE student_leave_request_status_enum AS ENUM ('PENDING', 'APPROVED', 'REJECTED');


-- ========== 1. SCHOOLS ==========
CREATE TABLE IF NOT EXISTS schools (
    school_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========== 2. BRANCHES ==========
CREATE TABLE IF NOT EXISTS branches (
    branch_id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_name VARCHAR(150) NOT NULL,
    branch_address TEXT,
    branch_phone VARCHAR(20),
    branch_email VARCHAR(255),
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (branch_id, school_id)
);

CREATE INDEX idx_branches_school_id ON branches(school_id);

-- ========== 3. USERS ==========
CREATE TABLE IF NOT EXISTS users (
    user_id BIGSERIAL PRIMARY KEY,
    user_name VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20) UNIQUE,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ========== 4. ROLES (RBAC) ==========

CREATE TABLE IF NOT EXISTS roles (
    role_id SERIAL PRIMARY KEY,
    role_name role_name_enum UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========== 5. USER ROLES (RBAC) ==========

CREATE TABLE IF NOT EXISTS user_roles (
    user_role_id BIGSERIAL PRIMARY KEY,

    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id INT NOT NULL REFERENCES roles(role_id),

    school_id INT REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id INT, -- NULL = school-level role
    role_name role_name_enum NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,

    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

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


-- ========== 6. DRIVERS ==========
CREATE TABLE IF NOT EXISTS drivers (
    driver_id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    school_id INT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id INT NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100),
    phone VARCHAR(20),
    license_number VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
   
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE(driver_id, branch_id, school_id)
);


-- ========== 7. BUSES ==========
CREATE TABLE IF NOT EXISTS buses (
    bus_id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id INT NOT NULL,
    bus_number VARCHAR(50) NOT NULL,
    capacity INT NOT NULL CHECK (capacity > 0),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (bus_id, branch_id, school_id)
);

-- ========== 8. GPS DEVICES ==========
CREATE TABLE IF NOT EXISTS gps_devices (
    device_id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    branch_id INT NOT NULL,
    device_imei VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE (device_id, branch_id, school_id)
);


-- ========== 9. ROUTES ==========
CREATE TABLE IF NOT EXISTS routes (
    route_id SERIAL PRIMARY KEY,
    school_id INT NOT NULL,
    branch_id INT NOT NULL,
    route_code VARCHAR(50) NOT NULL,
    route_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,
    -- Composite Foreign Key: branch belongs to school
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    UNIQUE(route_code, branch_id, school_id),
    UNIQUE(route_id, branch_id, school_id)
);


-- ========== 10. STOPS ==========
CREATE TABLE IF NOT EXISTS  stops (
    stop_id SERIAL PRIMARY KEY,
    school_id INT NOT NULL,
    branch_id INT NOT NULL,
    stop_name VARCHAR(255) NOT NULL,
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,
    -- Prevent duplicate stops in same branch
    UNIQUE (stop_name, branch_id, school_id),
    UNIQUE (stop_id, branch_id, school_id),

    -- Validation
    CONSTRAINT valid_latitude CHECK (latitude BETWEEN -90 AND 90),
    CONSTRAINT valid_longitude CHECK (longitude BETWEEN -180 AND 180)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_stops_school_branch
ON stops(school_id, branch_id);

CREATE INDEX IF NOT EXISTS idx_stops_lat_lng
ON stops(latitude, longitude);


-- ========== 11. ROUTE STOPS ==========

CREATE TABLE IF NOT EXISTS route_stops (
    route_stop_id SERIAL PRIMARY KEY,

    route_id INT NOT NULL,
    stop_id INT NOT NULL,

    school_id INT NOT NULL,
    branch_id INT NOT NULL,

    trip_type trip_type_enum NOT NULL, -- PICKUP / DROPOFF
    stop_sequence INT NOT NULL CHECK (stop_sequence > 0),

    estimated_time TIME,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    FOREIGN KEY (route_id)
        REFERENCES routes(route_id)
        ON DELETE CASCADE,

    FOREIGN KEY (stop_id)
        REFERENCES stops(stop_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    -- Prevent duplicate stop in same route + type
    UNIQUE(route_id, trip_type, stop_id),

    -- Ensure unique sequence per route + type
    UNIQUE(route_id, trip_type, stop_sequence)
);

-- Performance index
CREATE INDEX IF NOT EXISTS idx_route_stops_route_type
ON route_stops(route_id, trip_type);

-- ========== 12. STUDENTS ==========
CREATE TABLE IF NOT EXISTS students (
    student_id SERIAL PRIMARY KEY,
    school_id INT NOT NULL,
    branch_id INT NOT NULL,
    user_id BIGINT NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100),
    admission_number VARCHAR(50),
    grade VARCHAR(20),
    section VARCHAR(10),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,
    -- Foreign Keys
    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,
    UNIQUE (school_id, branch_id, first_name, last_name, grade, section),
    UNIQUE (student_id, branch_id, school_id)

);

-- Indexes

CREATE INDEX IF NOT EXISTS idx_students_school_branch
ON students(school_id, branch_id);

-- ========== 13. PARENTS ==========


CREATE TABLE IF NOT EXISTS parents (
    parent_id SERIAL PRIMARY KEY,

    user_id BIGINT NOT NULL UNIQUE, -- 1:1 with users

    school_id INT NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100),
    phone VARCHAR(20),
    alternate_phone VARCHAR(20),
    email VARCHAR(150),

    address TEXT,

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    FOREIGN KEY (school_id)
        REFERENCES schools(school_id)
        ON DELETE CASCADE
);

-- Index
CREATE INDEX IF NOT EXISTS idx_parents_school
ON parents(school_id);

-- ========== 14. STUDENT PARENTS ==========

CREATE TABLE IF NOT EXISTS student_parents (
    student_parent_id SERIAL PRIMARY KEY,

    student_id INT NOT NULL,
    parent_id INT NOT NULL,

    relationship VARCHAR(50) NOT NULL, 
    -- e.g., FATHER, MOTHER, GUARDIAN

    is_primary BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    FOREIGN KEY (student_id)
        REFERENCES students(student_id)
        ON DELETE CASCADE,

    FOREIGN KEY (parent_id)
        REFERENCES parents(parent_id)
        ON DELETE CASCADE,

    -- Prevent duplicate mappings
    UNIQUE(student_id, parent_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_student_parents_student
ON student_parents(student_id);

CREATE INDEX IF NOT EXISTS idx_student_parents_parent
ON student_parents(parent_id);


-- ========== 15. TRIPS ==========
CREATE TABLE IF NOT EXISTS trips (
    trip_id SERIAL PRIMARY KEY,
    school_id INT NOT NULL,
    branch_id INT NOT NULL,
    route_id INT NOT NULL,
    bus_id INT,
    driver_id INT,
    service_date DATE NOT NULL,
    trip_type trip_type_enum NOT NULL, --PICKUP / DROPOFF
    trip_status trip_status_enum DEFAULT 'SCHEDULED',
    actual_start_time TIMESTAMP,
    actual_end_time TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (route_id) REFERENCES routes(route_id) ON DELETE CASCADE,
    FOREIGN KEY (bus_id) REFERENCES buses(bus_id) ON DELETE SET NULL,
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id) ON DELETE SET NULL,
    FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,
    UNIQUE (school_id, branch_id, route_id, service_date, trip_type)
);

CREATE INDEX IF NOT EXISTS idx_trips_lookup
ON trips(school_id, service_date, route_id);



-- ========== 16. TRIP LIVE STATUS ==========
CREATE TABLE IF NOT EXISTS trip_live_status (
    live_status_id SERIAL PRIMARY KEY,
    school_id INT NOT NULL,
    branch_id INT NOT NULL,
    trip_id INT NOT NULL UNIQUE,
    current_latitude DECIMAL(9,6) NOT NULL,
    current_longitude DECIMAL(9,6) NOT NULL,
    speed DECIMAL(5,2),
    heading DECIMAL(5,2),
    last_stop_id INT,
    last_stop_arrival_time TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
    FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,
    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,
    FOREIGN KEY (last_stop_id, branch_id, school_id)
        REFERENCES stops(stop_id, branch_id, school_id)
);
CREATE INDEX IF NOT EXISTS idx_live_status_trip
ON trip_live_status(trip_id);

CREATE INDEX IF NOT EXISTS idx_live_status_updated
ON trip_live_status(last_updated);



-- ========== 17. STUDENT ROUTE ASSIGNMENTS ==========


CREATE TABLE IF NOT EXISTS student_route_assignments (
    assignment_id SERIAL PRIMARY KEY,

    school_id INT NOT NULL,
    branch_id INT NOT NULL,

    student_id INT NOT NULL,
    route_id INT NOT NULL,
    stop_id INT NOT NULL,

    assignment_type VARCHAR(10) NOT NULL
        CHECK (assignment_type IN ('PICKUP', 'DROP')),

    is_active BOOLEAN DEFAULT TRUE,

    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Composite Foreign Keys (Tenant-safe)
    FOREIGN KEY (student_id, branch_id, school_id)
        REFERENCES students(student_id, branch_id, school_id)
        ON DELETE CASCADE,

    FOREIGN KEY (route_id, branch_id, school_id)
        REFERENCES routes(route_id, branch_id, school_id)
        ON DELETE CASCADE,

    FOREIGN KEY (stop_id, branch_id, school_id)
        REFERENCES stops(stop_id, branch_id, school_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    FOREIGN KEY (school_id)
        REFERENCES schools(school_id)
        ON DELETE CASCADE,

    -- Prevent duplicates
    UNIQUE (student_id, route_id, assignment_type, school_id, branch_id)
);

CREATE INDEX IF NOT EXISTS idx_sra_student
ON student_route_assignments(student_id);

CREATE INDEX IF NOT EXISTS idx_sra_route
ON student_route_assignments(route_id);

CREATE INDEX IF NOT EXISTS idx_sra_branch
ON student_route_assignments(branch_id, school_id);

-- ========== 18. ATTENDANCE ==========

CREATE TABLE IF NOT EXISTS student_attendance (
    attendance_id SERIAL PRIMARY KEY,

    school_id INT NOT NULL,
    branch_id INT NOT NULL,

    student_id INT NOT NULL,
    trip_id INT NOT NULL,

    assignment_type trip_type_enum NOT NULL,

    attendance_status attendance_status_enum NOT NULL,

    stop_id INT,

    marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    marked_by_driver_id INT,

    -- Tenant-safe FKs
    FOREIGN KEY (student_id, branch_id, school_id)
        REFERENCES students(student_id, branch_id, school_id)
        ON DELETE CASCADE,

    FOREIGN KEY (trip_id)
        REFERENCES trips(trip_id)
        ON DELETE CASCADE,

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    FOREIGN KEY (school_id)
        REFERENCES schools(school_id)
        ON DELETE CASCADE,

    FOREIGN KEY (stop_id, branch_id, school_id)
        REFERENCES stops(stop_id, branch_id, school_id)
        ON DELETE SET NULL,

    FOREIGN KEY (marked_by_driver_id, branch_id, school_id)
        REFERENCES drivers(driver_id, branch_id, school_id)
        ON DELETE SET NULL,

    -- Prevent duplicates
    UNIQUE (student_id, trip_id, assignment_type, school_id, branch_id)
);

CREATE INDEX IF NOT EXISTS idx_attendance_trip
ON student_attendance(trip_id);

CREATE INDEX IF NOT EXISTS idx_attendance_student
ON student_attendance(student_id);

CREATE INDEX IF NOT EXISTS idx_attendance_branch
ON student_attendance(branch_id, school_id);

CREATE INDEX IF NOT EXISTS idx_attendance_driver
ON student_attendance(marked_by_driver_id);

-- ========== 19. NOTIFICATION LOGS ==========

CREATE TABLE IF NOT EXISTS notification_logs (
    notification_id SERIAL PRIMARY KEY,

    school_id INT NOT NULL,
    branch_id INT,

    user_id BIGINT NOT NULL, -- who receives

    student_id INT,
    trip_id INT,

    title TEXT NOT NULL,
    message TEXT NOT NULL,

    notification_type notification_type_enum NOT NULL,
    notification_status notification_status_enum NOT NULL DEFAULT 'PENDING',
    event_key VARCHAR(255),
    channel channel_enum,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Tenant-safe FKs
    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    FOREIGN KEY (student_id, branch_id, school_id)
        REFERENCES students(student_id, branch_id, school_id)
        ON DELETE SET NULL,

    FOREIGN KEY (trip_id)
        REFERENCES trips(trip_id)
        ON DELETE CASCADE,

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    FOREIGN KEY (school_id)
        REFERENCES schools(school_id)
        ON DELETE CASCADE
);


CREATE INDEX IF NOT EXISTS idx_notifications_user
ON notification_logs(user_id);

CREATE INDEX IF NOT EXISTS idx_notifications_trip
ON notification_logs(trip_id);

CREATE INDEX IF NOT EXISTS idx_notifications_status
ON notification_logs(notification_status);

CREATE INDEX IF NOT EXISTS idx_notifications_sent_at
ON notification_logs(sent_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_user_event
ON notification_logs(user_id, event_key)
WHERE event_key IS NOT NULL;

-- ========== 20. GPS LOGS ==========

CREATE TABLE IF NOT EXISTS gps_logs (
    gps_log_id BIGSERIAL PRIMARY KEY,

    school_id INT NOT NULL,
    branch_id INT NOT NULL,

    device_id INT NOT NULL,
    trip_id INT,

    latitude DECIMAL(9,6) NOT NULL,
    longitude DECIMAL(9,6) NOT NULL,

    speed DECIMAL(5,2),
    heading DECIMAL(5,2),
    accuracy DECIMAL(5,2),
    ignition_on BOOLEAN,

    recorded_at TIMESTAMP NOT NULL,

    -- Tenant-safe FKs
    FOREIGN KEY (device_id, branch_id, school_id)
        REFERENCES gps_devices(device_id, branch_id, school_id)
        ON DELETE CASCADE,

    FOREIGN KEY (trip_id)
        REFERENCES trips(trip_id)
        ON DELETE SET NULL,

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    FOREIGN KEY (school_id)
        REFERENCES schools(school_id)
        ON DELETE CASCADE
);


CREATE INDEX IF NOT EXISTS idx_gps_logs_device_time
ON gps_logs(device_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_gps_logs_trip_time
ON gps_logs(trip_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_gps_logs_branch_time
ON gps_logs(branch_id, school_id, recorded_at DESC);

-- ========== 21. BUS DEVICE ASSIGNMENTS ==========
CREATE TABLE IF NOT EXISTS bus_device_assignments (
    bus_device_id SERIAL PRIMARY KEY,

    school_id INT NOT NULL,
    branch_id INT NOT NULL,

    bus_id INT NOT NULL,
    device_id INT NOT NULL,

    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    unassigned_at TIMESTAMP,

    -- Tenant-safe FKs
    FOREIGN KEY (bus_id, branch_id, school_id)
        REFERENCES buses(bus_id, branch_id, school_id)
        ON DELETE CASCADE,

    FOREIGN KEY (device_id, branch_id, school_id)
        REFERENCES gps_devices(device_id, branch_id, school_id)
        ON DELETE CASCADE,

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    FOREIGN KEY (school_id)
        REFERENCES schools(school_id)
        ON DELETE CASCADE,

    -- Valid time range
    CHECK (unassigned_at IS NULL OR unassigned_at > assigned_at)
);

-- Active device per bus
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_device_per_bus
ON bus_device_assignments(bus_id)
WHERE unassigned_at IS NULL;

-- Active bus per device
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_bus_per_device
ON bus_device_assignments(device_id)
WHERE unassigned_at IS NULL;

-- Query history
CREATE INDEX IF NOT EXISTS idx_bus_device_history
ON bus_device_assignments(bus_id, assigned_at DESC);

-- ========== 22. STUDENT LEAVE REQUESTS ==========

CREATE TABLE IF NOT EXISTS student_leave_requests (
    leave_id SERIAL PRIMARY KEY,

    school_id INT NOT NULL,
    branch_id INT NOT NULL,

    student_id INT NOT NULL,
    requested_by BIGINT,

    start_date DATE NOT NULL,
    end_date DATE NOT NULL,

    reason TEXT,

    status student_leave_request_status_enum DEFAULT 'PENDING',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Validations
    CHECK (end_date >= start_date),

    -- FKs (tenant-safe)
    FOREIGN KEY (student_id)
        REFERENCES students(student_id)
        ON DELETE CASCADE,

    FOREIGN KEY (requested_by)
        REFERENCES users(user_id)
        ON DELETE SET NULL,

    FOREIGN KEY (branch_id, school_id)
        REFERENCES branches(branch_id, school_id)
        ON DELETE CASCADE,

    FOREIGN KEY (school_id)
        REFERENCES schools(school_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_leave_student
ON student_leave_requests(student_id);

CREATE INDEX IF NOT EXISTS idx_leave_status
ON student_leave_requests(status);

CREATE INDEX IF NOT EXISTS idx_leave_date_range
ON student_leave_requests(start_date, end_date);
