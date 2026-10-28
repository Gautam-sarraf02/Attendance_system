import base64
import json
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.student import Student
from app.models.subject import Subject
from app.models.timetable import TimetableEntry, get_section_variants
from app.models.attendance_session import AttendanceSession
from app.models.attendance import Attendance
from app.models.substitute_auth import SubstituteAuthorization
from app.models.face_enrollment import FaceEnrollment
from app.models.audit_log import AuditLog

client = TestClient(app)


def get_token(username: str, password: str = "Faculty@1234") -> str:
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


def make_face_image(seed: int = 42) -> str:
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





# ─── 1. Complete Database Audit of All Configured Subjects & Faculty ─────────────

def test_audit_all_configured_subjects_and_faculty():
    db = SessionLocal()
    try:
        configured_pairs = [
            ("Computer Vision", "kavita_maam", "FAC-KV01"),
            ("Big Data", "sumit_sir", "FAC-SM02"),
            ("R Programming", "deepak_sir", "FAC-DP03"),
            ("PD", "pd_trainer", "FAC-PD04"),
            ("Practical/LAB", "lab_instructor", "FAC-LB05"),
        ]

        for subj_name, username, expected_fid in configured_pairs:
            subj = db.query(Subject).filter(Subject.name == subj_name).first()
            assert subj is not None, f"Subject '{subj_name}' must exist in database"
            assert subj.is_active is True

            user = db.query(User).filter(User.username == username).first()
            assert user is not None, f"Faculty user '{username}' must exist in database"
            assert user.is_active is True
            assert user.faculty_id == expected_fid

            # Verify active face enrollment
            enrollment = db.query(FaceEnrollment).filter(
                FaceEnrollment.user_id == user.id,
                FaceEnrollment.status == "active"
            ).first()
            assert enrollment is not None, f"Face enrollment must be active for {user.full_name}"

            # Verify active timetable entries exist for this faculty
            active_slots = db.query(TimetableEntry).filter(
                TimetableEntry.teacher_id == user.id,
                TimetableEntry.subject_id == subj.id,
                TimetableEntry.is_active == True
            ).all()
            assert len(active_slots) > 0, f"Active timetable slots must exist for {subj_name} / {user.full_name}"
    finally:
        db.close()


# ─── 2. Session Authorization for Every Configured Subject ─────────────────────

@pytest.mark.parametrize("subject_name,username,section,dow,period,sim_time", [
    ("Computer Vision", "kavita_maam", "A", 0, 1, "08:45"),
    ("Big Data", "sumit_sir", "B", 0, 1, "08:45"),
    ("R Programming", "deepak_sir", "C", 0, 1, "08:45"),
    ("PD", "pd_trainer", "C", 0, 2, "09:50"),
    ("Practical/LAB", "lab_instructor", "A", 0, 5, "14:00"),
])
def test_all_subjects_session_authorization_by_assigned_faculty(subject_name, username, section, dow, period, sim_time):
    cleanup_active_sessions()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        slot = db.query(TimetableEntry).join(Subject).filter(
            Subject.name == subject_name,
            TimetableEntry.teacher_id == user.id,
            TimetableEntry.section == section,
            TimetableEntry.day_of_week == dow,
            TimetableEntry.period_number == period,
            TimetableEntry.is_active == True
        ).first()
        assert slot is not None, f"Expected slot for {subject_name} sec {section} P{period}"
        slot_id = slot.id
        user_id = user.id
    finally:
        db.close()

    token = get_token(username)
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.session_service.detector.decode_image_base64", return_value=np.ones((200, 200, 3), dtype=np.uint8)), \
         patch("app.services.session_service.detector.detect_faces", return_value=[(10, 10, 180, 180)]), \
         patch("app.services.session_service.detector.extract_and_normalize_face", return_value=np.ones((200, 200), dtype=np.uint8)), \
         patch("app.services.session_service.detector.evaluate_liveness", return_value=(True, 0.98, "Live face verified")), \
         patch("cv2.face.LBPHFaceRecognizer_create") as mock_rec_cls, \
         patch("cv2.matchTemplate", return_value=np.array([[0.85]])):

        mock_rec = mock_rec_cls.return_value
        mock_rec.predict.return_value = (user_id, 30.0)

        # 2026-10-19 is a Monday (dow=0)
        res = client.post(
            f"/api/sessions/authorized-start?date=2026-10-19&time={sim_time}",
            json={
                "timetable_entry_id": slot_id,
                "face_image": make_face_image()
            },
            headers=headers
        )
        assert res.status_code in (200, 201), f"Authorized start failed for {subject_name}: {res.text}"
        data = res.json()
        assert data["status"] == "active"
        assert data["subject"] == subject_name
        assert data["section"] == section
        assert data["teacher_id"] == user_id
        # Verify 15-minute window is set
        assert "recognition_window_end" in data
        assert data["recognition_window_end"] is not None


