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
from app.models.substitute_auth import SubstituteAuthorization
from app.auth.jwt_handler import get_password_hash
from sqlalchemy import or_

client = TestClient(app)


def get_token(username, password):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def setup_phase4_data():
    """
    Sets up academic structures for Phase 4 testing:
    Admin, Teacher 1, Teacher 2, Student, Academic Year, Semester, Subjects.
    """
    db = SessionLocal()
    try:
        # 1. Admin
        admin = db.query(User).filter(User.username == "p4_admin").first()
        if not admin:
            admin = User(
                username="p4_admin",
                password_hash=get_password_hash("admin123"),
                full_name="Phase 4 Administrator",
                email="admin.p4@test.edu",
                role="admin",
                is_active=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        # 2. Teachers
        t1 = db.query(User).filter(User.username == "p4_prof_rao").first()
        if not t1:
            t1 = User(
                username="p4_prof_rao",
                password_hash=get_password_hash("teacher123"),
                full_name="Prof. Rao",
                email="rao.p4@test.edu",
                role="teacher",
                is_active=True
            )
            db.add(t1)

        t2 = db.query(User).filter(User.username == "p4_prof_gupta").first()
        if not t2:
            t2 = User(
                username="p4_prof_gupta",
                password_hash=get_password_hash("teacher123"),
                full_name="Prof. Gupta",
                email="gupta.p4@test.edu",
                role="teacher",
                is_active=True
            )
            db.add(t2)

        # Inactive teacher for validation testing
        t_inactive = db.query(User).filter(User.username == "p4_prof_inactive").first()
        if not t_inactive:
            t_inactive = User(
                username="p4_prof_inactive",
                password_hash=get_password_hash("teacher123"),
                full_name="Prof. Inactive",
                email="inactive.p4@test.edu",
                role="teacher",
                is_active=False
            )
            db.add(t_inactive)

        # 3. Student
        student_user = db.query(User).filter(User.username == "p4_student").first()
        if not student_user:
            student_user = User(
                username="p4_student",
                password_hash=get_password_hash("student123"),
                full_name="P4 Student",
                email="student.p4@test.edu",
                role="student",
                is_active=True
            )
            db.add(student_user)

        # 4. Academic Year
        today = date.today()
        ay = db.query(AcademicYear).filter(AcademicYear.name == "2026-2027-P4").first()
        if not ay:
            ay = AcademicYear(
                name="2026-2027-P4",
                start_date=today - timedelta(days=60),
                end_date=today + timedelta(days=300),
                is_current=True
            )
            db.add(ay)
            db.commit()
            db.refresh(ay)

        # 5. Semester
        sem = db.query(Semester).filter(Semester.name == "Semester 5 P4").first()
        if not sem:
            sem = Semester(
                name="Semester 5 P4",
                academic_year_id=ay.id,
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=90),
                is_active=True
            )
            db.add(sem)
            db.commit()
            db.refresh(sem)

        # 6. Subjects
        sub1 = db.query(Subject).filter(Subject.code == "P4_CS501").first()
        if not sub1:
            sub1 = Subject(
                code="P4_CS501",
                name="Computer Vision and LBPH",
                semester_id=sem.id,
                section="CSE-A"
            )
            db.add(sub1)

        sub2 = db.query(Subject).filter(Subject.code == "P4_CS502").first()
        if not sub2:
            sub2 = Subject(
                code="P4_CS502",
                name="Distributed Machine Learning",
                semester_id=sem.id,
                section="CSE-A"
            )
            db.add(sub2)

        sub3 = db.query(Subject).filter(Subject.code == "P4_CS503").first()
        if not sub3:
            sub3 = Subject(
                code="P4_CS503",
                name="Neural Networks",
                semester_id=sem.id,
                section="CSE-B"
            )
            db.add(sub3)

        db.commit()
        db.refresh(t1)
        db.refresh(t2)
        db.refresh(sub1)
        db.refresh(sub2)
        db.refresh(sub3)

        # Clean existing test timetable entries and test holidays for clean baseline
        db.query(TimetableEntry).filter(TimetableEntry.semester_id == sem.id).delete()
        db.query(Holiday).filter(or_(Holiday.name.like("%Phase 4%"), Holiday.date == date(2026, 11, 4))).delete()
        db.commit()

        yield {
            "admin_user": "p4_admin",
            "admin_pass": "admin123",
            "t1_user": "p4_prof_rao",
            "t1_pass": "teacher123",
            "t1_id": t1.id,
            "t2_user": "p4_prof_gupta",
            "t2_pass": "teacher123",
            "t2_id": t2.id,
            "inactive_user": "p4_prof_inactive",
            "student_user": "p4_student",
            "student_pass": "student123",
            "ay_id": ay.id,
            "sem_id": sem.id,
            "sem_name": sem.name,
            "sub1_code": sub1.code,
            "sub1_id": sub1.id,
            "sub2_code": sub2.code,
            "sub2_id": sub2.id,
            "sub3_code": sub3.code,
            "sub3_id": sub3.id,
        }
    finally:
        db.close()


