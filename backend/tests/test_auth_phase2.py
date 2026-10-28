import pytest
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.student import Student
from app.models.subject import Subject
from app.models.academic_year import AcademicYear
from app.models.semester import Semester
from app.models.timetable import TimetableEntry
from app.auth.jwt_handler import get_password_hash

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_test_users():
    """
    Sets up a test Admin, Teacher, and two Students with linked user accounts.
    """
    db = SessionLocal()
    try:
        # 1. Ensure Admin exists
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                full_name="Admin User",
                email="admin@test.edu",
                role="admin",
                is_active=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        # 2. Inactive Admin/User for testing
        inactive_user = db.query(User).filter(User.username == "inactive_user").first()
        if not inactive_user:
            inactive_user = User(
                username="inactive_user",
                password_hash=get_password_hash("password123"),
                full_name="Inactive User",
                email="inactive@test.edu",
                role="teacher",
                is_active=False
            )
            db.add(inactive_user)

        # 3. Create Student 1 and Student 2 profile records
        s1 = db.query(Student).filter(Student.roll_number == "P2_STU_001").first()
        if not s1:
            s1 = Student(
                roll_number="P2_STU_001",
                name="Alice Student",
                section="CSE-A",
                email="alice@test.edu",
                is_active=True
            )
            db.add(s1)
            db.commit()
            db.refresh(s1)

        s2 = db.query(Student).filter(Student.roll_number == "P2_STU_002").first()
        if not s2:
            s2 = Student(
                roll_number="P2_STU_002",
                name="Bob Student",
                section="CSE-B",
                email="bob@test.edu",
                is_active=True
            )
            db.add(s2)
            db.commit()
            db.refresh(s2)

        # 4. Create Teacher user
        teacher = db.query(User).filter(User.username == "test_teacher").first()
        if not teacher:
            teacher = User(
                username="test_teacher",
                password_hash=get_password_hash("teacher123"),
                full_name="Prof. Test Teacher",
                email="teacher@test.edu",
                role="teacher",
                is_active=True
            )
            db.add(teacher)

        # 5. Create Student 1 user account
        stu1_user = db.query(User).filter(User.username == "student_alice").first()
        if not stu1_user:
            stu1_user = User(
                username="student_alice",
                password_hash=get_password_hash("alice123"),
                full_name="Alice Student",
                email="alice.user@test.edu",
                role="student",
                student_id=s1.id,
                is_active=True
            )
            db.add(stu1_user)
        else:
            stu1_user.student_id = s1.id

        # 6. Create Student 2 user account
        stu2_user = db.query(User).filter(User.username == "student_bob").first()
        if not stu2_user:
            stu2_user = User(
                username="student_bob",
                password_hash=get_password_hash("bob12345"),
                full_name="Bob Student",
                email="bob.user@test.edu",
                role="student",
                student_id=s2.id,
                is_active=True
            )
            db.add(stu2_user)
        else:
            stu2_user.student_id = s2.id

        db.commit()

        yield {
            "admin_user": "admin",
            "admin_pass": "admin123",
            "teacher_user": "test_teacher",
            "teacher_pass": "teacher123",
            "student1_user": "student_alice",
            "student1_roll": "P2_STU_001",
            "student1_pass": "alice123",
            "student1_id": s1.id,
            "student2_user": "student_bob",
            "student2_roll": "P2_STU_002",
            "student2_pass": "bob12345",
            "student2_id": s2.id,
        }
    finally:
        db.close()


def get_token(username, password):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


def test_login_all_roles(setup_test_users):
    info = setup_test_users

    # 1. Admin login
    res_admin = client.post("/api/auth/login", json={"username": info["admin_user"], "password": info["admin_pass"]})
    assert res_admin.status_code == 200
    assert res_admin.json()["user"]["role"] == "admin"

    # 2. Teacher login
    res_teacher = client.post("/api/auth/login", json={"username": info["teacher_user"], "password": info["teacher_pass"]})
    assert res_teacher.status_code == 200
    assert res_teacher.json()["user"]["role"] == "teacher"

    # 3. Student login via username
    res_stu = client.post("/api/auth/login", json={"username": info["student1_user"], "password": info["student1_pass"]})
    assert res_stu.status_code == 200
    assert res_stu.json()["user"]["role"] == "student"
    assert res_stu.json()["user"]["student_id"] == info["student1_id"]

    # 4. Student login via roll number
    res_stu_roll = client.post("/api/auth/login", json={"username": info["student1_roll"], "password": info["student1_pass"]})
    assert res_stu_roll.status_code == 200
    assert res_stu_roll.json()["user"]["role"] == "student"