# ─── 3. Section Alias & CSE Prefix Normalization ────────────────────────────────

def test_section_alias_resolution_cse_a_matches_active_slot():
    """Verifies that requesting 'CSE-A' resolves to active slot 'A' without archived error."""
    cleanup_active_sessions()
    token = get_token("kavita_maam")
    headers = {"Authorization": f"Bearer {token}"}
    kavita = SessionLocal().query(User).filter(User.username == "kavita_maam").first()

    with patch("app.services.session_service.detector.decode_image_base64", return_value=np.ones((200, 200, 3), dtype=np.uint8)), \
         patch("app.services.session_service.detector.detect_faces", return_value=[(10, 10, 180, 180)]), \
         patch("app.services.session_service.detector.extract_and_normalize_face", return_value=np.ones((200, 200), dtype=np.uint8)), \
         patch("app.services.session_service.detector.evaluate_liveness", return_value=(True, 0.98, "Live face verified")), \
         patch("cv2.face.LBPHFaceRecognizer_create") as mock_rec_cls, \
         patch("cv2.matchTemplate", return_value=np.array([[0.85]])):

        mock_rec = mock_rec_cls.return_value
        mock_rec.predict.return_value = (kavita.id, 25.0)

        # Send manual subject "Computer Vision" with section "CSE-A"
        res = client.post(
            "/api/sessions/authorized-start?date=2026-10-19&time=08:45",
            json={
                "subject": "Computer Vision",
                "section": "CSE-A",
                "face_image": make_face_image()
            },
            headers=headers
        )
        assert res.status_code in (200, 201), f"Failed to resolve section alias: {res.text}"
        data = res.json()
        assert data["status"] == "active"
        assert data["subject"] == "Computer Vision"
        assert data["section"] in ("A", "CSE-A")


# ─── 4. Archived Slot 51 Safe Resolution & Obsolete Slot Rejection ────────────

def test_archived_slot_51_safe_resolution_to_active_entry():
    """
    Slot 51 is the archived Computer Vision slot. When referenced on a scheduled class day,
    the backend must safely resolve to the active replacement rather than displaying an error.
    """
    cleanup_active_sessions()
    token = get_token("kavita_maam")
    headers = {"Authorization": f"Bearer {token}"}
    kavita = SessionLocal().query(User).filter(User.username == "kavita_maam").first()

    with patch("app.services.session_service.detector.decode_image_base64", return_value=np.ones((200, 200, 3), dtype=np.uint8)), \
         patch("app.services.session_service.detector.detect_faces", return_value=[(10, 10, 180, 180)]), \
         patch("app.services.session_service.detector.extract_and_normalize_face", return_value=np.ones((200, 200), dtype=np.uint8)), \
         patch("app.services.session_service.detector.evaluate_liveness", return_value=(True, 0.98, "Live face verified")), \
         patch("cv2.face.LBPHFaceRecognizer_create") as mock_rec_cls, \
         patch("cv2.matchTemplate", return_value=np.array([[0.85]])):

        mock_rec = mock_rec_cls.return_value
        mock_rec.predict.return_value = (kavita.id, 20.0)

        # Pass archived slot 51 on Monday 08:45 AM (when Period 1 active slot exists)
        res = client.post(
            "/api/sessions/authorized-start?date=2026-10-19&time=08:45",
            json={
                "timetable_entry_id": 51,
                "face_image": make_face_image()
            },
            headers=headers
        )
        assert res.status_code in (200, 201), f"Archived slot resolution failed: {res.text}"
        data = res.json()
        assert data["status"] == "active"
        assert data["subject"] == "Computer Vision"


