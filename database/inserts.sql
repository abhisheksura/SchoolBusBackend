INSERT INTO roles (role_name) VALUES
('SUPER_ADMIN'),
('SCHOOL_ADMIN'),
('BRANCH_ADMIN'),
('DRIVER'),
('PARENT'),
('STUDENT');

INSERT INTO schools (name)
VALUES 
('Green Valley School'),
('Sunrise Public School')
RETURNING school_id, name;


INSERT INTO branches (school_id, branch_name, branch_address)
VALUES
-- School 1 (2 branches)
(1, 'GV Main Campus', 'Koti'),
(1, 'GV North Campus', 'Secunderabad'),

-- School 2 (3 branches)
(2, 'Sunrise Main', 'Dilsukhnagar'),
(2, 'Sunrise East', 'Kukatpally'),
(2, 'Sunrise West', 'Chandanagar')
RETURNING branch_id, school_id, branch_name;


-- Ensure the extension is enabled for password hashing
CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO users (user_name, email, phone, password_hash)
VALUES
('superadmin',   NULL,                   '9000000001', crypt('superadmin',   gen_salt('bf', 12))),
('schooladmin1', 'schooladmin1@gvs.com', '9000000002', crypt('schooladmin1', gen_salt('bf', 12))),
('branchadmin1', 'branchadmin1@gvs.com', '9000000003', crypt('branchadmin1', gen_salt('bf', 12))),
('branchadmin2', 'branchadmin2@gvs.com', '9000000004', crypt('branchadmin2', gen_salt('bf', 12))),
('schooladmin2', 'schooladmin2@svs.com', '9000000005', crypt('schooladmin2', gen_salt('bf', 12))),
('branchadmin3', 'branchadmin3@svs.com', '9000000006', crypt('branchadmin3', gen_salt('bf', 12))),
('driver1',      'driver@gvs.com',       '9000000007', crypt('driverpass',   gen_salt('bf', 12))),
('parent1',      'parent@gvs.com',       '9000000008', crypt('parentpass',   gen_salt('bf', 12))),
('driver2_gv', 'driver2@gvs.com', '9000000009', crypt('pass123', gen_salt('bf', 10))),
('parent2_gv', 'parent2@gvs.com', '9000000010', crypt('pass123', gen_salt('bf', 10))),

-- School 2 (Sunrise Public) Staff & Parents
('driver3_sr', 'driver3@svs.com', '9000000011', crypt('pass123', gen_salt('bf', 10))),
('driver4_sr', 'driver4@svs.com', '9000000012', crypt('pass123', gen_salt('bf', 10))),
('parent3_sr', 'parent3@svs.com', '9000000013', crypt('pass123', gen_salt('bf', 10)))
RETURNING user_id, user_name;

INSERT INTO users (user_name, email, phone, password_hash)
VALUES
-- School 1 Students
('std_mark_gv',  NULL, '9000000014', crypt('stdpass1', gen_salt('bf', 10))),
('std_lucy_gv',  NULL, '9000000015', crypt('stdpass2', gen_salt('bf', 10))),

-- School 2 Students
('std_arjun_sr', NULL, '9000000016', crypt('stdpass3', gen_salt('bf', 10))),
('std_priya_sr', NULL, '9000000017', crypt('stdpass4', gen_salt('bf', 10)))
RETURNING user_id, user_name;


INSERT INTO user_roles (user_id, role_id, school_id, branch_id, role_name)
VALUES
-- 1. superadmin (User 1) -> SUPER_ADMIN (Role 1)
(1, 1, NULL, NULL, 'SUPER_ADMIN'),

-- 2. schooladmin1 (User 2) -> SCHOOL_ADMIN (Role 2) for Green Valley (School 1)
(2, 2, 1, NULL, 'SCHOOL_ADMIN'),

-- 3. branchadmin1 (User 3) -> BRANCH_ADMIN (Role 3) for GV Main (Branch 1, School 1)
(3, 3, 1, 1, 'BRANCH_ADMIN'),

-- 4. branchadmin2 (User 4) -> BRANCH_ADMIN (Role 3) for GV North (Branch 2, School 1)
(4, 3, 1, 2, 'BRANCH_ADMIN'),

-- 5. schooladmin2 (User 5) -> SCHOOL_ADMIN (Role 2) for Sunrise (School 2)
(5, 2, 2, NULL, 'SCHOOL_ADMIN'),

-- 6. branchadmin3 (User 6) -> BRANCH_ADMIN (Role 3) for Sunrise Main (Branch 3, School 2)
(6, 3, 2, 3, 'BRANCH_ADMIN'),