def test_timetable_template_download():
    """Verify standard CSV template download."""
    res = client.get("/api/timetable/template/csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    text = res.text
    assert "day,period,start_time,end_time,semester,section,subject,teacher" in text


def test_timetable_import_preview_and_commit(setup_phase4_data):
    """
    Requirements 2, 3, 6:
    - Support day, period, start/end time, semester, section, subject, teacher.
    - Validate CSV upload with preview before saving.
    - Commit valid rows to DB.
    """
    info = setup_phase4_data
    admin_token = get_token(info["admin_user"], info["admin_pass"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    csv_data = (
        "day,period,start_time,end_time,semester,section,subject,teacher\n"
        f"Monday,1,09:00,10:00,{info['sem_name']},CSE-A,{info['sub1_code']},{info['t1_user']}\n"
        f"Monday,2,10:00,11:00,{info['sem_name']},CSE-A,{info['sub2_code']},{info['t2_user']}\n"
        f"Tuesday,1,09:00,10:00,{info['sem_name']},CSE-B,{info['sub3_code']},{info['t1_user']}\n"
    )

    # 1. Preview via file upload
    file_payload = ("timetable.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")
    res_preview = client.post("/api/timetable/import/preview", files={"file": file_payload}, headers=headers)
    assert res_preview.status_code == 200
    preview = res_preview.json()

    assert preview["total_rows"] == 3
    assert preview["valid_count"] == 3
    assert preview["conflict_count"] == 0
    assert preview["error_count"] == 0

    valid_rows = [r["resolved"] for r in preview["rows"] if r["status"] == "valid"]
    assert len(valid_rows) == 3

    # 2. Commit the previewed rows
    res_commit = client.post("/api/timetable/import/commit", json={"rows": valid_rows}, headers=headers)
    assert res_commit.status_code == 200
    assert res_commit.json()["imported_count"] == 3

    # 3. Verify records stored in DB
    db = SessionLocal()
    entries = db.query(TimetableEntry).filter(TimetableEntry.semester_id == info["sem_id"]).all()
    assert len(entries) >= 3
    db.close()


def test_timetable_import_invalid_rows_detection(setup_phase4_data):
    """
    Requirements 3, 5:
    - Validate rows and report errors for missing fields, bad time formats, unknown entities, inactive teachers.
    """
    info = setup_phase4_data
    admin_token = get_token(info["admin_user"], info["admin_pass"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    invalid_csv = (
        "day,period,start_time,end_time,semester,section,subject,teacher\n"
        # Row 1: Unknown semester
        f"Monday,1,09:00,10:00,NonExistentSemester,CSE-A,{info['sub1_code']},{info['t1_user']}\n"
        # Row 2: Inverted time (end before start)
        f"Monday,2,11:00,09:00,{info['sem_name']},CSE-A,{info['sub2_code']},{info['t2_user']}\n"
        # Row 3: Inactive teacher
        f"Wednesday,1,09:00,10:00,{info['sem_name']},CSE-A,{info['sub1_code']},{info['inactive_user']}\n"
        # Row 4: Unknown subject
        f"Wednesday,2,10:00,11:00,{info['sem_name']},CSE-A,INVALID_CODE,{info['t1_user']}\n"
        # Row 5: Missing fields
        f"Thursday,,,,{info['sem_name']},CSE-A,,\n"
    )

    file_payload = ("invalid.csv", io.BytesIO(invalid_csv.encode("utf-8")), "text/csv")
    res_preview = client.post("/api/timetable/import/preview", files={"file": file_payload}, headers=headers)
    assert res_preview.status_code == 200
    preview = res_preview.json()

    assert preview["total_rows"] == 5
    assert preview["valid_count"] == 0
    assert preview["error_count"] == 5

    # Check descriptive error messages
    row1 = preview["rows"][0]
    assert any("not found in database" in err.lower() for err in row1["errors"])

    row2 = preview["rows"][1]
    assert any("must be strictly after start time" in err.lower() for err in row2["errors"])

    row3 = preview["rows"][2]
    assert any("inactive" in err.lower() for err in row3["errors"])

    row4 = preview["rows"][3]
    assert any("subject" in err.lower() and "not found" in err.lower() for err in row4["errors"])

    row5 = preview["rows"][4]
    assert any("missing required fields" in err.lower() for err in row5["errors"])


def test_detect_conflicting_section_periods(setup_phase4_data):
    """
    Requirement 4: Detect conflicting section periods (same section, same day with duplicate period or overlapping time).
    """
    info = setup_phase4_data
    admin_token = get_token(info["admin_user"], info["admin_pass"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    # In previous test, Section CSE-A on Monday has:
    # Period 1: 09:00 - 10:00
    # Period 2: 10:00 - 11:00

    # 1. Attempt to create conflicting duplicate period 1 for CSE-A on Monday -> 400 Bad Request
    res_dup_period = client.post("/api/timetable/entries", json={
        "semester_id": info["sem_id"],
        "subject_id": info["sub2_id"],
        "teacher_id": info["t2_id"],
        "section": "CSE-A",
        "day_of_week": 0,  # Monday
        "period_number": 1,  # Duplicate period
        "start_time": "11:00:00",
        "end_time": "12:00:00"
    }, headers=headers)
    assert res_dup_period.status_code == 400
    assert "already has period 1 assigned" in res_dup_period.json()["detail"].lower()

    # 2. Attempt to create overlapping time (e.g. 09:30 - 10:30 overlaps with 09:00-10:00 and 10:00-11:00)
    res_time_overlap = client.post("/api/timetable/entries", json={
        "semester_id": info["sem_id"],
        "subject_id": info["sub2_id"],
        "teacher_id": info["t2_id"],
        "section": "CSE-A",
        "day_of_week": 0,  # Monday
        "period_number": 5,
        "start_time": "09:30:00",
        "end_time": "10:30:00"
    }, headers=headers)
    assert res_time_overlap.status_code == 400
    assert "overlapping class" in res_time_overlap.json()["detail"].lower()


def test_detect_conflicting_teacher_assignments(setup_phase4_data):
    """
    Requirement 4: Detect conflicting teacher assignments (teacher double-booked on same day/period or overlapping time).
    """
    info = setup_phase4_data
    admin_token = get_token(info["admin_user"], info["admin_pass"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Teacher 1 (p4_prof_rao) is currently teaching:
    # Monday Period 1 (09:00 - 10:00) in Section CSE-A

    # Attempt to assign Teacher 1 to teach Section CSE-B on Monday Period 1 -> 400 Bad Request
    res_teacher_conflict = client.post("/api/timetable/entries", json={
        "semester_id": info["sem_id"],
        "subject_id": info["sub3_id"],
        "teacher_id": info["t1_id"],  # Same teacher
        "section": "CSE-B",           # Different section
        "day_of_week": 0,             # Same Monday
        "period_number": 1,           # Same period
        "start_time": "09:00:00",
        "end_time": "10:00:00"
    }, headers=headers)
    assert res_teacher_conflict.status_code == 400
    assert "already assigned to period 1" in res_teacher_conflict.json()["detail"].lower()

    # Also test internal file conflict: a CSV file with double-booked teacher
    conflict_csv = (
        "day,period,start_time,end_time,semester,section,subject,teacher\n"
        f"Friday,1,09:00,10:00,{info['sem_name']},CSE-A,{info['sub1_code']},{info['t1_user']}\n"
        f"Friday,1,09:00,10:00,{info['sem_name']},CSE-B,{info['sub3_code']},{info['t1_user']}\n"
    )
    file_payload = ("conflict.csv", io.BytesIO(conflict_csv.encode("utf-8")), "text/csv")
    res_preview = client.post("/api/timetable/import/preview", files={"file": file_payload}, headers=headers)
    assert res_preview.status_code == 200
    data = res_preview.json()
    assert data["conflict_count"] >= 1
    row2 = data["rows"][1]
    assert row2["status"] == "conflict"
    assert any("internal conflict" in err.lower() for err in row2["errors"])


def test_admin_correct_and_commit_import(setup_phase4_data):
    """
    Requirement 5: Allow Admin to correct invalid rows and review import errors before saving.
    """
    info = setup_phase4_data
    admin_token = get_token(info["admin_user"], info["admin_pass"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Simulate correcting row data on the client side:
    corrected_rows = [
        {
            "semester_id": info["sem_id"],
            "semester_name": info["sem_name"],
            "subject_id": info["sub1_id"],
            "subject_code": info["sub1_code"],
            "subject_name": "Computer Vision",
            "teacher_id": info["t1_id"],
            "teacher_name": "Prof. Rao",
            "section": "CSE-A",
            "day_of_week": 3,  # Thursday
            "day_name": "Thursday",
            "period_number": 3,
            "start_time": "11:00:00",
            "end_time": "12:00:00"
        }
    ]

    res_commit = client.post("/api/timetable/import/commit", json={"rows": corrected_rows}, headers=headers)
    assert res_commit.status_code == 200
    assert res_commit.json()["imported_count"] == 1


def test_scheduled_class_lookup_api(setup_phase4_data):
    """
    Requirement 7, 9:
    - Retrieve scheduled class for particular day and time.
    - Evaluate holidays, weekends, semester duration bounds, and substitute teachers.
    """
    info = setup_phase4_data
    admin_token = get_token(info["admin_user"], info["admin_pass"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Lookup by day_of_week=0 (Monday) and time=09:30
    res_time = client.get("/api/timetable/lookup?day_of_week=0&time=09:30:00&section=CSE-A", headers=headers)
    assert res_time.status_code == 200
    data = res_time.json()
    assert data["total_entries"] == 1
    entry = data["entries"][0]
    assert entry["period_number"] == 1
    assert entry["subject_code"] == info["sub1_code"]
    assert entry["section"] == "CSE-A"

    # 2. Sunday Weekend detection
    # Pick a known Sunday
    test_sunday = date(2026, 10, 25)  # 2026-10-25 is Sunday
    assert test_sunday.weekday() == 6
    res_sunday = client.get(f"/api/timetable/lookup?date={test_sunday}", headers=headers)
    assert res_sunday.status_code == 200
    assert res_sunday.json()["is_holiday"] is True
    assert "Sunday" in res_sunday.json()["holiday_name"]

    # 3. Holiday registration & detection
    test_holiday_date = date(2026, 11, 4)
    _db = SessionLocal()
    _db.query(Holiday).filter(Holiday.date == test_holiday_date).delete()
    _db.commit()
    _db.close()

    # Register holiday
    h_res = client.post("/api/timetable/holidays", json={
        "name": "Phase 4 College Fest Holiday",
        "date": str(test_holiday_date),
        "description": "Annual College Festival"
    }, headers=headers)
    assert h_res.status_code == 201

    res_hol = client.get(f"/api/timetable/lookup?date={test_holiday_date}", headers=headers)
    assert res_hol.status_code == 200
    assert res_hol.json()["is_holiday"] is True
    assert "College Fest" in res_hol.json()["holiday_name"]

    # 4. Outside semester boundary check
    res_outside = client.get(
        f"/api/timetable/lookup?date=2025-01-01&semester_id={info['sem_id']}",
        headers=headers
    )
    assert res_outside.status_code == 200
    assert res_outside.json()["is_outside_semester"] is True

    # 5. Substitute Teacher Authorization reflects in lookup
    db = SessionLocal()
    monday_entry = db.query(TimetableEntry).filter(
        TimetableEntry.semester_id == info["sem_id"],
        TimetableEntry.section == "CSE-A",
        TimetableEntry.day_of_week == 0,
        TimetableEntry.period_number == 1
    ).first()
    assert monday_entry is not None

    target_monday = date(2026, 10, 26)  # Monday
    db.query(SubstituteAuthorization).filter(
        SubstituteAuthorization.timetable_entry_id == monday_entry.id,
        SubstituteAuthorization.date == target_monday
    ).delete()
    db.commit()

    sub_auth = SubstituteAuthorization(
        timetable_entry_id=monday_entry.id,
        original_teacher_id=monday_entry.teacher_id,
        substitute_teacher_id=info["t2_id"],  # Prof Gupta substitutes for Prof Rao
        date=target_monday,
        reason="Medical emergency leave substitution",
        status="authorized"
    )
    db.add(sub_auth)
    db.commit()
    db.close()

    res_sub = client.get(f"/api/timetable/lookup?date={target_monday}&time=09:15:00&section=CSE-A", headers=headers)
    assert res_sub.status_code == 200
    sub_data = res_sub.json()
    assert sub_data["total_entries"] == 1
    sub_class = sub_data["entries"][0]
    assert sub_class["is_substituted"] is True
    assert sub_class["effective_teacher_id"] == info["t2_id"]
    assert "Prof. Gupta" in sub_class["effective_teacher_name"]


def test_role_restrictions_on_timetable_management(setup_phase4_data):
    """
    Requirement: Only Administrator can import, create, update, delete entries, and manage holidays.
    Teachers and Students cannot.
    """
    info = setup_phase4_data
    teacher_token = get_token(info["t1_user"], info["t1_pass"])
    student_token = get_token(info["student_user"], info["student_pass"])

    # 1. Teacher cannot import preview
    res_t_import = client.post("/api/timetable/import/preview", json={"rows": []}, headers={"Authorization": f"Bearer {teacher_token}"})
    assert res_t_import.status_code == 403

    # 2. Student cannot import commit
    res_s_commit = client.post("/api/timetable/import/commit", json={"rows": []}, headers={"Authorization": f"Bearer {student_token}"})
    assert res_s_commit.status_code == 403

    # 3. Teacher cannot create timetable entry
    res_t_create = client.post("/api/timetable/entries", json={
        "semester_id": info["sem_id"],
        "subject_id": info["sub1_id"],
        "teacher_id": info["t1_id"],
        "section": "CSE-A",
        "day_of_week": 4,
        "period_number": 4,
        "start_time": "14:00:00",
        "end_time": "15:00:00"
    }, headers={"Authorization": f"Bearer {teacher_token}"})
    assert res_t_create.status_code == 403

    # 4. Student cannot add holiday
    res_s_hol = client.post("/api/timetable/holidays", json={
        "name": "Student Hack Holiday",
        "date": "2026-12-25"
    }, headers={"Authorization": f"Bearer {student_token}"})
    assert res_s_hol.status_code == 403

    # 5. Unauthenticated cannot access management
    assert client.post("/api/timetable/import/preview").status_code == 401
    assert client.post("/api/timetable/entries").status_code == 401
