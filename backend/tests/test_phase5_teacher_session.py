import base64
import json
from datetime import date, datetime, timedelta, timezone, time
from unittest.mock import patch
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.student import Student
from app.models.academic_year import AcademicYear
from app.models.semester import Semester
from app.models.subject import Subject
from app.models.timetable import TimetableEntry
from app.models.holiday import Holiday
from app.models.substitute_auth import SubstituteAuthorization
from app.models.face_enrollment import FaceEnrollment
from app.models.face_sample import FaceSample
from app.models.attendance_session import AttendanceSession
from app.models.audit_log import AuditLog
from app.auth.jwt_handler import get_password_hash
from app.face.detector import detector
from app.face.storage import storage

client = TestClient(app)


def get_token(username, password):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


def create_synthetic_face(width=200, height=200, brightness=125, pattern_seed=1):
    img = np.ones((height, width, 3), dtype=np.uint8) * brightness
    # Draw high frequency lines and circles to pass sharpness & feature detection
    for i in range(10, width - 10, 8):
        cv2.line(img, (i, 10), (i, height - 10), (pattern_seed * 15 % 255, 20, 20), 2)
        cv2.circle(img, (i, 100), 4, (240, 240, 240), -1)
    return img


def img_to_b64(img):
    _, buf = cv2.imencode('.jpg', img)
    return f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"


