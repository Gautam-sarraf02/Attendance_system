import io
import pytest
import datetime
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.academic_year import AcademicYear
from app.models.semester import Semester
from app.models.subject import Subject
from app.models.timetable import TimetableEntry
from app.models.holiday import Holiday
from app.models.face_enrollment import FaceEnrollment
from app.auth.jwt_handler import get_password_hash

client = TestClient(app)


def get_token(username, password="Password@123", role=None):
    payload = {"username": username, "password": password}
    if role:
        payload["role"] = role
    res = client.post("/api/auth/login", json=payload)
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def setup_admin_hub_test_data():
    db = SessionLocal()
    try:
        # 1. Admin
        admin = db.query(User).filter(User.username == "admin_hub_admin").first()
        if not admin:
            admin = User(
                username="admin_hub_admin",
                password_hash=get_password_hash("Password@123"),
                full_name="Admin Hub Test Administrator",
                email="admin_hub@college.edu",
                role="admin",
                is_active=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        # 2. Student User (unauthorized for admin operations)
        student = db.query(User).filter(User.username == "admin_hub_student").first()
        if not student:
            student = User(
                username="admin_hub_student",
                password_hash=get_password_hash("Password@123"),
                full_name="Student Test User",
                email="stu_hub@college.edu",
                role="student",
                is_active=True
            )
            db.add(student)
            db.commit()
            db.refresh(student)

        # 3. Academic Year & Semester
        ay = db.query(AcademicYear).filter(AcademicYear.name == "AY-Hub-2026").first()
        if not ay:
            ay = AcademicYear(
                name="AY-Hub-2026",
                start_date=date(2026, 8, 1),
                end_date=date(2027, 7, 31),
                is_current=True
            )
            db.add(ay)
            db.commit()
            db.refresh(ay)

        sem = db.query(Semester).filter(Semester.name == "Sem-Hub-1").first()
        if not sem:
            sem = Semester(
                name="Sem-Hub-1",
                academic_year_id=ay.id,
                start_date=ay.start_date,
                end_date=ay.end_date,
                is_active=True
            )
            db.add(sem)
            db.commit()
            db.refresh(sem)

        # 4. Subject
        sub = db.query(Subject).filter(Subject.code == "CS-HUB-101").first()
        if not sub:
            sub = Subject(
                code="CS-HUB-101",
                name="Cloud Computing Hub",
                semester_id=sem.id,
                section="A",
                is_active=True
            )
            db.add(sub)
            db.commit()
            db.refresh(sub)

        return {
            "admin_id": admin.id,
            "admin_user": admin.username,
            "student_id": student.id,
            "student_user": student.username,
            "ay_id": ay.id,
            "sem_id": sem.id,
            "sub_id": sub.id
        }
    finally:
        db.close()


# ─── 1. Admin Can Register a Faculty Member ──────────────────────────────────

def test_01_admin_can_register_faculty(setup_admin_hub_test_data):
    admin_tok = get_token("admin_hub_admin", role="admin")
    headers = {"Authorization": f"Bearer {admin_tok}"}

    payload = {
        "faculty_id": "FAC-TEST99",
        "username": "prof_test99",
        "full_name": "Prof. Test NinetyNine",
        "email": "test99@smartattend.edu",
        "password": "Password@123",
        "role": "faculty",
        "is_active": True,
        "assigned_subject_ids": [setup_admin_hub_test_data["sub_id"]],
        "assigned_sections": ["A"]
    }

    # Clean up previous runs if any
    db = SessionLocal()
    prev = db.query(User).filter(User.username == "prof_test99").first()
    if prev:
        db.delete(prev)
        db.commit()
    db.close()

    res = client.post("/api/auth/faculty", json=payload, headers=headers)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["faculty_id"] == "FAC-TEST99"
    assert data["username"] == "prof_test99"
    assert data["full_name"] == "Prof. Test NinetyNine"
    assert data["role"] == "faculty"
    assert data["is_active"] is True


# ─── 2. Duplicate Faculty ID or Username is Rejected ─────────────────────────

def test_02_duplicate_faculty_id_or_username_rejected(setup_admin_hub_test_data):
    admin_tok = get_token("admin_hub_admin", role="admin")
    headers = {"Authorization": f"Bearer {admin_tok}"}

    # Duplicate faculty_id
    payload_dup_fid = {
        "faculty_id": "FAC-TEST99",
        "username": "different_username",
        "full_name": "Another Name",
        "password": "Password@123"
    }
    res_fid = client.post("/api/auth/faculty", json=payload_dup_fid, headers=headers)
    assert res_fid.status_code == 400
    assert "already registered" in res_fid.json()["detail"]

    # Duplicate username
    payload_dup_user = {
        "faculty_id": "FAC-UNIQUE01",
        "username": "prof_test99",
        "full_name": "Another Name",
        "password": "Password@123"
    }
    res_user = client.post("/api/auth/faculty", json=payload_dup_user, headers=headers)
    assert res_user.status_code == 400
    assert "already registered" in res_user.json()["detail"] or "already taken" in res_user.json()["detail"]


# ─── 3. Unauthorized Users Cannot Register Faculty or Enroll ──────────────────

def test_03_unauthorized_users_cannot_register_faculty_or_enroll(setup_admin_hub_test_data):
    student_tok = get_token("admin_hub_student", role="student")
    headers = {"Authorization": f"Bearer {student_tok}"}

    payload = {
        "faculty_id": "FAC-HACK01",
        "username": "hacker_prof",
        "full_name": "Malicious User",
        "password": "Password@123"
    }
    # Student attempting to create faculty
    res = client.post("/api/auth/faculty", json=payload, headers=headers)
    assert res.status_code == 403

    # Student attempting to register biometrics
    enroll_payload = {
        "academic_year_id": setup_admin_hub_test_data["ay_id"],
        "user_id": setup_admin_hub_test_data["admin_id"],
        "images": ["dummy_b64"]
    }
    res_enroll = client.post("/api/enrollments/register", json=enroll_payload, headers=headers)
    assert res_enroll.status_code == 403


# ─── 4. Faculty Registration and Admin Hub Endpoints Return 200 Not 404 ──────

def test_04_admin_hub_endpoints_return_valid_responses_not_404(setup_admin_hub_test_data):
    admin_tok = get_token("admin_hub_admin", role="admin")
    headers = {"Authorization": f"Bearer {admin_tok}"}

    endpoints = [
        "/api/auth/faculty",
        "/api/timetable/entries",
        "/api/timetable/academic-years",
        "/api/timetable/semesters",
        "/api/timetable/subjects",
        "/api/timetable/holidays",
        "/api/enrollments"
    ]

    for ep in endpoints:
        res = client.get(ep, headers=headers)
        assert res.status_code == 200, f"Endpoint {ep} returned {res.status_code} (expected 200, not 404!): {res.text}"
        data = res.json()
        assert isinstance(data, list), f"Expected list response for {ep}, got {type(data)}"


# ─── 5. Weekly Timetable Entries Load From the Database ──────────────────────

def test_05_weekly_timetable_entries_load_from_db(setup_admin_hub_test_data):
    admin_tok = get_token("admin_hub_admin", role="admin")
    headers = {"Authorization": f"Bearer {admin_tok}"}

    res = client.get("/api/timetable/entries", headers=headers)
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) > 0, "Expected non-zero timetable entries from database."

    # Verify presence of essential timetable fields
    first_slot = entries[0]
    assert "id" in first_slot
    assert "subject_name" in first_slot or "subject_id" in first_slot
    assert "section" in first_slot
    assert "day_of_week" in first_slot
    assert "start_time" in first_slot
    assert "end_time" in first_slot
    assert "is_active" in first_slot