-- 7. driver1 (User 7) -> DRIVER (Role 4) for GV Main (Branch 1, School 1)
(7, 4, 1, 1, 'DRIVER'),

-- 8. parent1 (User 8) -> PARENT (Role 5) for GV Main (Branch 1, School 1)
(8, 5, 1, 1, 'PARENT')

RETURNING user_role_id, role_name;
INSERT INTO user_roles (user_id, role_id, school_id, branch_id, role_name)
VALUES
(9,  4, 1, 2, 'DRIVER'),       -- driver2_gv -> GV North (Br 2)
(10, 5, 1, 2, 'PARENT'),       -- parent2_gv -> GV North (Br 2)
(11, 4, 2, 3, 'DRIVER'),       -- driver3_sr -> Sunrise Main (Br 3)
(12, 4, 2, 4, 'DRIVER'),       -- driver4_sr -> Sunrise East (Br 4)
(13, 5, 2, 3, 'PARENT')        -- parent3_sr -> Sunrise Main (Br 3)
RETURNING user_role_id, role_name;

--INSERT INTO user_roles (user_id, role_id, school_id, branch_id, role_name)
--VALUES
--(14, 6, 1, 1, 'STUDENT'),
--(15, 6, 1, 2, 'STUDENT'),
--(16, 6, 2, 3, 'STUDENT'),
--(17, 6, 2, 3, 'STUDENT');


/*
============ Drivers ============
*/


INSERT INTO drivers (user_id, school_id, branch_id, first_name, last_name, phone, license_number)
VALUES
(7, 1, 1, 'John', 'Driver', '9000000007', 'LIC-GV-2024-001')
RETURNING driver_id, first_name, last_name;
INSERT INTO drivers (user_id, school_id, branch_id, first_name, last_name, phone, license_number)
VALUES
(9,  1, 2, 'Robert', 'Smith', '9000000009', 'LIC-GV-2024-002'),
(11, 2, 3, 'Amit', 'Kumar',   '9000000011', 'LIC-SR-2024-001'),
(12, 2, 4, 'Suresh', 'Raina', '9000000012', 'LIC-SR-2024-002');



/*
============ PARENTS ============
*/


INSERT INTO parents (user_id, school_id, first_name, last_name, phone, email, address)
VALUES
(8, 1, 'Jane', 'Parent', '9000000008', 'parent@gvs.com', 'Flat 402, Sunrise Apartments, Hyderabad')
RETURNING parent_id, first_name, last_name;

INSERT INTO parents (user_id, school_id, first_name, last_name, phone, email, address)
VALUES
(10, 1, 'Sarah', 'Connor', '9000000010', 'parent2@gvs.com', 'North Sector, Secunderabad'),
(13, 2, 'Vijay', 'Verma',  '9000000013', 'parent3@svs.com', 'Electronic City, Bangalore');



/*
============ STUDENTS ============
*/


INSERT INTO students (school_id, branch_id, user_id, first_name, last_name, admission_number, grade, section)
VALUES
-- Green Valley (School 1)
(1, 1, 14, 'Mark', 'Parent', 'GVS-101', '5th', 'A'), -- Child of Jane (Parent ID 1)
(1, 2, 15, 'Lucy', 'Connor', 'GVS-202', '3rd', 'B'), -- Child of Sarah (Parent ID 2)

-- Sunrise Public (School 2)
(2, 3, 16, 'Arjun', 'Verma', 'SVS-301', '7th', 'C'), -- Child of Vijay (Parent ID 3)
(2, 3, 17, 'Priya', 'Verma', 'SVS-302', '4th', 'A')  -- Also child of Vijay
RETURNING student_id, first_name;



/*
============ STUDENT_PARENTS ============
*/


INSERT INTO student_parents (student_id, parent_id, relationship, is_primary)
VALUES
-- Mark belongs to Jane (Parent 1)
(1, 1, 'MOTHER', TRUE),

-- Lucy belongs to Sarah (Parent 2)
(2, 2, 'MOTHER', TRUE),

-- Arjun & Priya belong to Vijay (Parent 3)
(3, 3, 'FATHER', TRUE),
(4, 3, 'FATHER', TRUE)
RETURNING student_parent_id, student_id, parent_id;


/*
============ ROUTES ============
*/