@pytest.fixture(scope="module")
def setup_phase5_data():
    db = SessionLocal()
    try:
        # 1. Admin
        admin = db.query(User).filter(User.username == "phase5_admin").first()
        if not admin:
            admin = User(
                username="phase5_admin",
                password_hash=get_password_hash("admin123"),
                full_name="Phase5 Admin",
                email="admin.p5@college.edu",
                role="admin",
                is_active=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        # 2. Teacher Alpha (primary teacher)
        teacher_alpha = db.query(User).filter(User.username == "teacher_alpha").first()
        if not teacher_alpha:
            teacher_alpha = User(
                username="teacher_alpha",
                password_hash=get_password_hash("alpha123"),
                full_name="Dr. Alpha Sharma",
                email="alpha@college.edu",
                role="teacher",
                is_active=True
            )
            db.add(teacher_alpha)
            db.commit()
            db.refresh(teacher_alpha)

        # 3. Teacher Beta (different teacher / substitute)
        teacher_beta = db.query(User).filter(User.username == "teacher_beta").first()
        if not teacher_beta:
            teacher_beta = User(
                username="teacher_beta",
                password_hash=get_password_hash("beta123"),
                full_name="Prof. Beta Patel",
                email="beta@college.edu",
                role="teacher",
                is_active=True
            )
            db.add(teacher_beta)
            db.commit()
            db.refresh(teacher_beta)

        # 4. Student User
        student_user = db.query(User).filter(User.username == "student_p5").first()
        if not student_user:
            student_user = User(
                username="student_p5",
                password_hash=get_password_hash("student123"),
                full_name="Student P5",
                email="student.p5@college.edu",
                role="student",
                is_active=True
            )
            db.add(student_user)
            db.commit()
            db.refresh(student_user)

        # 5. Academic Year & Semester
        today = date.today()
        ay = db.query(AcademicYear).filter(AcademicYear.name == "2026-2027-P5").first()
        if not ay:
            ay = AcademicYear(
                name="2026-2027-P5",
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=300),
                is_current=True
            )
            db.add(ay)
            db.commit()
            db.refresh(ay)

        sem = db.query(Semester).filter(Semester.name == "Semester P5").first()
        if not sem:
            sem = Semester(
                name="Semester P5",
                academic_year_id=ay.id,
                start_date=ay.start_date,
                end_date=ay.end_date,
                is_active=True
            )
            db.add(sem)
            db.commit()
            db.refresh(sem)

        # 6. Subjects
        sub_cv = db.query(Subject).filter(Subject.code == "CS501-P5").first()
        if not sub_cv:
            sub_cv = Subject(
                code="CS501-P5",
                name="Computer Vision P5",
                semester_id=sem.id,
                section="CSE-P5"
            )
            db.add(sub_cv)
            db.commit()
            db.refresh(sub_cv)

        # 7. Timetable Entries
        # Slot 1: Alpha's class today on period 1 (09:00 - 10:00)
        today_dow = today.weekday()
        # Clean up any leftover slot on this code/teacher
        db.query(TimetableEntry).filter(TimetableEntry.subject_id == sub_cv.id).delete()
        db.commit()

        slot_alpha = TimetableEntry(
            semester_id=sem.id,
            subject_id=sub_cv.id,
            teacher_id=teacher_alpha.id,
            section="CSE-P5",
            day_of_week=today_dow,
            period_number=1,
            start_time=time(9, 0),
            end_time=time(10, 0)
        )
        db.add(slot_alpha)

        # Slot 2: Different day slot (tomorrow or different day of week)
        other_dow = (today_dow + 1) % 6  # Monday to Saturday
        slot_other_day = TimetableEntry(
            semester_id=sem.id,
            subject_id=sub_cv.id,
            teacher_id=teacher_alpha.id,
            section="CSE-P5",
            day_of_week=other_dow,
            period_number=2,
            start_time=time(10, 0),
            end_time=time(11, 0)
        )
        db.add(slot_other_day)
        db.commit()
        db.refresh(slot_alpha)
        db.refresh(slot_other_day)

        # 8. Enroll Face for Teacher Alpha
        # Remove any existing face samples and enrollment
        db.query(FaceEnrollment).filter(FaceEnrollment.user_id == teacher_alpha.id).delete()
        db.commit()

        enroll_alpha = FaceEnrollment(
            user_id=teacher_alpha.id,
            academic_year_id=ay.id,
            status="active",
            valid_from=today - timedelta(days=10),
            valid_until=today + timedelta(days=350)
        )
        db.add(enroll_alpha)
        db.commit()
        db.refresh(enroll_alpha)

        # Save synthetic normalized face template for teacher alpha
        alpha_face_img = create_synthetic_face(200, 200, brightness=130, pattern_seed=5)
        file_path, file_name = storage.save_face_sample(
            entity_id=teacher_alpha.id,
            face_image=alpha_face_img,
            sample_index=1,
            is_user=True
        )
        sample = FaceSample(
            user_id=teacher_alpha.id,
            enrollment_id=enroll_alpha.id,
            image_path=file_path,
            file_name=file_name
        )
        db.add(sample)
        db.commit()

        # Enroll Face for Teacher Beta
        db.query(FaceEnrollment).filter(FaceEnrollment.user_id == teacher_beta.id).delete()
        db.commit()

        enroll_beta = FaceEnrollment(
            user_id=teacher_beta.id,
            academic_year_id=ay.id,
            status="active",
            valid_from=today - timedelta(days=10),
            valid_until=today + timedelta(days=350)
        )
        db.add(enroll_beta)
        db.commit()
        db.refresh(enroll_beta)

        beta_face_img = create_synthetic_face(200, 200, brightness=140, pattern_seed=9)
        file_path_b, file_name_b = storage.save_face_sample(
            entity_id=teacher_beta.id,
            face_image=beta_face_img,
            sample_index=1,
            is_user=True
        )
        sample_b = FaceSample(
            user_id=teacher_beta.id,
            enrollment_id=enroll_beta.id,
            image_path=file_path_b,
            file_name=file_name_b
        )
        db.add(sample_b)
        db.commit()

        # Clean existing sessions on slot_alpha
        db.query(AttendanceSession).filter(AttendanceSession.timetable_entry_id == slot_alpha.id).delete()
        db.commit()

        return {
            "admin_user": "phase5_admin",
            "admin_pass": "admin123",
            "alpha_user": "teacher_alpha",
            "alpha_pass": "alpha123",
            "alpha_id": teacher_alpha.id,
            "alpha_face_b64": img_to_b64(alpha_face_img),
            "beta_user": "teacher_beta",
            "beta_pass": "beta123",
            "beta_id": teacher_beta.id,
            "beta_face_b64": img_to_b64(beta_face_img),
            "student_user": "student_p5",
            "student_pass": "student123",
            "slot_alpha_id": slot_alpha.id,
            "slot_other_day_id": slot_other_day.id,
            "ay_id": ay.id,
            "sem_id": sem.id,
            "enroll_alpha_id": enroll_alpha.id,
            "today": today,
            "today_dow": today_dow
        }
    finally:
        db.close()