def test_obsolete_slot_without_active_replacement_rejected():
    """An archived slot that has NO valid active replacement must be rejected with 400."""
    cleanup_active_sessions()
    token = get_token("kavita_maam")
    headers = {"Authorization": f"Bearer {token}"}

    # Query an inactive entry from another subject or nonexistent period
    db = SessionLocal()
    try:
        old_slot = db.query(TimetableEntry).filter(
            TimetableEntry.is_active == False,
            TimetableEntry.subject_id != 13 # Not Computer Vision
        ).first()
        assert old_slot is not None
        old_id = old_slot.id
    finally:
        db.close()

    res = client.post(
        "/api/sessions/authorized-start?date=2026-10-19&time=06:00",
        json={
            "timetable_entry_id": old_id,
            "face_image": make_face_image()
        },
        headers=headers
    )
    assert res.status_code in (400, 404)
    detail = res.json()["detail"].lower()
    assert "inactive" in detail or "archived" in detail or "obsolete" in detail or "not found" in detail


# ─── 5. Unauthorized Faculty Assignment Rejection ─────────────────────────────

def test_unauthorized_faculty_assignment_rejected():
    """Sumit Sir is not assigned to Kavita Ma'am's Computer Vision class -> 403 Forbidden."""
    cleanup_active_sessions()
    db = SessionLocal()
    try:
        cv_slot = db.query(TimetableEntry).filter(
            TimetableEntry.subject_id == 13,
            TimetableEntry.section == "A",
            TimetableEntry.day_of_week == 0,
            TimetableEntry.is_active == True
        ).first()
        assert cv_slot is not None
        slot_id = cv_slot.id
        sumit = db.query(User).filter(User.username == "sumit_sir").first()
        sumit_id = sumit.id
        db.query(SubstituteAuthorization).filter(
            SubstituteAuthorization.substitute_teacher_id == sumit_id
        ).delete()
        db.commit()
    finally:
        db.close()

    token = get_token("sumit_sir")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.session_service.detector.decode_image_base64", return_value=np.ones((200, 200, 3), dtype=np.uint8)), \
         patch("app.services.session_service.detector.detect_faces", return_value=[(10, 10, 180, 180)]), \
         patch("app.services.session_service.detector.extract_and_normalize_face", return_value=np.ones((200, 200), dtype=np.uint8)), \
         patch("app.services.session_service.detector.evaluate_liveness", return_value=(True, 0.98, "Live face verified")), \
         patch("cv2.face.LBPHFaceRecognizer_create") as mock_rec_cls, \
         patch("cv2.matchTemplate", return_value=np.array([[0.85]])):

        mock_rec = mock_rec_cls.return_value
        mock_rec.predict.return_value = (sumit_id, 20.0)

        res = client.post(
            "/api/sessions/authorized-start?date=2026-10-19&time=08:45",
            json={
                "timetable_entry_id": slot_id,
                "face_image": make_face_image()
            },
            headers=headers
        )
        assert res.status_code == 403
        detail = res.json()["detail"].lower()
        assert "unauthorized" in detail or "not assigned" in detail


# ─── 6. Substitute Authorization Starts Class Successfully ────────────────────

def test_substitute_authorization_allows_alternate_instructor():
    """Sumit Sir authorized as substitute for Kavita Ma'am on Computer Vision -> 201."""
    cleanup_active_sessions()
    db = SessionLocal()
    try:
        cv_slot = db.query(TimetableEntry).filter(
            TimetableEntry.subject_id == 13,
            TimetableEntry.section == "A",
            TimetableEntry.day_of_week == 0,
            TimetableEntry.is_active == True
        ).first()
        kavita = db.query(User).filter(User.username == "kavita_maam").first()
        sumit = db.query(User).filter(User.username == "sumit_sir").first()
        sub_date = date(2026, 10, 19)

        # Clear existing
        db.query(SubstituteAuthorization).filter(
            SubstituteAuthorization.timetable_entry_id == cv_slot.id,
            SubstituteAuthorization.date == sub_date
        ).delete()

        sub_auth = SubstituteAuthorization(
            timetable_entry_id=cv_slot.id,
            original_teacher_id=kavita.id,
            substitute_teacher_id=sumit.id,
            date=sub_date,
            reason="Faculty conference substitute",
            status="authorized"
        )
        db.add(sub_auth)
        db.commit()
        slot_id = cv_slot.id
        sumit_id = sumit.id
    finally:
        db.close()

    token = get_token("sumit_sir")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.session_service.detector.decode_image_base64", return_value=np.ones((200, 200, 3), dtype=np.uint8)), \
         patch("app.services.session_service.detector.detect_faces", return_value=[(10, 10, 180, 180)]), \
         patch("app.services.session_service.detector.extract_and_normalize_face", return_value=np.ones((200, 200), dtype=np.uint8)), \
         patch("app.services.session_service.detector.evaluate_liveness", return_value=(True, 0.98, "Live face verified")), \
         patch("cv2.face.LBPHFaceRecognizer_create") as mock_rec_cls, \
         patch("cv2.matchTemplate", return_value=np.array([[0.85]])):

        mock_rec = mock_rec_cls.return_value
        mock_rec.predict.return_value = (sumit_id, 20.0)

        res = client.post(
            "/api/sessions/authorized-start?date=2026-10-19&time=08:45",
            json={
                "timetable_entry_id": slot_id,
                "face_image": make_face_image()
            },
            headers=headers
        )
        assert res.status_code in (200, 201), f"Substitute start failed: {res.text}"
        data = res.json()
        assert data["status"] == "active"
        assert data["teacher_id"] == sumit_id