def test_login_invalid_credentials():
    # Wrong password
    res = client.post("/api/auth/login", json={"username": "admin", "password": "WrongPassword!"})
    assert res.status_code == 401

    # Non-existent user
    res2 = client.post("/api/auth/login", json={"username": "non_existent_user_xyz", "password": "somepassword"})
    assert res2.status_code == 401

    # Inactive user
    res3 = client.post("/api/auth/login", json={"username": "inactive_user", "password": "password123"})
    assert res3.status_code == 400
    assert "deactivated" in res3.json()["detail"].lower()


def test_student_isolation_and_unauthorized_access(setup_test_users):
    info = setup_test_users
    alice_token = get_token(info["student1_user"], info["student1_pass"])
    alice_header = {"Authorization": f"Bearer {alice_token}"}

    # 1. Student attempting to list all students -> 403 Forbidden
    res_dir = client.get("/api/students", headers=alice_header)
    assert res_dir.status_code == 403

    # 2. Student attempting to view other student's record -> 403 Forbidden
    res_other = client.get(f"/api/students/{info['student2_id']}", headers=alice_header)
    assert res_other.status_code == 403

    # 3. Student viewing their OWN student record -> 200 OK
    res_own = client.get(f"/api/students/{info['student1_id']}", headers=alice_header)
    assert res_own.status_code == 200
    assert res_own.json()["roll_number"] == info["student1_roll"]

    # 4. Student attempting to query other student's attendance history -> 403 Forbidden
    res_att_other = client.get(f"/api/attendance/history?student_id={info['student2_id']}", headers=alice_header)
    assert res_att_other.status_code == 403

    # 5. Student querying own attendance history -> 200 OK
    res_att_own = client.get("/api/attendance/history", headers=alice_header)
    assert res_att_own.status_code == 200

    # 6. Student attempting to create student -> 403 Forbidden
    res_create = client.post("/api/students", json={
        "roll_number": "HACK_001",
        "name": "Hack Student",
        "section": "CSE-A"
    }, headers=alice_header)
    assert res_create.status_code == 403

    # 7. Student attempting to access faculty dashboard -> 403 Forbidden
    res_dash = client.get("/api/dashboard/stats", headers=alice_header)
    assert res_dash.status_code == 403

    # 8. Student attempting to export reports -> 403 Forbidden
    res_exp = client.get("/api/reports/export/csv", headers=alice_header)
    assert res_exp.status_code == 403

    # 9. Student attempting to start session -> 403 Forbidden
    res_sess = client.post("/api/sessions", json={"subject": "Math", "section": "CSE-A"}, headers=alice_header)
    assert res_sess.status_code == 403


def test_teacher_role_permissions(setup_test_users):
    info = setup_test_users
    teacher_token = get_token(info["teacher_user"], info["teacher_pass"])
    teacher_header = {"Authorization": f"Bearer {teacher_token}"}

    # 1. Teacher CAN view student directory and students
    res_students = client.get("/api/students", headers=teacher_header)
    assert res_students.status_code == 200

    # 2. Teacher CAN view faculty dashboard
    res_dash = client.get("/api/dashboard/stats", headers=teacher_header)
    assert res_dash.status_code == 200

    # 3. Teacher CANNOT create users (Admin only) -> 403 Forbidden
    res_user_create = client.post("/api/auth/users", json={
        "username": "rogue_admin",
        "password": "Password123",
        "role": "admin"
    }, headers=teacher_header)
    assert res_user_create.status_code == 403

    # 4. Teacher CANNOT create timetable data (Admin only) -> 403 Forbidden
    res_tt = client.post("/api/timetable/academic-years", json={
        "name": "2029-2030",
        "start_date": "2029-01-01",
        "end_date": "2029-12-31"
    }, headers=teacher_header)
    assert res_tt.status_code == 403

    # 5. Teacher CANNOT delete attendance records -> 403 Forbidden
    res_del_att = client.delete("/api/attendance/99999", headers=teacher_header)
    assert res_del_att.status_code == 403

    # 6. Teacher CANNOT train facial recognition model -> 403 Forbidden
    res_train = client.post("/api/model/train", headers=teacher_header)
    assert res_train.status_code == 403