def test_teacher_assigned_slots_list(setup_phase5_data):
    """
    Requirement 1: Teacher logs in and inspects assigned classes.
    Students must be blocked from inspecting teacher schedules.
    """
    info = setup_phase5_data
    alpha_token = get_token(info["alpha_user"], info["alpha_pass"])
    student_token = get_token(info["student_user"], info["student_pass"])

    # 1. Teacher can retrieve assigned slots for today
    res = client.get(
        "/api/sessions/teacher/assigned-slots",
        headers={"Authorization": f"Bearer {alpha_token}"}
    )
    assert res.status_code == 200
    slots = res.json()
    assert isinstance(slots, list)
    assert len(slots) >= 1
    slot = slots[0]
    assert slot["timetable_entry_id"] == info["slot_alpha_id"]
    assert slot["subject_code"] == "CS501-P5"
    assert slot["section"] == "CSE-P5"
    assert slot["day_of_week"] == info["today_dow"]

    # 2. Student is blocked (403 Forbidden)
    res_stu = client.get(
        "/api/sessions/teacher/assigned-slots",
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert res_stu.status_code == 403


def test_unauthorized_teacher_blocked(setup_phase5_data):
    """
    Requirement 2 & 6:
    Prevent unauthorized teachers from starting sessions on classes they are not assigned to.
    """
    info = setup_phase5_data
    beta_token = get_token(info["beta_user"], info["beta_pass"])
    student_token = get_token(info["student_user"], info["student_pass"])

    # Teacher Beta tries to start Alpha's class slot -> 403 Forbidden
    with patch.object(detector, 'detect_faces', return_value=[(10, 10, 180, 180)]):
        res_unauth = client.post(
            "/api/sessions/authorized-start?time=09:15",
            json={
                "timetable_entry_id": info["slot_alpha_id"],
                "face_image": info["beta_face_b64"]
            },
            headers={"Authorization": f"Bearer {beta_token}"}
        )
        assert res_unauth.status_code == 403
        assert "Unauthorized instructor" in res_unauth.json()["detail"]

    # Student cannot start session -> 403 Forbidden
    res_student = client.post(
        "/api/sessions/authorized-start?time=09:15",
        json={
            "timetable_entry_id": info["slot_alpha_id"],
            "face_image": info["alpha_face_b64"]
        },
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert res_student.status_code == 403


def test_incorrect_time_slot_rejected(setup_phase5_data):
    """
    Requirement 2 & 11:
    Validate time slot and day:
    - Attempting to start outside the scheduled time slot must be rejected with 400 Bad Request.
    - Attempting to start on a day other than the scheduled day must be rejected with 400 Bad Request.
    """
    info = setup_phase5_data
    alpha_token = get_token(info["alpha_user"], info["alpha_pass"])
    headers = {"Authorization": f"Bearer {alpha_token}"}

    with patch.object(detector, 'detect_faces', return_value=[(10, 10, 180, 180)]):
        # 1. Slot is 09:00 - 10:00. Teacher attempts to start at 14:30 -> 400 Bad Request
        res_time_err = client.post(
            "/api/sessions/authorized-start?time=14:30",
            json={
                "timetable_entry_id": info["slot_alpha_id"],
                "face_image": info["alpha_face_b64"]
            },
            headers=headers
        )
        assert res_time_err.status_code == 400
        assert "Time slot mismatch" in res_time_err.json()["detail"]

        # 2. Attempting to start slot scheduled for a different day of week -> 400 Bad Request
        res_day_err = client.post(
            "/api/sessions/authorized-start?time=10:15",
            json={
                "timetable_entry_id": info["slot_other_day_id"],
                "face_image": info["alpha_face_b64"]
            },
            headers=headers
        )
        assert res_day_err.status_code == 400
        assert "Scheduled day mismatch" in res_day_err.json()["detail"]


def test_holiday_and_weekend_blocked(setup_phase5_data):
    """
    Requirement 9:
    Classes cannot be initiated on declared holidays or weekends.
    """
    info = setup_phase5_data
    alpha_token = get_token(info["alpha_user"], info["alpha_pass"])
    headers = {"Authorization": f"Bearer {alpha_token}"}
    db = SessionLocal()

    holiday_date = info["today"]
    hol = db.query(Holiday).filter(Holiday.date == holiday_date).first()
    if not hol:
        hol = Holiday(
            name="Phase 5 Test Holiday",
            date=holiday_date,
            description="Testing holiday session lockout"
        )
        db.add(hol)
        db.commit()

    try:
        with patch.object(detector, 'detect_faces', return_value=[(10, 10, 180, 180)]):
            res_hol = client.post(
                "/api/sessions/authorized-start?time=09:15",
                json={
                    "timetable_entry_id": info["slot_alpha_id"],
                    "face_image": info["alpha_face_b64"]
                },
                headers=headers
            )
            assert res_hol.status_code == 400
            assert "Cannot start session on scheduled holiday" in res_hol.json()["detail"]
    finally:
        db.delete(hol)
        db.commit()
        db.close()


def test_expired_and_missing_biometric_enrollment(setup_phase5_data):
    """
    Requirement 3, 6, 11:
    - Teacher without biometric enrollment must be blocked (403).
    - Teacher with expired biometric enrollment must be blocked (403).
    """
    info = setup_phase5_data
    db = SessionLocal()

    # Create temporary teacher Charlie with NO enrollment
    charlie = db.query(User).filter(User.username == "teacher_charlie_p5").first()
    if not charlie:
        charlie = User(
            username="teacher_charlie_p5",
            password_hash=get_password_hash("charlie123"),
            full_name="Dr. Charlie NoEnroll",
            role="teacher",
            is_active=True
        )
        db.add(charlie)
        db.commit()
        db.refresh(charlie)

    charlie_token = get_token("teacher_charlie_p5", "charlie123")

    today = date.today()
    sub_cv = db.query(Subject).filter(Subject.code == "CS501-P5").first()
    slot_charlie = TimetableEntry(
        semester_id=info["sem_id"],
        subject_id=sub_cv.id,
        teacher_id=charlie.id,
        section="CSE-C",
        day_of_week=today.weekday(),
        period_number=1,
        start_time=time(9, 0),
        end_time=time(10, 0)
    )
    db.add(slot_charlie)
    db.commit()
    db.refresh(slot_charlie)

    try:
        # Charlie tries to start session without face enrollment -> 403 Forbidden
        with patch.object(detector, 'detect_faces', return_value=[(10, 10, 180, 180)]):
            res_no_enroll = client.post(
                "/api/sessions/authorized-start?time=09:15",
                json={
                    "timetable_entry_id": slot_charlie.id,
                    "face_image": info["alpha_face_b64"]
                },
                headers={"Authorization": f"Bearer {charlie_token}"}
            )
            assert res_no_enroll.status_code == 403
            assert "no registered face biometrics" in res_no_enroll.json()["detail"]

        # Now give Charlie an EXPIRED enrollment
        exp_enroll = FaceEnrollment(
            user_id=charlie.id,
            academic_year_id=info["ay_id"],
            status="active",
            valid_from=today - timedelta(days=400),
            valid_until=today - timedelta(days=35)
        )
        db.add(exp_enroll)
        db.commit()

        # Save template for charlie
        storage.save_face_sample(charlie.id, create_synthetic_face(), 1, is_user=True)

        with patch.object(detector, 'detect_faces', return_value=[(10, 10, 180, 180)]):
            res_exp = client.post(
                "/api/sessions/authorized-start?time=09:15",
                json={
                    "timetable_entry_id": slot_charlie.id,
                    "face_image": info["alpha_face_b64"]
                },
                headers={"Authorization": f"Bearer {charlie_token}"}
            )
            assert res_exp.status_code == 403
            assert "expired" in res_exp.json()["detail"].lower()
    finally:
        db.query(FaceEnrollment).filter(FaceEnrollment.user_id == charlie.id).delete()
        db.query(FaceSample).filter(FaceSample.user_id == charlie.id).delete()
        db.delete(slot_charlie)
        db.delete(charlie)
        db.commit()
        db.close()


def test_camera_failure_and_invalid_face_capture(setup_phase5_data):
    """
    Requirement 10:
    Handle camera failures and invalid face captures safely:
    - Missing face image -> 400 Bad Request
    - Corrupted image stream -> 422 Unprocessable Entity
    - No face detected -> 422 Unprocessable Entity
    - Multiple faces in frame -> 422 Unprocessable Entity
    - Wrong person's face -> 403 Forbidden
    """
    info = setup_phase5_data
    alpha_token = get_token(info["alpha_user"], info["alpha_pass"])
    headers = {"Authorization": f"Bearer {alpha_token}"}

    # 1. Missing image -> 400 Bad Request
    res_empty = client.post(
        "/api/sessions/authorized-start?time=09:15",
        json={"timetable_entry_id": info["slot_alpha_id"], "face_image": ""},
        headers=headers
    )
    assert res_empty.status_code == 400

    # 2. Corrupted image buffer -> 422 Unprocessable Entity
    res_corrupt = client.post(
        "/api/sessions/authorized-start?time=09:15",
        json={"timetable_entry_id": info["slot_alpha_id"], "face_image": "data:image/jpeg;base64,not-a-valid-image"},
        headers=headers
    )
    assert res_corrupt.status_code == 422

    # 3. No face detected in frame -> 422 Unprocessable Entity
    with patch.object(detector, 'detect_faces', return_value=[]):
        res_no_face = client.post(
            "/api/sessions/authorized-start?time=09:15",
            json={"timetable_entry_id": info["slot_alpha_id"], "face_image": info["alpha_face_b64"]},
            headers=headers
        )
        assert res_no_face.status_code == 422
        assert "No face detected" in res_no_face.json()["detail"]

    # 4. Multiple faces detected in frame -> 422 Unprocessable Entity
    with patch.object(detector, 'detect_faces', return_value=[(10, 10, 50, 50), (80, 80, 50, 50)]):
        res_multi_face = client.post(
            "/api/sessions/authorized-start?time=09:15",
            json={"timetable_entry_id": info["slot_alpha_id"], "face_image": info["alpha_face_b64"]},
            headers=headers
        )
        assert res_multi_face.status_code == 422
        assert "Multiple faces" in res_multi_face.json()["detail"]

    # 5. Teacher Alpha presents Teacher Beta's face (unmatching biometric profile) -> 403 Forbidden
    with patch.object(detector, 'detect_faces', return_value=[(10, 10, 180, 180)]):
        with patch.object(cv2.face.LBPHFaceRecognizer, 'predict', return_value=(999, 120.0)):
            res_wrong_face = client.post(
                "/api/sessions/authorized-start?time=09:15",
                json={"timetable_entry_id": info["slot_alpha_id"], "face_image": info["beta_face_b64"]},
                headers=headers
            )
            assert res_wrong_face.status_code == 403
            assert "Biometric face verification failed" in res_wrong_face.json()["detail"]


def test_successful_authorized_session_creation(setup_phase5_data):
    """
    Requirements 3, 4, 5, 8, 9:
    - Teacher Alpha passes face verification.
    - Creates attendance session linked to timetable slot, teacher, subject, semester, section, and academic year.
    - Server clock records start time and establishes 15-minute deadline.
    - Status is 'active'.
    - Comprehensive audit log is created.
    """
    info = setup_phase5_data
    alpha_token = get_token(info["alpha_user"], info["alpha_pass"])
    headers = {"Authorization": f"Bearer {alpha_token}"}
    db = SessionLocal()

    # Clean existing active sessions on slot_alpha
    db.query(AttendanceSession).filter(AttendanceSession.timetable_entry_id == info["slot_alpha_id"]).delete()
    db.commit()

    with patch.object(detector, 'detect_faces', return_value=[(10, 10, 180, 180)]), \
         patch.object(detector, 'evaluate_liveness', return_value=(True, 0.95, "Live real face")), \
         patch.object(cv2.face.LBPHFaceRecognizer, 'predict', return_value=(info["alpha_id"], 15.0)):
        res = client.post(
            "/api/sessions/authorized-start?time=09:15",
            json={
                "timetable_entry_id": info["slot_alpha_id"],
                "face_image": info["alpha_face_b64"]
            },
            headers=headers
        )
        assert res.status_code == 201
        session_data = res.json()

        # Verify response schema and links (Requirement 4)
        assert session_data["status"] == "active"
        assert session_data["timetable_entry_id"] == info["slot_alpha_id"]
        assert session_data["teacher_id"] == info["alpha_id"]
        assert session_data["subject"] == "Computer Vision P5"
        assert session_data["section"] == "CSE-P5"
        assert session_data["semester_id"] == info["sem_id"]
        assert session_data["academic_year_id"] == info["ay_id"]
        assert session_data["teacher_name"] == "Dr. Alpha Sharma"

        # Verify 15-minute deadline (Requirement 5)
        assert session_data["recognition_window_end"] is not None
        assert session_data["is_deadline_passed"] is False
        assert session_data["remaining_deadline_seconds"] > 800  # ~900s for 15 minutes

        # Verify Audit Logging (Requirement 9)
        audit = db.query(AuditLog).filter(
            AuditLog.action == "START_AUTHORIZED_SESSION",
            AuditLog.entity_id == session_data["id"]
        ).first()
        assert audit is not None
        assert audit.user_id == info["alpha_id"]
        details = json.loads(audit.details)
        assert details["timetable_entry_id"] == info["slot_alpha_id"]
        assert details["deadline_window_minutes"] == 15
    db.close()


def test_duplicate_active_session_conflicts(setup_phase5_data):
    """
    Requirement 7 & 11:
    Prevent duplicate active sessions:
    - Another session on the same timetable slot -> 409 Conflict.
    - Teacher attempting to open a second concurrent active session -> 409 Conflict.
    """
    info = setup_phase5_data
    alpha_token = get_token(info["alpha_user"], info["alpha_pass"])
    headers = {"Authorization": f"Bearer {alpha_token}"}

    # An active session already exists from previous test
    with patch.object(detector, 'detect_faces', return_value=[(10, 10, 180, 180)]), \
         patch.object(detector, 'evaluate_liveness', return_value=(True, 0.95, "Live real face")), \
         patch.object(cv2.face.LBPHFaceRecognizer, 'predict', return_value=(info["alpha_id"], 15.0)):
        res_dup = client.post(
            "/api/sessions/authorized-start?time=09:20",
            json={
                "timetable_entry_id": info["slot_alpha_id"],
                "face_image": info["alpha_face_b64"]
            },
            headers=headers
        )
        assert res_dup.status_code == 409
        assert "already open" in res_dup.json()["detail"] or "already has an active session" in res_dup.json()["detail"]


def test_session_closure_and_review_required(setup_phase5_data):
    """
    Requirements 8 & 9:
    - Test session closure (transitions state to 'closed', records ended_at, creates audit log).
    - Test flagging session as 'review-required' with remarks and audit log.
    - Test permission isolation (unauthorized teachers cannot close sessions).
    """
    info = setup_phase5_data
    alpha_token = get_token(info["alpha_user"], info["alpha_pass"])
    beta_token = get_token(info["beta_user"], info["beta_pass"])
    db = SessionLocal()

    active_sess = db.query(AttendanceSession).filter(
        AttendanceSession.timetable_entry_id == info["slot_alpha_id"],
        AttendanceSession.status == "active"
    ).first()
    assert active_sess is not None

    # 1. Teacher Beta tries to close Teacher Alpha's session -> 403 Forbidden
    res_unauth = client.post(
        f"/api/sessions/{active_sess.id}/close",
        headers={"Authorization": f"Bearer {beta_token}"}
    )
    assert res_unauth.status_code == 403
    assert "Access denied" in res_unauth.json()["detail"]

    # 2. Flag session for review (Requirement 8 & 9)
    res_flag = client.post(
        f"/api/sessions/{active_sess.id}/flag-review",
        json={"reason": "Power outage disrupted attendance scan midway", "require_review": True},
        headers={"Authorization": f"Bearer {alpha_token}"}
    )
    assert res_flag.status_code == 200
    flagged = res_flag.json()
    assert flagged["status"] == "review-required"
    assert flagged["review_reason"] == "Power outage disrupted attendance scan midway"

    # Verify audit log for review flag
    audit_flag = db.query(AuditLog).filter(
        AuditLog.action == "FLAG_SESSION_REVIEW",
        AuditLog.entity_id == active_sess.id
    ).first()
    assert audit_flag is not None

    # 3. Create another session and close normally
    db.query(AttendanceSession).filter(AttendanceSession.id == active_sess.id).delete()
    db.commit()

    with patch.object(detector, 'detect_faces', return_value=[(10, 10, 180, 180)]), \
         patch.object(detector, 'evaluate_liveness', return_value=(True, 0.95, "Live real face")), \
         patch.object(cv2.face.LBPHFaceRecognizer, 'predict', return_value=(info["alpha_id"], 15.0)):
        res_new = client.post(
            "/api/sessions/authorized-start?time=09:15",
            json={
                "timetable_entry_id": info["slot_alpha_id"],
                "face_image": info["alpha_face_b64"]
            },
            headers={"Authorization": f"Bearer {alpha_token}"}
        )
        assert res_new.status_code == 201
        new_id = res_new.json()["id"]

    # Close session normally
    res_close = client.post(
        f"/api/sessions/{new_id}/close",
        headers={"Authorization": f"Bearer {alpha_token}"}
    )
    assert res_close.status_code == 200
    closed_data = res_close.json()
    assert closed_data["status"] == "closed"
    assert closed_data["ended_at"] is not None

    # Verify audit log for session closure
    audit_close = db.query(AuditLog).filter(
        AuditLog.action == "CLOSE_SESSION",
        AuditLog.entity_id == new_id
    ).first()
    assert audit_close is not None
    db.close()


def test_substitute_teacher_authorized_session(setup_phase5_data):
    """
    Requirements 2, 3, 6, 9:
    Substitute teacher authorization:
    - Admin authorizes Teacher Beta to substitute for Teacher Alpha on slot_alpha today.
    - Teacher Beta verifies their own face and successfully starts the authorized session.
    """
    info = setup_phase5_data
    beta_token = get_token(info["beta_user"], info["beta_pass"])
    db = SessionLocal()

    # Clean existing sessions on slot_alpha and for teacher Beta
    db.query(AttendanceSession).filter(AttendanceSession.timetable_entry_id == info["slot_alpha_id"]).delete()
    db.query(AttendanceSession).filter(AttendanceSession.teacher_id == info["beta_id"]).delete()
    db.commit()

    # Authorize Beta as substitute on slot_alpha today
    sub_auth = SubstituteAuthorization(
        timetable_entry_id=info["slot_alpha_id"],
        original_teacher_id=info["alpha_id"],
        substitute_teacher_id=info["beta_id"],
        date=info["today"],
        reason="Dr. Alpha attending university research symposium",
        status="authorized"
    )
    db.add(sub_auth)
    db.commit()

    try:
        # Teacher Beta starts session with verified face
        with patch.object(detector, 'detect_faces', return_value=[(10, 10, 180, 180)]), \
             patch.object(detector, 'evaluate_liveness', return_value=(True, 0.95, "Live real face")), \
             patch.object(cv2.face.LBPHFaceRecognizer, 'predict', return_value=(info["beta_id"], 12.0)):
            res_sub = client.post(
                "/api/sessions/authorized-start?time=09:20",
                json={
                    "timetable_entry_id": info["slot_alpha_id"],
                    "face_image": info["beta_face_b64"]
                },
                headers={"Authorization": f"Bearer {beta_token}"}
            )
            assert res_sub.status_code == 201
            sess = res_sub.json()
            assert sess["status"] == "active"
            assert sess["teacher_id"] == info["beta_id"]
            assert sess["timetable_entry_id"] == info["slot_alpha_id"]

            # Check audit log reflects substitute authorization
            fresh_db = SessionLocal()
            audit = fresh_db.query(AuditLog).filter(
                AuditLog.action == "START_AUTHORIZED_SESSION",
                AuditLog.entity_id == sess["id"]
            ).order_by(AuditLog.id.desc()).first()
            assert audit is not None
            details = json.loads(audit.details)
            assert details["is_substitute"] is True
            fresh_db.close()
    finally:
        db.delete(sub_auth)
        db.commit()
        db.close()