INSERT INTO routes (school_id, branch_id, route_code, route_name, description)
VALUES
-- Koti Branch (Branch 1)
(1, 1, 'GV-KOTI-01', 'LB Nagar', 'Serves Malakpet and Saidabad residential zones'),
(1, 1, 'GV-KOTI-02', 'Mehdipatnam', 'Fast-track route via Nampally to Mehdipatnam'),
(1, 1, 'GV-KOTI-03', 'Secunderaba', 'Covers Kachiguda and Amberpet areas'),

-- North Campus (Branch 2)
(1, 2, 'GV-NOR-01', 'Alwal', 'Primary pickup for Alwal and Lothkunta'),
(1, 2, 'GV-NOR-02', 'Kompally', 'Extended route reaching Kompally gated communities')
RETURNING route_id, route_code, route_name;


INSERT INTO routes (school_id, branch_id, route_code, route_name, description)
VALUES
-- Dilsuknagar Branch (Branch 3)
(2, 3, 'SR-DSN-01', 'LB Nagar', 'Covers LB Nagar, Kothapet, and Chaitanyapuri'),
(2, 3, 'SR-DSN-02', 'Mehdipatnam', 'Long-distance route for East Hyderabad outskirts'),

-- Kukatpally Branch (Branch 4)
(2, 4, 'SR-KPT-01', 'Bachupally', 'Serves Nizampet, Hydernagar, and JNTU areas'),
(2, 4, 'SR-KPT-02', 'Ameerpet', 'Covers Moosapet and Bharat Nagar metro zones'),
(2, 4, 'SR-KPT-03', 'Miyapur', 'Covers Miyapur metro zones'),


-- Chandanagar Branch (Branch 5)
(2, 5, 'SR-CHN-01', 'BHEL Township', 'Dedicated route for BHEL and Lingampally areas'),
(2, 5, 'SR-CHN-02', 'Kukatpally', 'Dedicated route for Kukatpally areas')
RETURNING route_id, route_code, route_name;


INSERT INTO stops (school_id, branch_id, stop_name, latitude, longitude)
VALUES
-- Branch 1: Koti
(1, 1, 'Malakpet Metro Station', 17.3769, 78.4939),
(1, 1, 'Dilsuknagar', 17.3685, 78.5247),
(1, 1, 'Chaitanyapuri Metro', 17.3683, 78.5358),
(1, 1, 'Kothapet Fruit Market', 17.3731, 78.5476),
(1, 1, 'LB Nagar X Roads', 17.3477, 78.5576),
(1, 1, 'Abids GPO', 17.3912, 78.4735),
(1, 1, 'Lakdikapool', 17.4018, 78.4658),
(1, 1, 'Masabtank X Roads', 17.3995, 78.4529),
(1, 1, 'Mehdipatnam Rythu Bazar', 17.3958, 78.4312),
(1, 1, 'Kachiguda Station Road', 17.3850, 78.4912),
(1, 1, 'Chikkadpally', 17.4026, 78.4939),
(1, 1, 'RTC X Roads', 17.4063, 78.4947),
(1, 1, 'Gandhi Hospital', 17.4227, 78.5028),
(1, 1, 'Secunderabad station', 17.4344, 78.5017),

-- Branch 2: North Campus
(1, 2, 'Alwal Ganesh Temple', 17.5011, 78.5034),
(1, 2, 'Lothkunta Junction', 17.4850, 78.4980),
(1, 2, 'Vikrampuri', 17.4497, 78.4920),
(1, 2, 'West Maredpally', 17.4485, 78.4985),
(1, 2, 'Kompally Big Bazaar', 17.5350, 78.4850),
(1, 2, 'Suchitra Circle', 17.5150, 78.4750)
RETURNING stop_id, stop_name;

INSERT INTO stops (school_id, branch_id, stop_name, latitude, longitude)
VALUES
-- Branch 3: Dilsuknagar
(2, 3, 'LB Nagar X Roads', 17.3477, 78.5576),
(2, 3, 'Kothapet Fruit Market', 17.3731, 78.5476),
(2, 3, 'Chaitanyapuri Metro', 17.3683, 78.5358),
(2, 3, 'Saroornagar Lake', 17.3500, 78.5300),

-- Branch 4: Kukatpally
(2, 4, 'JNTU Main Gate', 17.4933, 78.3915),
(2, 4, 'Nizampet Village Road', 17.5228, 78.3800),
(2, 4, 'Bachupally X Roads', 17.5389, 78.3586),
(2, 4, 'Moosapet Metro Station', 17.4764, 78.4172),
(2, 4, 'ESI Hospital', 17.4566, 78.4357),
(2, 4, 'Erragadda X Roads', 17.4616, 78.4282),
(2, 4, 'SR Nagar', 17.4439, 78.4452),
(2, 4, 'Ameerpet Metro Station', 17.4348, 78.4480),
(2, 4, 'Miyapur Allwyn Colony', 17.4967, 78.3500),
(2, 4, 'Miyapur X Roads', 17.4967, 78.3400),
(2, 4, 'Miyapur Metro', 17.4968, 78.3614),

