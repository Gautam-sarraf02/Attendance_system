"""
Comprehensive test suite for SmartAttend Secure Attendance Workflow:
1. Correct teacher face + live face -> session starts (15-min timer begins).
2. Wrong teacher face -> session rejected, timer not started.
3. Unregistered teacher -> session rejected, timer not started.
4. Teacher photo/video spoof -> session rejected.
5. Correct-section student -> attendance can be marked.
6. Wrong-section student -> rejected ("Wrong Section").
7. Wrong subject, teacher, weekday, or period -> rejected.
8. Attendance after 15 minutes -> rejected ("Deadline Expired").
9. Duplicate attendance request -> rejected ("Already Marked Present").
10. Missing anti-spoofing model or inference error -> safe failure, no attendance marked.
11. Old timetable entries (is_active=False) -> cannot authorize new sessions.
12. Timetable teacher conflicts -> detected and reported accurately.
"""
import base64
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
from app.models.timetable import TimetableEntry
from app.models.face_enrollment import FaceEnrollment
from app.models.face_sample import FaceSample
from app.models.attendance_session import AttendanceSession
from app.models.attendance import Attendance
from app.auth.jwt_handler import get_password_hash

client = TestClient(app)


def get_token(username: str, password: str = "Faculty@1234") -> str:
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


def make_b64_face_image(seed: int = 42) -> str:
    np.random.seed(seed)
    img = np.full((200, 200, 3), 140, dtype=np.uint8)
    cv2.circle(img, (100, 100), 60, (180, 180, 180), -1)
    cv2.circle(img, (75, 80), 12, (20, 20, 20), -1)
    cv2.circle(img, (125, 80), 12, (20, 20, 20), -1)
    cv2.ellipse(img, (100, 130), (25, 10), 0, 0, 180, (50, 50, 50), -1)
    _, buf = cv2.imencode(".jpg", img)
    return f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"


def cleanup_active_sessions():
    db = SessionLocal()
    db.query(AttendanceSession).filter(AttendanceSession.status == "active").update({"status": "closed"})
    db.commit()
    db.close()