# ─── 6. Adding, Editing, and Deactivating Timetable Entries ───────────────────

def test_06_adding_editing_and_deactivating_timetable_entries(setup_admin_hub_test_data):
    admin_tok = get_token("admin_hub_admin", role="admin")
    headers = {"Authorization": f"Bearer {admin_tok}"}
    data = setup_admin_hub_test_data

    # Add slot
    create_payload = {
        "subject_id": data["sub_id"],
        "teacher_id": data["admin_id"],
        "semester_id": data["sem_id"],
        "section": "HUB-Z",
        "day_of_week": 4, # Friday
        "period_number": 6,
        "start_time": "16:00",
        "end_time": "17:00",
        "is_active": True
    }
    res_add = client.post("/api/timetable/entries", json=create_payload, headers=headers)
    assert res_add.status_code == 201, res_add.text
    slot_id = res_add.json()["id"]

    # Edit slot
    update_payload = {
        "start_time": "16:15",
        "end_time": "17:15"
    }
    res_edit = client.put(f"/api/timetable/entries/{slot_id}", json=update_payload, headers=headers)
    assert res_edit.status_code == 200

    # Deactivate / Delete slot
    res_del = client.delete(f"/api/timetable/entries/{slot_id}", headers=headers)
    assert res_del.status_code == 200


# ─── 7. Academic Years, Subjects, Sections, and Holidays Load and Update ──────

def test_07_academic_years_subjects_sections_and_holidays_load_and_update(setup_admin_hub_test_data):
    admin_tok = get_token("admin_hub_admin", role="admin")
    headers = {"Authorization": f"Bearer {admin_tok}"}
    data = setup_admin_hub_test_data

    # 1. Academic Years
    res_ay = client.get("/api/timetable/academic-years", headers=headers)
    assert res_ay.status_code == 200
    assert len(res_ay.json()) >= 1

    # 2. Subjects
    res_sub = client.get(f"/api/timetable/subjects?semester_id={data['sem_id']}", headers=headers)
    assert res_sub.status_code == 200
    assert len(res_sub.json()) >= 1

    # 3. Create Holiday
    h_payload = {
        "academic_year_id": data["ay_id"],
        "name": "Institute Foundation Day",
        "date": "2026-11-15",
        "description": "Annual institutional celebration"
    }
    res_h = client.post("/api/timetable/holidays", json=h_payload, headers=headers)
    assert res_h.status_code == 201
    h_id = res_h.json()["id"]

    # List holidays
    res_hl = client.get(f"/api/timetable/holidays?academic_year_id={data['ay_id']}", headers=headers)
    assert res_hl.status_code == 200
    assert any(h["name"] == "Institute Foundation Day" for h in res_hl.json())

    # Delete Holiday
    res_hdel = client.delete(f"/api/timetable/holidays/{h_id}", headers=headers)
    assert res_hdel.status_code == 200