-- Branch 5: Chandanagar
(2, 5, 'BHEL Main Gate', 17.5000, 78.3000),
(2, 5, 'Lingampally Station', 17.4835, 78.3181),
(2, 5, 'Chandanagar GHMC Park', 17.4910, 78.3250),
(2, 5, 'Miyapur Metro', 17.4968, 78.3614),
(2, 5, 'Miyapur X Roads', 17.4967, 78.3400),
(2, 5, 'KPHB Phase 9', 17.4845, 78.3889)
RETURNING stop_id, stop_name;



INSERT INTO route_stops (school_id, branch_id, route_id, stop_id, trip_type, stop_sequence)
VALUES
-- School 1, Branch 1 (Koti) - Route 1
(1, 1, 1, 5, 'PICKUP', 1), (1, 1, 1, 4, 'PICKUP', 2), (1, 1, 1, 3, 'PICKUP', 3), (1, 1, 1, 2, 'PICKUP', 4), (1, 1, 1, 1, 'PICKUP', 5),
(1, 1, 1, 1, 'DROPOFF', 1), (1, 1, 1, 2, 'DROPOFF', 2), (1, 1, 1, 3, 'DROPOFF', 3), (1, 1, 1, 4, 'DROPOFF', 4), (1, 1, 1, 5, 'DROPOFF', 5),
-- School 1, Branch 1 (Koti) - Route 2
(1, 1, 2, 9, 'PICKUP', 1), (1, 1, 2, 8, 'PICKUP', 2), (1, 1, 2, 7, 'PICKUP', 3), (1, 1, 2, 6, 'PICKUP', 4),
(1, 1, 2, 6, 'DROPOFF', 1), (1, 1, 2, 7, 'DROPOFF', 2), (1, 1, 2, 8, 'DROPOFF', 3), (1, 1, 2, 9, 'DROPOFF', 4),
-- School 1, Branch 1 (Koti) - Route 3
(1, 1, 3, 14, 'PICKUP', 1), (1, 1, 3, 13, 'PICKUP', 2), (1, 1, 3, 12, 'PICKUP', 3), (1, 1, 3, 11, 'PICKUP', 4), (1, 1, 3, 10, 'PICKUP', 5),
(1, 1, 3, 10, 'DROPOFF', 1), (1, 1, 3, 11, 'DROPOFF', 2), (1, 1, 3, 12, 'DROPOFF', 3), (1, 1, 3, 13, 'DROPOFF', 4), (1, 1, 3, 14, 'DROPOFF', 5),
-- School 1, Branch 2 (North Campus) - Routes 4 & 5
(1, 2, 4, 15, 'PICKUP', 1), (1, 2, 4, 16, 'PICKUP', 2), (1, 2, 4, 17, 'PICKUP', 3),
(1, 2, 4, 17, 'DROPOFF', 1), (1, 2, 4, 16, 'DROPOFF', 2), (1, 2, 4, 15, 'DROPOFF', 3),
(1, 2, 5, 19, 'PICKUP', 1), (1, 2, 5, 20, 'PICKUP', 2), (1, 2, 5, 18, 'PICKUP', 3),
(1, 2, 5, 18, 'DROPOFF', 1), (1, 2, 5, 20, 'DROPOFF', 2), (1, 2, 5, 19, 'DROPOFF', 3),
-- School 2, Branch 3 (Dilsuknagar) - Route 6
(2, 3, 6, 21, 'PICKUP', 1), (2, 3, 6, 22, 'PICKUP', 2), (2, 3, 6, 23, 'PICKUP', 3), (2, 3, 6, 24, 'PICKUP', 4),
(2, 3, 6, 24, 'DROPOFF', 1), (2, 3, 6, 23, 'DROPOFF', 2), (2, 3, 6, 22, 'DROPOFF', 3), (2, 3, 6, 21, 'DROPOFF', 4),
-- School 2, Branch 4 (Kukatpally) - Routes 8, 9, 10
(2, 4, 8, 27, 'PICKUP', 1), (2, 4, 8, 26, 'PICKUP', 2), (2, 4, 8, 25, 'PICKUP', 3),
(2, 4, 8, 25, 'DROPOFF', 1), (2, 4, 8, 26, 'DROPOFF', 2), (2, 4, 8, 27, 'DROPOFF', 3),
(2, 4, 9, 32, 'PICKUP', 1), (2, 4, 9, 31, 'PICKUP', 2), (2, 4, 9, 29, 'PICKUP', 3), (2, 4, 9, 30, 'PICKUP', 4), (2, 4, 9, 28, 'PICKUP', 5),
(2, 4, 9, 28, 'DROPOFF', 1), (2, 4, 9, 30, 'DROPOFF', 2), (2, 4, 9, 29, 'DROPOFF', 3), (2, 4, 9, 31, 'DROPOFF', 4), (2, 4, 9, 32, 'DROPOFF', 5),
(2, 4, 10, 33, 'PICKUP', 1), (2, 4, 10, 34, 'PICKUP', 2), (2, 4, 10, 35, 'PICKUP', 3), (2, 4, 10, 25, 'PICKUP', 4),
(2, 4, 10, 25, 'DROPOFF', 1), (2, 4, 10, 35, 'DROPOFF', 2), (2, 4, 10, 34, 'DROPOFF', 3), (2, 4, 10, 33, 'DROPOFF', 4),
-- School 2, Branch 5 (Chandanagar) - Routes 11 & 12
(2, 5, 11, 36, 'PICKUP', 1), (2, 5, 11, 37, 'PICKUP', 2), (2, 5, 11, 38, 'PICKUP', 3),
(2, 5, 11, 38, 'DROPOFF', 1), (2, 5, 11, 37, 'DROPOFF', 2), (2, 5, 11, 36, 'DROPOFF', 3),
(2, 5, 12, 41, 'PICKUP', 1), (2, 5, 12, 39, 'PICKUP', 2), (2, 5, 12, 40, 'PICKUP', 3),
(2, 5, 12, 40, 'DROPOFF', 1), (2, 5, 12, 39, 'DROPOFF', 2), (2, 5, 12, 41, 'DROPOFF', 3);