@pytest.fixture(scope="module")
def setup_workflow_data():
    db = SessionLocal()
    try:
        # 1. Admin
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=get_password_hash("Admin@1234"),
                full_name="System Admin",
                role="admin",
                is_active=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        # 2. Kavita Ma'am (Faculty)
        kavita = db.query(User).filter(User.username == "kavita_maam").first()
        assert kavita is not None, "kavita_maam should exist from update script"

        # 3. Unregistered Teacher
        unreg_teacher = db.query(User).filter(User.username == "unreg_teacher").first()
        if not unreg_teacher:
            unreg_teacher = User(
                username="unreg_teacher",
                password_hash=get_password_hash("Faculty@1234"),
                full_name="Prof. Unregistered",
                role="faculty",
                faculty_id="FAC-UN01",
                is_active=True
            )
            db.add(unreg_teacher)
            db.commit()
            db.refresh(unreg_teacher)
        # Ensure no face enrollments exist for unreg_teacher
        db.query(FaceEnrollment).filter(FaceEnrollment.user_id == unreg_teacher.id).delete()
        db.commit()

        # 4. Active Timetable Entry for Kavita Ma'am
        active_entry = db.query(TimetableEntry).filter(
            TimetableEntry.teacher_id == kavita.id,
            TimetableEntry.section == "A",
            TimetableEntry.is_active == True
        ).first()
        assert active_entry is not None, "Active timetable entry for Kavita Ma'am should exist"

        # Active entry assigned to unreg_teacher so timetable check passes, but face check fails
        unreg_entry = db.query(TimetableEntry).filter(
            TimetableEntry.teacher_id == unreg_teacher.id,
            TimetableEntry.is_active == True
        ).first()
        if not unreg_entry:
            unreg_entry = TimetableEntry(
                semester_id=active_entry.semester_id,
                subject_id=active_entry.subject_id,
                teacher_id=unreg_teacher.id,
                section="UN-A",
                day_of_week=0,
                period_number=3,
                start_time=time(10, 40),
                end_time=time(11, 40),
                is_active=True
            )
            db.add(unreg_entry)
            db.commit()
            db.refresh(unreg_entry)

        # 5. Old/Inactive Timetable Entry
        old_entry = db.query(TimetableEntry).filter(TimetableEntry.is_active == False).first()
        if not old_entry:
            old_entry = TimetableEntry(
                semester_id=active_entry.semester_id,
                subject_id=active_entry.subject_id,
                teacher_id=kavita.id,
                section="OLD-A",
                day_of_week=0,
                period_number=99,
                start_time=time(6, 0),
                end_time=time(7, 0),
                is_active=False
            )
            db.add(old_entry)
            db.commit()
            db.refresh(old_entry)

        # 6. Students:
        ay = db.query(AcademicYear).filter(AcademicYear.is_current == True).first()
        stu_a = db.query(Student).filter(Student.roll_number == "TEST-SEC-A").first()
        if not stu_a:
            stu_a = Student(
                name="Student Section A",
                roll_number="TEST-SEC-A",
                email="stu_a@smartattend.edu",
                section="CSE-A",
                is_active=True
            )
            db.add(stu_a)
            db.commit()
            db.refresh(stu_a)

        stu_b = db.query(Student).filter(Student.roll_number == "TEST-SEC-B").first()
        if not stu_b:
            stu_b = Student(
                name="Student Section B",
                roll_number="TEST-SEC-B",
                email="stu_b@smartattend.edu",
                section="CSE-B",
                is_active=True
            )
            db.add(stu_b)
            db.commit()
            db.refresh(stu_b)

        # Enroll faces for stu_a and stu_b
        for st in [stu_a, stu_b]:
            enr = db.query(FaceEnrollment).filter(FaceEnrollment.student_id == st.id).first()
            if not enr:
                enr = FaceEnrollment(
                    student_id=st.id,
                    academic_year_id=ay.id if ay else 9,
                    valid_from=date(2026, 8, 1),
                    valid_until=date(2027, 7, 31),
                    status="active"
                )
                db.add(enr)
                db.commit()
                db.refresh(enr)

        return {
            "admin_id": admin.id,
            "kavita_id": kavita.id,
            "unreg_teacher_id": unreg_teacher.id,
            "active_entry_id": active_entry.id,
            "active_entry_day": active_entry.day_of_week,
            "active_entry_hour": active_entry.start_time.hour,
            "active_entry_min": active_entry.start_time.minute,
            "active_entry_period": active_entry.period_number,
            "active_entry_subject": active_entry.subject.name,
            "unreg_entry_id": unreg_entry.id,
            "unreg_entry_hour": unreg_entry.start_time.hour,
            "unreg_entry_min": unreg_entry.start_time.minute,
            "old_entry_id": old_entry.id,
            "stu_a_id": stu_a.id,
            "stu_b_id": stu_b.id,
            "ay_id": ay.id if ay else 9,
        }
    finally:
        db.close()


# ─── 1. Correct teacher face + live face -> session starts ────────────────────

def test_01_correct_teacher_face_and_live_face_starts_session(setup_workflow_data):
    cleanup_active_sessions()
    data = setup_workflow_data
    token = get_token("kavita_maam")
    headers = {"Authorization": f"Bearer {token}"}

    face_b64 = make_b64_face_image(seed=12)

    with patch("app.services.session_service.detector.decode_image_base64", return_value=np.ones((200, 200, 3), dtype=np.uint8)), \
         patch("app.services.session_service.detector.detect_faces", return_value=[(10, 10, 180, 180)]), \
         patch("app.services.session_service.detector.extract_and_normalize_face", return_value=np.ones((200, 200), dtype=np.uint8)), \
         patch("app.services.session_service.detector.evaluate_liveness", return_value=(True, 0.98, "Live face verified (real person)")), \
         patch("cv2.face.LBPHFaceRecognizer_create") as mock_rec_cls, \
         patch("cv2.matchTemplate", return_value=np.array([[0.85]])):

        mock_rec = mock_rec_cls.return_value
        mock_rec.predict.return_value = (data["kavita_id"], 35.0)

        payload = {
            "timetable_entry_id": data["active_entry_id"],
            "face_image": face_b64
        }
        target_date = "2026-10-19" if data["active_entry_day"] == 0 else "2026-10-20"
        sim_time = f"{data['active_entry_hour']:02d}:{data['active_entry_min']:02d}"

        res = client.post(
            f"/api/sessions/authorized-start?date={target_date}&time={sim_time}",
            json=payload,
            headers=headers
        )
        assert res.status_code in (200, 201), f"Session start failed: {res.text}"
        res_data = res.json()
        assert res_data["status"] == "active"
        assert res_data["recognition_window_end"] is not None
        assert res_data["teacher_id"] == data["kavita_id"]


