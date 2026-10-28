import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.student import Student
from app.auth.jwt_handler import get_password_hash

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def ensure_role_demo_accounts():
    """Ensure admin, teacher, and student demo accounts exist and are linked properly."""
    db = SessionLocal()
    try:
        # 1. Admin
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                full_name="System Administrator",
                email="admin@college.edu",
                role="admin",
                is_active=True
            )
            db.add(admin)
        else:
            admin.password_hash = get_password_hash("admin123")
            admin.is_active = True

        # 2. Teacher (Faculty)
        teacher = db.query(User).filter(User.username == "teacher").first()
        if not teacher:
            teacher = User(
                username="teacher",
                password_hash=get_password_hash("teacher123"),
                full_name="Prof. John Doe",
                email="teacher@college.edu",
                role="teacher",
                is_active=True
            )
            db.add(teacher)
        else:
            teacher.password_hash = get_password_hash("teacher123")
            teacher.is_active = True

        # 3. Student Profile & User
        student_profile = db.query(Student).filter(Student.roll_number == "11242211").first()
        if not student_profile:
            student_profile = Student(
                roll_number="11242211",
                name="Gurpreet Maan",
                section="CSE-A",
                email="gurpreet@college.edu",
                is_active=True
            )
            db.add(student_profile)
            db.flush()

        student_user = db.query(User).filter(User.username == "student").first()
        if not student_user:
            student_user = User(
                username="student",
                password_hash=get_password_hash("student123"),
                full_name="Gurpreet Maan",
                email="student@college.edu",
                role="student",
                student_id=student_profile.id,
                is_active=True
            )
            db.add(student_user)
        else:
            student_user.password_hash = get_password_hash("student123")
            student_user.student_id = student_profile.id
            student_user.is_active = True

        db.commit()
    finally:
        db.close()


def test_admin_login_with_role_admin():
    """Admin authenticates successfully when role is 'admin'."""
    res = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123",
        "role": "admin"
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "admin"


def test_faculty_login_with_role_faculty():
    """Faculty authenticates successfully when role is 'faculty'."""
    res = client.post("/api/auth/login", json={
        "username": "teacher",
        "password": "teacher123",
        "role": "faculty"
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] in ("teacher", "faculty")


def test_student_login_with_role_student():
    """Student authenticates successfully when role is 'student'."""
    res = client.post("/api/auth/login", json={
        "username": "student",
        "password": "student123",
        "role": "student"
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "student"


def test_student_login_via_roll_number():
    """Student authenticates successfully using roll number as username."""
    res = client.post("/api/auth/login", json={
        "username": "11242211",
        "password": "student123",
        "role": "student"
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data
    assert data["user"]["username"] == "student"


def test_role_mismatch_admin_attempting_student_role():
    """Admin credentials rejected with 403 when selected role is student."""
    res = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123",
        "role": "student"
    })
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_role_mismatch_teacher_attempting_admin_role():
    """Teacher credentials rejected with 403 when selected role is admin."""
    res = client.post("/api/auth/login", json={
        "username": "teacher",
        "password": "teacher123",
        "role": "admin"
    })
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_role_mismatch_student_attempting_faculty_role():
    """Student credentials rejected with 403 when selected role is faculty."""
    res = client.post("/api/auth/login", json={
        "username": "student",
        "password": "student123",
        "role": "faculty"
    })
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_invalid_credentials_returns_401():
    """Incorrect password returns HTTP 401 Unauthorized."""
    res = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "WrongPassword999",
        "role": "admin"
    })
    assert res.status_code == 401