BEGIN;

-- 1. Create Users (Using your pgcrypto logic)
INSERT INTO users (user_name, email, phone, password_hash)
VALUES 
('aarav.s1', 'aarav.s1@example.com', '9876543210',  crypt('aarav', gen_salt('bf', 10))),
('ishani.g1', 'ishani.g1@example.com', '9876543211',  crypt('ishani', gen_salt('bf', 10))),
('sai.k2', 'sai.k2@example.com', '9876543212',  crypt('sai', gen_salt('bf', 10))),
('ananya.r2', 'ananya.r2@example.com', '9876543213',  crypt('ananya', gen_salt('bf', 10))),
('vihaan.v3', 'vihaan.v3@example.com', '9876543214',  crypt('vihaan', gen_salt('bf', 10))),
('myra.s3', 'myra.s3@example.com', '9876543215',  crypt('myra', gen_salt('bf', 10))),
('arjun.r4', 'arjun.r4@example.com', '9876543216',  crypt('arjun', gen_salt('bf', 10))),
('kavya.n4', 'kavya.n4@example.com', '9876543217',  crypt('kavya', gen_salt('bf', 10))),
('reyansh.j5', 'reyansh.j5@example.com', '9876543218',  crypt('reyansh123', gen_salt('bf', 10))),
('diya.m5', 'diya.m5@example.com', '9876543219', crypt('diya123', gen_salt('bf', 10)))
RETURNING user_id, user_name;

-- 2. Link Users to Roles (Fixed Branch/School Logic)
INSERT INTO user_roles (user_id, role_id, school_id, branch_id, role_name)
SELECT u.user_id, r.role_id, 
       -- Assign School ID
       CASE 
            WHEN u.user_name LIKE '%.s1' OR u.user_name LIKE '%.g1' THEN 1 -- Koti (B1)
            WHEN u.user_name LIKE '%.k2' OR u.user_name LIKE '%.r2' THEN 1 -- North (B2)
            ELSE 2 -- School 2 (Branches 3, 4, 5)
       END,
       -- Assign Branch ID
       CASE 
            WHEN u.user_name LIKE '%.s1' OR u.user_name LIKE '%.g1' THEN 1 
            WHEN u.user_name LIKE '%.k2' OR u.user_name LIKE '%.r2' THEN 2 
            WHEN u.user_name LIKE '%.v3' OR u.user_name LIKE '%.s3' THEN 3 
            WHEN u.user_name LIKE '%.r4' OR u.user_name LIKE '%.n4' THEN 4 
            ELSE 5 
       END,
       'STUDENT'