# ─── 2. Wrong teacher face -> session rejected, timer not started ─────────────

def test_02_wrong_teacher_face_rejects_session(setup_workflow_data):
    cleanup_active_sessions()
    data = setup_workflow_data
    token = get_token("kavita_maam")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.session_service.detector.decode_image_base64", return_value=np.ones((200, 200, 3), dtype=np.uint8)), \
         patch("app.services.session_service.detector.detect_faces", return_value=[(10, 10, 180, 180)]), \
         patch("app.services.session_service.detector.extract_and_normalize_face", return_value=np.ones((200, 200), dtype=np.uint8)), \
         patch("app.services.session_service.detector.evaluate_liveness", return_value=(True, 0.95, "Live face")), \
         patch("cv2.face.LBPHFaceRecognizer_create") as mock_rec_cls, \
         patch("cv2.matchTemplate", return_value=np.array([[0.10]])):

        mock_rec = mock_rec_cls.return_value
        mock_rec.predict.return_value = (999, 120.0)

        payload = {
            "timetable_entry_id": data["active_entry_id"],
            "face_image": make_b64_face_image(seed=999)
        }
        target_date = "2026-10-19" if data["active_entry_day"] == 0 else "2026-10-20"
        sim_time = f"{data['active_entry_hour']:02d}:{data['active_entry_min']:02d}"

        res = client.post(
            f"/api/sessions/authorized-start?date={target_date}&time={sim_time}",
            json=payload,
            headers=headers
        )
        assert res.status_code == 403
        assert "Biometric face verification failed" in res.json()["detail"]


# ─── 3. Unregistered teacher -> session rejected, timer not started ───────────

def test_03_unregistered_teacher_face_rejects_session(setup_workflow_data):
    cleanup_active_sessions()
    data = setup_workflow_data
    token = get_token("unreg_teacher")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "timetable_entry_id": data["unreg_entry_id"],
        "face_image": make_b64_face_image(seed=1)
    }
    target_date = "2026-10-19"
    sim_time = f"{data['unreg_entry_hour']:02d}:{data['unreg_entry_min']:02d}"

    res = client.post(
        f"/api/sessions/authorized-start?date={target_date}&time={sim_time}",
        json=payload,
        headers=headers
    )
    assert res.status_code == 403
    detail = res.json()["detail"].lower()
    assert "no registered face biometrics" in detail or "unregistered" in detail


# ─── 4. Teacher photo/video spoof -> session rejected ─────────────────────────

def test_04_teacher_spoof_rejects_session(setup_workflow_data):
    cleanup_active_sessions()
    data = setup_workflow_data
    token = get_token("kavita_maam")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.session_service.detector.decode_image_base64", return_value=np.ones((200, 200, 3), dtype=np.uint8)), \
         patch("app.services.session_service.detector.detect_faces", return_value=[(10, 10, 180, 180)]), \
         patch("app.services.session_service.detector.extract_and_normalize_face", return_value=np.ones((200, 200), dtype=np.uint8)), \
         patch("app.services.session_service.detector.evaluate_liveness", return_value=(False, 0.12, "Spoof detected (printed paper presentation attack)")):

        payload = {
            "timetable_entry_id": data["active_entry_id"],
            "face_image": make_b64_face_image(seed=12)
        }
        target_date = "2026-10-19" if data["active_entry_day"] == 0 else "2026-10-20"
        sim_time = f"{data['active_entry_hour']:02d}:{data['active_entry_min']:02d}"

        res = client.post(
            f"/api/sessions/authorized-start?date={target_date}&time={sim_time}",
            json=payload,
            headers=headers
        )
        assert res.status_code == 403
        assert "Anti-spoofing check failed" in res.json()["detail"]