# ─── 7. Time Boundaries & Day Validation ──────────────────────────────────────

def test_time_outside_permitted_window_rejected():
    """Attempting to start class at 07:00 when scheduled for 08:40 -> 400 Bad Request."""
    cleanup_active_sessions()
    db = SessionLocal()
    try:
        slot = db.query(TimetableEntry).filter(
            TimetableEntry.subject_id == 13,
            TimetableEntry.section == "A",
            TimetableEntry.day_of_week == 0,
            TimetableEntry.is_active == True
        ).first()
        slot_id = slot.id
    finally:
        db.close()

    token = get_token("kavita_maam")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/api/sessions/authorized-start?date=2026-10-19&time=07:00",
        json={
            "timetable_entry_id": slot_id,
            "face_image": make_face_image()
        },
        headers=headers
    )
    assert res.status_code == 400
    detail = res.json()["detail"].lower()
    assert "time" in detail or "slot" in detail or "mismatch" in detail or "window" in detail


def test_scheduled_day_mismatch_rejected():
    """Attempting to start Monday class on Tuesday -> 400 Bad Request."""
    cleanup_active_sessions()
    db = SessionLocal()
    try:
        slot = db.query(TimetableEntry).filter(
            TimetableEntry.subject_id == 13,
            TimetableEntry.section == "A",
            TimetableEntry.day_of_week == 0,
            TimetableEntry.is_active == True
        ).first()
        slot_id = slot.id
    finally:
        db.close()

    token = get_token("kavita_maam")
    headers = {"Authorization": f"Bearer {token}"}

    # 2026-10-20 is a Tuesday (dow=1)
    res = client.post(
        "/api/sessions/authorized-start?date=2026-10-20&time=08:45",
        json={
            "timetable_entry_id": slot_id,
            "face_image": make_face_image()
        },
        headers=headers
    )
    assert res.status_code == 400
    detail = res.json()["detail"].lower()
    assert "day mismatch" in detail or "scheduled" in detail


# ─── 8. Active Slots Retrieval for Teachers and Admins ─────────────────────────

def test_assigned_slots_retrieval_active_only():
    token_teacher = get_token("kavita_maam")
    res_t = client.get(
        "/api/sessions/teacher/assigned-slots?date=2026-10-19",
        headers={"Authorization": f"Bearer {token_teacher}"}
    )
    assert res_t.status_code == 200
    teacher_slots = res_t.json()
    assert len(teacher_slots) > 0
    # Ensure no slot returned is inactive
    db = SessionLocal()
    try:
        for s in teacher_slots:
            entry = db.query(TimetableEntry).filter(TimetableEntry.id == s["timetable_entry_id"]).first()
            assert entry is not None
            assert entry.is_active is True
            assert entry.teacher_id == entry.teacher.id
    finally:
        db.close()

    # Admin visibility
    token_admin = get_token("admin", "Admin@1234") if client.post("/api/auth/login", json={"username": "admin", "password": "Admin@1234"}).status_code == 200 else get_token("admin", "admin123")
    res_a = client.get(
        "/api/sessions/teacher/assigned-slots?date=2026-10-19",
        headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert res_a.status_code == 200
    admin_slots = res_a.json()
    assert len(admin_slots) >= len(teacher_slots)