FROM users u, roles r 
WHERE r.role_name = 'STUDENT' 
AND u.user_name IN ('aarav.s1', 'ishani.g1', 'sai.k2', 'ananya.r2', 'vihaan.v3', 'myra.s3', 'arjun.r4', 'kavya.n4', 'reyansh.j5', 'diya.m5');

-- 3. Create Student Profiles
INSERT INTO students (school_id, branch_id, user_id, first_name, last_name, admission_number, grade, section)
VALUES
(1, 1, (SELECT user_id FROM users WHERE user_name='aarav.s1'), 'Aarav', 'Sharma', 'GV1005', 'Grade 5', 'A'),
(1, 1, (SELECT user_id FROM users WHERE user_name='ishani.g1'), 'Ishani', 'Gupta', 'GV1006', 'Grade 4', 'B'),
(1, 2, (SELECT user_id FROM users WHERE user_name='sai.k2'), 'Sai', 'Kiran', 'GVN2005', 'Grade 8', 'C'),
(1, 2, (SELECT user_id FROM users WHERE user_name='ananya.r2'), 'Ananya', 'Reddy', 'GVN2006', 'Grade 7', 'A'),
(2, 3, (SELECT user_id FROM users WHERE user_name='vihaan.v3'), 'Vihaan', 'Verma', 'SRD3005', 'Grade 3', 'B'),
(2, 3, (SELECT user_id FROM users WHERE user_name='myra.s3'), 'Myra', 'Singh', 'SRD3006', 'Grade 2', 'A'),
(2, 4, (SELECT user_id FROM users WHERE user_name='arjun.r4'), 'Arjun', 'Rao', 'SRK4005', 'Grade 10', 'D'),
(2, 4, (SELECT user_id FROM users WHERE user_name='kavya.n4'), 'Kavya', 'Nair', 'SRK4006', 'Grade 9', 'B'),
(2, 5, (SELECT user_id FROM users WHERE user_name='reyansh.j5'), 'Reyansh', 'Joshi', 'SRC5005', 'Grade 6', 'C'),
(2, 5, (SELECT user_id FROM users WHERE user_name='diya.m5'), 'Diya', 'Malhotra', 'SRC5006', 'Grade 5', 'A');

-- 4. Route Assignments
INSERT INTO student_route_assignments (school_id, branch_id, student_id, route_id, stop_id, assignment_type)
VALUES
(1, 1, (SELECT student_id FROM students WHERE admission_number='GV1005'), 1, 5, 'PICKUP'),
(1, 1, (SELECT student_id FROM students WHERE admission_number='GV1005'), 1, 5, 'DROPOFF'),
(1, 2, (SELECT student_id FROM students WHERE admission_number='GVN2005'), 4, 15, 'PICKUP'),
(1, 2, (SELECT student_id FROM students WHERE admission_number='GVN2005'), 4, 15, 'DROPOFF'),
(2, 3, (SELECT student_id FROM students WHERE admission_number='SRD3005'), 6, 21, 'PICKUP'),
(2, 3, (SELECT student_id FROM students WHERE admission_number='SRD3005'), 6, 21, 'DROPOFF'),
(2, 4, (SELECT student_id FROM students WHERE admission_number='SRK4005'), 8, 27, 'PICKUP'),
(2, 4, (SELECT student_id FROM students WHERE admission_number='SRK4005'), 8, 27, 'DROPOFF'),
(2, 5, (SELECT student_id FROM students WHERE admission_number='SRC5005'), 11, 36, 'PICKUP'),
(2, 5, (SELECT student_id FROM students WHERE admission_number='SRC5005'), 11, 36, 'DROPOFF');

COMMIT;


BEGIN;

-- 1. Create User accounts (New phone range: 933...)
INSERT INTO users (user_name, email, phone, password_hash)
VALUES 
('p3.sharma', 'parent3.sharma@test.com', '9330000001', crypt('parent123', gen_salt('bf', 10))),
('p3.gupta', 'parent3.gupta@test.com', '9330000002', crypt('parent123', gen_salt('bf', 10))),
('p3.kiran', 'parent3.kiran@test.com', '9330000003', crypt('parent123', gen_salt('bf', 10))),
('p3.reddy', 'parent3.reddy@test.com', '9330000004', crypt('parent123', gen_salt('bf', 10))),
('p3.verma', 'parent3.verma@test.com', '9330000005', crypt('parent123', gen_salt('bf', 10))),
('p3.singh', 'parent3.singh@test.com', '9330000006', crypt('parent123', gen_salt('bf', 10))),
('p3.rao', 'parent3.rao@test.com', '9330000007', crypt('parent123', gen_salt('bf', 10))),
('p3.nair', 'parent3.nair@test.com', '9330000008', crypt('parent123', gen_salt('bf', 10))),
('p3.joshi', 'parent3.joshi@test.com', '9330000009', crypt('parent123', gen_salt('bf', 10))),
('p3.malhotra', 'parent3.malhotra@test.com', '9330000010', crypt('parent123', gen_salt('bf', 10)))
ON CONFLICT (user_name) DO NOTHING;