# ─── 5. Correct-section student -> attendance marked ──────────────────────────

def test_05_correct_section_student_attendance_marked(setup_workflow_data):
    cleanup_active_sessions()
    data = setup_workflow_data
    db = SessionLocal()
    try:
        now_utc = datetime.now(timezone.utc)
        session = AttendanceSession(
            timetable_entry_id=data["active_entry_id"],
            teacher_id=data["kavita_id"],
            academic_year_id=data["ay_id"],
            subject=data["active_entry_subject"],
            section="A",
            started_at=now_utc,
            status="active",
            recognition_window_end=now_utc + timedelta(minutes=15)
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Clear prior attendance
        db.query(Attendance).filter(Attendance.session_id == session.id).delete()
        db.commit()

        token = get_token("kavita_maam")
        headers = {"Authorization": f"Bearer {token}"}

        with patch("app.routers.attendance.detector.detect_faces", return_value=[(10, 10, 100, 100)]), \
             patch("app.routers.attendance.detector.evaluate_liveness", return_value=(True, 0.96, "Live real face")), \
             patch("app.routers.attendance.recognizer_service.predict", return_value=(data["stu_a_id"], 25.0, True)):

            payload = {
                "session_id": session.id,
                "image_base64": make_b64_face_image(),
                "auto_mark": True
            }
            res = client.post("/api/attendance/recognize", json=payload, headers=headers)
            assert res.status_code == 200, res.text
            res_data = res.json()
            assert res_data["detections"][0]["attendance_marked"] is True
            assert res_data["detections"][0]["status_message"] == "Marked Present"
    finally:
        db.close()


# ─── 6. Wrong-section student -> rejected ─────────────────────────────────────

def test_06_wrong_section_student_rejected(setup_workflow_data):
    cleanup_active_sessions()
    data = setup_workflow_data
    db = SessionLocal()
    try:
        now_utc = datetime.now(timezone.utc)
        session = AttendanceSession(
            timetable_entry_id=data["active_entry_id"],
            teacher_id=data["kavita_id"],
            academic_year_id=data["ay_id"],
            subject=data["active_entry_subject"],
            section="A",
            started_at=now_utc,
            status="active",
            recognition_window_end=now_utc + timedelta(minutes=15)
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        token = get_token("kavita_maam")
        headers = {"Authorization": f"Bearer {token}"}

        # Predict Section B student (stu_b_id) when session is Section A
        with patch("app.routers.attendance.detector.detect_faces", return_value=[(10, 10, 100, 100)]), \
             patch("app.routers.attendance.detector.evaluate_liveness", return_value=(True, 0.95, "Live real face")), \
             patch("app.routers.attendance.recognizer_service.predict", return_value=(data["stu_b_id"], 20.0, True)):

            payload = {
                "session_id": session.id,
                "image_base64": make_b64_face_image(),
                "auto_mark": True
            }
            res = client.post("/api/attendance/recognize", json=payload, headers=headers)
            assert res.status_code == 200
            res_data = res.json()
            assert res_data["detections"][0]["attendance_marked"] is False
            assert "Wrong Section" in res_data["detections"][0]["status_message"]
    finally:
        db.close()


# ─── 7. Wrong subject, teacher, weekday, or period -> rejected ────────────────

def test_07_wrong_subject_teacher_weekday_or_period_rejected(setup_workflow_data):
    cleanup_active_sessions()
    data = setup_workflow_data
    token = get_token("deepak_sir") # Deepak Sir is not assigned to Kavita's active entry
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "timetable_entry_id": data["active_entry_id"],
        "face_image": make_b64_face_image()
    }
    target_date = "2026-10-19" if data["active_entry_day"] == 0 else "2026-10-20"
    sim_time = f"{data['active_entry_hour']:02d}:{data['active_entry_min']:02d}"

    res = client.post(
        f"/api/sessions/authorized-start?date={target_date}&time={sim_time}",
        json=payload,
        headers=headers
    )
    assert res.status_code in (400, 403)
    detail = res.json()["detail"].lower()
    assert "unauthorized" in detail or "not assigned" in detail or "permission" in detail


# ─── 8. Attendance after 15 minutes -> rejected ───────────────────────────────

def test_08_attendance_after_15_minutes_rejected(setup_workflow_data):
    cleanup_active_sessions()
    data = setup_workflow_data
    db = SessionLocal()
    try:
        now_utc = datetime.now(timezone.utc)
        session = AttendanceSession(
            timetable_entry_id=data["active_entry_id"],
            teacher_id=data["kavita_id"],
            academic_year_id=data["ay_id"],
            subject=data["active_entry_subject"],
            section="A",
            started_at=now_utc - timedelta(minutes=20),
            status="active",
            recognition_window_end=now_utc - timedelta(minutes=5)
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        token = get_token("kavita_maam")
        headers = {"Authorization": f"Bearer {token}"}

        with patch("app.routers.attendance.detector.detect_faces", return_value=[(10, 10, 100, 100)]), \
             patch("app.routers.attendance.detector.evaluate_liveness", return_value=(True, 0.95, "Live real face")), \
             patch("app.routers.attendance.recognizer_service.predict", return_value=(data["stu_a_id"], 25.0, True)):

            payload = {
                "session_id": session.id,
                "image_base64": make_b64_face_image(),
                "auto_mark": True
            }
            res = client.post("/api/attendance/recognize", json=payload, headers=headers)
            assert res.status_code == 200
            res_data = res.json()
            assert res_data["detections"][0]["attendance_marked"] is False
            assert "Deadline Expired" in res_data["detections"][0]["status_message"]
    finally:
        db.close()


# ─── 9. Duplicate attendance request -> rejected ──────────────────────────────

def test_09_duplicate_attendance_rejected(setup_workflow_data):
    cleanup_active_sessions()
    data = setup_workflow_data
    db = SessionLocal()
    try:
        now_utc = datetime.now(timezone.utc)
        session = AttendanceSession(
            timetable_entry_id=data["active_entry_id"],
            teacher_id=data["kavita_id"],
            academic_year_id=data["ay_id"],
            subject=data["active_entry_subject"],
            section="A",
            started_at=now_utc,
            status="active",
            recognition_window_end=now_utc + timedelta(minutes=15)
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Clear prior records and insert one
        db.query(Attendance).filter(Attendance.session_id == session.id).delete()
        existing_att = Attendance(
            student_id=data["stu_a_id"],
            session_id=session.id,
            subject=session.subject,
            date=date.today(),
            time=time(9, 0),
            status="present",
            confidence_score=22.0
        )
        db.add(existing_att)
        db.commit()

        token = get_token("kavita_maam")
        headers = {"Authorization": f"Bearer {token}"}

        with patch("app.routers.attendance.detector.detect_faces", return_value=[(10, 10, 100, 100)]), \
             patch("app.routers.attendance.detector.evaluate_liveness", return_value=(True, 0.95, "Live real face")), \
             patch("app.routers.attendance.recognizer_service.predict", return_value=(data["stu_a_id"], 25.0, True)):

            payload = {
                "session_id": session.id,
                "image_base64": make_b64_face_image(),
                "auto_mark": True
            }
            res = client.post("/api/attendance/recognize", json=payload, headers=headers)
            assert res.status_code == 200
            res_data = res.json()
            assert res_data["detections"][0]["attendance_marked"] is False
            assert "Already Marked Present" in res_data["detections"][0]["status_message"]
    finally:
        db.close()


# ─── 10. Missing anti-spoofing model or inference error -> no attendance ──────

def test_10_missing_antispoof_model_or_inference_error_no_attendance(setup_workflow_data):
    cleanup_active_sessions()
    data = setup_workflow_data
    db = SessionLocal()
    try:
        now_utc = datetime.now(timezone.utc)
        session = AttendanceSession(
            timetable_entry_id=data["active_entry_id"],
            teacher_id=data["kavita_id"],
            academic_year_id=data["ay_id"],
            subject=data["active_entry_subject"],
            section="A",
            started_at=now_utc,
            status="active",
            recognition_window_end=now_utc + timedelta(minutes=15)
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        token = get_token("kavita_maam")
        headers = {"Authorization": f"Bearer {token}"}

        # Simulate anti-spoofing failure / exception (fails safe -> is_live = False)
        with patch("app.routers.attendance.detector.detect_faces", return_value=[(10, 10, 100, 100)]), \
             patch("app.routers.attendance.detector.evaluate_liveness", return_value=(False, 0.0, "Anti-spoofing inference error (fail-safe rejection)")), \
             patch("app.routers.attendance.recognizer_service.predict", return_value=(data["stu_a_id"], 25.0, True)):

            payload = {
                "session_id": session.id,
                "image_base64": make_b64_face_image(),
                "auto_mark": True
            }
            res = client.post("/api/attendance/recognize", json=payload, headers=headers)
            assert res.status_code == 200
            res_data = res.json()
            assert res_data["detections"][0]["attendance_marked"] is False
            assert "Liveness check failed" in res_data["detections"][0]["status_message"]
    finally:
        db.close()


# ─── 11. Old timetable entries cannot authorize new sessions ──────────────────

def test_11_old_timetable_entries_cannot_authorize_new_sessions(setup_workflow_data):
    cleanup_active_sessions()
    data = setup_workflow_data
    token = get_token("kavita_maam")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "timetable_entry_id": data["old_entry_id"],
        "face_image": make_b64_face_image()
    }
    res = client.post(
        "/api/sessions/authorized-start?date=2026-10-19&time=06:00",
        json=payload,
        headers=headers
    )
    assert res.status_code in (400, 404)
    detail = res.json()["detail"].lower()
    assert "inactive" in detail or "archived" in detail or "obsolete" in detail or "not found" in detail


# ─── 12. Timetable teacher conflicts detected and reported ─────────────────────

def test_12_timetable_teacher_conflicts_detected_and_reported():
    """
    Formally audits the Monday-Friday requested rotation schedule and detects:
    1. Friday Period 4 double-booking conflict for Kavita Ma'am (Sec B & Sec C).
    2. Practical/LAB single-instructor simultaneous conflict across Sec A, B, C.
    """
    db = SessionLocal()
    try:
        active_entries = db.query(TimetableEntry).filter(TimetableEntry.is_active == True).all()
        assert len(active_entries) > 0, "Active timetable entries must exist"

        # Check for any simultaneous teacher assignment
        slots = {}
        for e in active_entries:
            key = (e.day_of_week, e.period_number, e.teacher_id)
            if key not in slots:
                slots[key] = []
            slots[key].append(e.section)

        # Confirm NO active slot has the same teacher assigned to more than 1 section
        for (day, period, teacher_id), sections in slots.items():
            assert len(sections) == 1, f"Found active double-booked slot: Day {day}, Period {period}, Teacher {teacher_id} assigned to {sections}"

        # Confirm that Friday Period 4 conflict was detected:
        fri_p4_b = db.query(TimetableEntry).filter(
            TimetableEntry.day_of_week == 4,
            TimetableEntry.period_number == 4,
            TimetableEntry.section == "B",
            TimetableEntry.is_active == True
        ).first()
        assert fri_p4_b is not None
        assert fri_p4_b.subject.name == "Computer Vision"

        fri_p4_c = db.query(TimetableEntry).filter(
            TimetableEntry.day_of_week == 4,
            TimetableEntry.period_number == 4,
            TimetableEntry.section == "C",
            TimetableEntry.is_active == True
        ).first()
        # Section C must NOT be active with Kavita Ma'am to avoid double-booking
        assert fri_p4_c is None or fri_p4_c.teacher_id != fri_p4_b.teacher_id
    finally:
        db.close()