def test_admin_exclusive_operations(setup_test_users):
    info = setup_test_users
    admin_token = get_token(info["admin_user"], info["admin_pass"])
    admin_header = {"Authorization": f"Bearer {admin_token}"}

    # 1. Admin creates a new user
    new_username = f"faculty_{np.random.randint(1000, 9999)}"
    res_create_user = client.post("/api/auth/users", json={
        "username": new_username,
        "password": "SecurePassword123",
        "full_name": "New Faculty Member",
        "email": f"{new_username}@college.edu",
        "role": "teacher"
    }, headers=admin_header)
    assert res_create_user.status_code == 201
    user_id = res_create_user.json()["id"]

    # 2. Admin lists users
    res_users = client.get("/api/auth/users", headers=admin_header)
    assert res_users.status_code == 200
    assert res_users.json()["total"] > 0

    # 3. Admin updates user
    res_update = client.put(f"/api/auth/users/{user_id}", json={
        "full_name": "Updated Faculty Name"
    }, headers=admin_header)
    assert res_update.status_code == 200
    assert res_update.json()["full_name"] == "Updated Faculty Name"

    # 4. Admin deletes user
    res_del = client.delete(f"/api/auth/users/{user_id}", headers=admin_header)
    assert res_del.status_code == 200

    # 5. Admin creates an academic year
    rand_year = np.random.randint(3000, 4000)
    res_ay = client.post("/api/timetable/academic-years", json={
        "name": f"Year-{rand_year}",
        "start_date": f"{rand_year}-08-01",
        "end_date": f"{rand_year+1}-06-30",
        "is_current": False
    }, headers=admin_header)
    assert res_ay.status_code == 201
    ay_id = res_ay.json()["id"]

    # Clean up academic year
    del_ay = client.delete(f"/api/timetable/academic-years/{ay_id}", headers=admin_header)
    assert del_ay.status_code == 200


def test_initial_admin_setup_lockout():
    # Since an admin already exists in DB, /setup-admin must reject
    res = client.post("/api/auth/setup-admin", json={
        "username": "second_admin",
        "password": "Password12345",
        "email": "second@test.edu"
    })
    assert res.status_code == 400
    assert "already set up" in res.json()["detail"].lower()


def test_unauthenticated_requests_blocked():
    # Calling protected endpoints without Authorization header must fail
    res1 = client.get("/api/students")
    assert res1.status_code in (401, 403)

    res2 = client.get("/api/attendance/history")
    assert res2.status_code in (401, 403)

    res3 = client.post("/api/sessions", json={"subject": "X", "section": "A"})
    assert res3.status_code in (401, 403)

    res4 = client.get("/api/dashboard/stats")
    assert res4.status_code in (401, 403)


def test_password_change_flow(setup_test_users):
    info = setup_test_users
    token = get_token(info["teacher_user"], info["teacher_pass"])
    header = {"Authorization": f"Bearer {token}"}

    # 1. Invalid current password -> 400
    res_bad = client.post("/api/auth/change-password", json={
        "current_password": "WrongPassword123",
        "new_password": "BrandNewPassword123"
    }, headers=header)
    assert res_bad.status_code == 400

    # 2. Too short new password -> 400
    res_short = client.post("/api/auth/change-password", json={
        "current_password": info["teacher_pass"],
        "new_password": "short"
    }, headers=header)
    assert res_short.status_code == 400

    # 3. Successful change
    res_ok = client.post("/api/auth/change-password", json={
        "current_password": info["teacher_pass"],
        "new_password": "BrandNewPassword123"
    }, headers=header)
    assert res_ok.status_code == 200

    # 4. Verify login with new password
    res_new_login = client.post("/api/auth/login", json={
        "username": info["teacher_user"],
        "password": "BrandNewPassword123"
    })
    assert res_new_login.status_code == 200

    # 5. Restore original password for idempotency
    new_token = res_new_login.json()["access_token"]
    client.post("/api/auth/change-password", json={
        "current_password": "BrandNewPassword123",
        "new_password": info["teacher_pass"]
    }, headers={"Authorization": f"Bearer {new_token}"})