-- 2. Add Parent Profiles
INSERT INTO parents (user_id, school_id, first_name, last_name, phone, email, address)
SELECT user_id, 
       CASE WHEN user_name IN ('p3.sharma', 'p3.gupta', 'p3.kiran', 'p3.reddy') THEN 1 ELSE 2 END,
       split_part(user_name, '.', 2), 
       'Parent', 
       phone, email, 'Address for ' || user_name
FROM users 
WHERE user_name LIKE 'p3.%'
ON CONFLICT DO NOTHING;

-- 3. Link Parents to Students
INSERT INTO student_parents (student_id, parent_id, relationship, is_primary)
SELECT s.student_id, p.parent_id, 'FATHER', TRUE
FROM students s, parents p
WHERE (s.admission_number = 'GV1005' AND p.email = 'parent3.sharma@test.com')
   OR (s.admission_number = 'GV1006' AND p.email = 'parent3.gupta@test.com')
   OR (s.admission_number = 'GVN2005' AND p.email = 'parent3.kiran@test.com')
   OR (s.admission_number = 'GVN2006' AND p.email = 'parent3.reddy@test.com')
   OR (s.admission_number = 'SRD3005' AND p.email = 'parent3.verma@test.com')
ON CONFLICT DO NOTHING;

-- 4. Assign PARENT Role (FIXED: Added ::role_name_enum cast)
INSERT INTO user_roles (user_id, role_id, school_id, branch_id, role_name)
SELECT DISTINCT 
    p.user_id, 
    r.role_id, 
    p.school_id, 
    s.branch_id, 
    'PARENT'::role_name_enum  -- Casting text to the Enum type
FROM parents p
JOIN roles r ON r.role_name::text = 'PARENT' -- Casting both sides if needed for comparison
JOIN student_parents sp ON p.parent_id = sp.parent_id
JOIN students s ON sp.student_id = s.student_id
WHERE p.email LIKE 'parent3.%'
ON CONFLICT DO NOTHING;

COMMIT;

BEGIN;

-- 1. GPS DEVICES (Required for tracking)
-- Mapping one device per branch for now
INSERT INTO gps_devices (device_id, school_id, branch_id, device_imei) VALUES 
(1, 1, 1, 'IMEI-GV-KOTI-01'),
(2, 1, 2, 'IMEI-GV-ALWAL-01'),
(3, 2, 3, 'IMEI-SR-DILS-01'),
(4, 2, 4, 'IMEI-SR-KUKT-01'),
(5, 2, 5, 'IMEI-SR-CHAN-01');

-- 2. BUSES (Mapping to specific branches and capacities)
INSERT INTO buses (bus_id, school_id, branch_id, bus_number, capacity) VALUES 
-- Green Valley (School 1)
(1, 1, 1, 'TS-09-UB-1001', 40), -- Koti
(2, 1, 1, 'TS-09-UB-1002', 25), -- Koti (Mini Bus)
(3, 1, 2, 'TS-10-UA-2001', 50), -- Alwal
-- Sunrise Public (School 2)
(4, 2, 3, 'TS-11-UD-3001', 40), -- Dilsuknagar
(5, 2, 4, 'TS-12-UK-4001', 45), -- Kukatpally
(6, 2, 5, 'TS-13-UC-5001', 30); -- Chandanagar

-- 3. Sync sequences to prevent future Gaps/Collisions
SELECT setval('gps_devices_device_id_seq', (SELECT MAX(device_id) FROM gps_devices));
SELECT setval('buses_bus_id_seq', (SELECT MAX(bus_id) FROM buses));

COMMIT;

BEGIN;

-- 1. Additional GPS DEVICES
INSERT INTO gps_devices (device_id, school_id, branch_id, device_imei) VALUES 
(6, 1, 1, 'IMEI-GV-KOTI-02'),
(7, 1, 2, 'IMEI-GV-ALWAL-02'),
(8, 2, 3, 'IMEI-SR-DILS-02'),
(9, 2, 4, 'IMEI-SR-KUKT-02'),
(10, 2, 5, 'IMEI-SR-CHAN-02');

-- 2. Additional BUSES
INSERT INTO buses (bus_id, school_id, branch_id, bus_number, capacity) VALUES 
-- Green Valley (School 1)
(7, 1, 1, 'TS-09-UB-1003', 50), -- Koti (High Capacity)
(8, 1, 2, 'TS-10-UA-2002', 30), -- Alwal (Medium)
-- Sunrise Public (School 2)
(9, 2, 3, 'TS-11-UD-3002', 20),  -- Dilsuknagar (Mini Van)
(10, 2, 4, 'TS-12-UK-4002', 60), -- Kukatpally (Large Coach)
(11, 2, 5, 'TS-13-UC-5002', 40); -- Chandanagar (Standard)

-- 3. Sync sequences to the new maximums
SELECT setval('gps_devices_device_id_seq', (SELECT MAX(device_id) FROM gps_devices));
SELECT setval('buses_bus_id_seq', (SELECT MAX(bus_id) FROM buses));

COMMIT;


BEGIN;

-- 1. Create User Accounts for new Drivers
-- Starting from ID 38 (assuming 37 is the current max)
INSERT INTO users (user_id, user_name, email, phone, password_hash) VALUES 
(38, 'drvr.vikram', 'vikram.s@schoolbus.com', '9550000101', crypt('driver123', gen_salt('bf', 8))),
(39, 'drvr.prakash', 'prakash.r@schoolbus.com', '9550000102', crypt('driver123', gen_salt('bf', 8))),
(40, 'drvr.abdul', 'abdul.k@schoolbus.com', '9550000103', crypt('driver123', gen_salt('bf', 8))),
(41, 'drvr.manoj', 'manoj.sh@schoolbus.com', '9550000104', crypt('driver123', gen_salt('bf', 8))),
(42, 'drvr.somesh', 'somesh.v@schoolbus.com', '9550000105', crypt('driver123', gen_salt('bf', 8)));

-- 2. Create Driver Profiles
-- Mapping to Branch IDs 1 through 5
INSERT INTO drivers (driver_id, user_id, school_id, branch_id, first_name, last_name, phone, license_number) VALUES 
(5, 38, 1, 1, 'Vikram', 'Singh', '9550000101', 'LIC-GV-2026-005'), -- Koti
(6, 39, 1, 2, 'Prakash', 'Raj', '9550000102', 'LIC-GV-2026-006'), -- Alwal
(7, 40, 2, 3, 'Abdul', 'Khan', '9550000103', 'LIC-SR-2026-007'), -- Dilsuknagar
(8, 41, 2, 4, 'Manoj', 'Sharma', '9550000104', 'LIC-SR-2026-008'), -- Kukatpally
(9, 42, 2, 5, 'Somesh', 'Vaddy', '9550000105', 'LIC-SR-2026-009'); -- Chandanagar

-- 3. Assign DRIVER Role
INSERT INTO user_roles (user_id, role_id, school_id, branch_id, role_name)
SELECT 
    d.user_id, 
    (SELECT role_id FROM roles WHERE role_name = 'DRIVER'::role_name_enum), 
    d.school_id, 
    d.branch_id, 
    'DRIVER'::role_name_enum
FROM drivers d
WHERE d.driver_id >= 5;

-- 4. Sync sequences to the new maximums
SELECT setval('users_user_id_seq', (SELECT MAX(user_id) FROM users));
SELECT setval('drivers_driver_id_seq', (SELECT MAX(driver_id) FROM drivers));

COMMIT;


BEGIN;

-- Assuming trip_id starts at 1
INSERT INTO trips (trip_id, school_id, branch_id, route_id, bus_id, driver_id, trip_type, scheduled_start_time)
VALUES 
-- Green Valley - Koti (Branch 1)
(1, 1, 1, 1, 1, 1, 'PICKUP'::trip_type_enum, '07:00:00'),
(2, 1, 1, 1, 1, 1, 'DROPOFF'::trip_type_enum, '15:30:00'),

-- Green Valley - Alwal (Branch 2)
(3, 1, 2, 4, 3, 2, 'PICKUP'::trip_type_enum, '07:15:00'),

-- Sunrise - Dilsuknagar (Branch 3)
(4, 2, 3, 6, 4, 3, 'PICKUP'::trip_type_enum, '07:30:00');

-- Sync trip sequence
SELECT setval('trips_trip_id_seq', (SELECT MAX(trip_id) FROM trips));

COMMIT;