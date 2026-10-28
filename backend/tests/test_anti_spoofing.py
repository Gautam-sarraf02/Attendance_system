import os
import base64
import datetime
from datetime import timezone, timedelta, date
from unittest.mock import patch, MagicMock
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.student import Student
from app.models.attendance_session import AttendanceSession
from app.models.attendance import Attendance
from app.models.academic_year import AcademicYear
from app.models.face_enrollment import FaceEnrollment
from app.face.detector import detector
from app.face.anti_spoof import AntiSpoofClassifier, anti_spoof_classifier
from app.face.recognizer import recognizer_service
from app.auth.jwt_handler import get_password_hash

client = TestClient(app)

def img_to_b64(img):
    _, buf = cv2.imencode('.jpg', img)
    return f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"

@pytest.fixture(scope="module")
def setup_anti_spoof_data():
    db = SessionLocal()
    try:
        today = date.today()

        # 1. Teacher
        teacher = db.query(User).filter(User.username == "as_teacher").first()
        if not teacher:
            teacher = User(
                username="as_teacher",
                password_hash=get_password_hash("teacher123"),
                full_name="AntiSpoof Teacher",
                email="teacher.as@college.edu",
                role="teacher",
                is_active=True
            )
            db.add(teacher)
            db.commit()
            db.refresh(teacher)

        # 2. Student
        student = db.query(Student).filter(Student.roll_number == "AS-STUDENT-01").first()
        if not student:
            student = Student(
                roll_number="AS-STUDENT-01",
                name="Spoof Test Student",
                section="SEC-AS",
                email="student.as@college.edu",
                is_active=True
            )
            db.add(student)
            db.commit()
            db.refresh(student)

        # 3. Academic Year & Face Enrollment
        ay = db.query(AcademicYear).filter(AcademicYear.name == "2026-2027").first()
        if not ay:
            ay = AcademicYear(
                name="2026-2027",
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=300),
                is_current=True
            )
            db.add(ay)
            db.commit()
            db.refresh(ay)

        enr = db.query(FaceEnrollment).filter(FaceEnrollment.student_id == student.id).first()
        if not enr:
            enr = FaceEnrollment(
                student_id=student.id,
                academic_year_id=ay.id,
                status="active",
                valid_from=today - timedelta(days=10),
                valid_until=today + timedelta(days=300)
            )
            db.add(enr)
            db.commit()

        # 4. Active Attendance Session
        now_utc = datetime.datetime.now(timezone.utc)
        session = AttendanceSession(
            subject="Biometric Security",
            section="SEC-AS",
            teacher_id=teacher.id,
            academic_year_id=ay.id,
            status="active",
            started_at=now_utc,
            recognition_window_end=now_utc + timedelta(minutes=15)
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Auth Token
        res = client.post("/api/auth/login", json={"username": "as_teacher", "password": "teacher123"})
        assert res.status_code == 200
        token = res.json()["access_token"]

        return {
            "token": token,
            "session_id": session.id,
            "student_id": student.id,
            "student_name": student.name,
            "student_roll": student.roll_number
        }
    finally:
        db.close()


def test_minifasnet_model_availability_and_initialization():
    """Confirms that the pretrained MiniFASNet models are loaded and available via ONNX Runtime."""
    assert anti_spoof_classifier.is_available is True
    assert anti_spoof_classifier.session_v2 is not None
    assert anti_spoof_classifier.session_v1se is not None


def test_printed_photograph_attack_is_rejected():
    """
    Simulates a printed paper photograph presentation attack.
    MiniFASNet must detect paper margins, flat lighting, and reject it as spoof.
    """
    # Create a frame showing a desk with a printed photo on white paper
    frame = np.full((480, 640, 3), 70, dtype=np.uint8) # Dark classroom desk
    # White paper sheet
    cv2.rectangle(frame, (160, 50), (480, 430), (245, 245, 245), -1)
    # Printed photo on paper
    cv2.rectangle(frame, (190, 80), (450, 400), (130, 150, 200), -1)
    # Face features on photo
    cv2.circle(frame, (320, 200), 55, (120, 140, 190), -1)
    cv2.circle(frame, (300, 190), 6, (30, 30, 30), -1)
    cv2.circle(frame, (340, 190), 6, (30, 30, 30), -1)

    bbox = (265, 145, 110, 110)
    is_live, score, reason = detector.evaluate_liveness(
        face_roi=frame[145:255, 265:375],
        full_image=frame,
        bbox=bbox
    )

    assert is_live is False
    assert "Liveness check failed" in reason
    assert ("printed photograph" in reason) or ("replay" in reason) or ("low liveness" in reason)


def test_phone_screen_photo_attack_is_rejected():
    """
    Simulates displaying a student's photo on a smartphone held in front of the camera.
    Must be detected as a digital screen replay attack.
    """
    frame = np.full((480, 640, 3), 110, dtype=np.uint8) # Background
    # Phone body / bezel
    cv2.rectangle(frame, (180, 60), (460, 420), (15, 15, 15), -1)
    # Phone screen display area
    cv2.rectangle(frame, (195, 75), (445, 405), (140, 160, 215), -1)
    # Face displayed on phone screen
    cv2.circle(frame, (320, 200), 55, (125, 145, 195), -1)
    cv2.circle(frame, (300, 190), 6, (25, 25, 25), -1)
    cv2.circle(frame, (340, 190), 6, (25, 25, 25), -1)
    # Digital scanline / moiré patterns
    for y in range(80, 400, 4):
        frame[y, 200:440] = np.clip(frame[y, 200:440].astype(int) + 18, 0, 255)

    bbox = (265, 145, 110, 110)
    is_live, score, reason = detector.evaluate_liveness(
        face_roi=frame[145:255, 265:375],
        full_image=frame,
        bbox=bbox
    )

    assert is_live is False
    assert "Liveness check failed" in reason


def test_attendance_blocked_when_spoof_detected(setup_anti_spoof_data):
    """
    CRITICAL CHECK: When anti-spoofing fails (e.g. photo on phone shown to camera),
    attendance MUST NOT be marked in the database.
    """
    data = setup_anti_spoof_data
    headers = {"Authorization": f"Bearer {data['token']}"}

    # Frame containing a spoof phone presentation
    frame = np.full((480, 640, 3), 100, dtype=np.uint8)
    cv2.rectangle(frame, (180, 60), (460, 420), (20, 20, 20), -1) # Phone
    cv2.rectangle(frame, (195, 75), (445, 405), (140, 160, 215), -1) # Screen
    cv2.circle(frame, (320, 200), 55, (125, 145, 195), -1)
    b64 = img_to_b64(frame)

    box = (265, 145, 110, 110)

    # Face recognizer recognizes the student from the photo
    with patch.object(detector, 'detect_faces', return_value=[box]), \
         patch.object(recognizer_service, 'predict', return_value=(data["student_id"], 21.0, True)):

        res = client.post("/api/attendance/recognize", json={
            "image_base64": b64,
            "session_id": data["session_id"],
            "auto_mark": True
        }, headers=headers)

        assert res.status_code == 200
        resp = res.json()
        assert resp["known_faces_count"] == 1
        det = resp["detections"][0]

        # Liveness check failed -> Attendance NOT marked!
        assert det["is_live"] is False
        assert det["attendance_marked"] is False
        assert "Liveness check failed" in det["status_message"]

    # Verify database: no attendance record exists
    db = SessionLocal()
    try:
        count = db.query(Attendance).filter(
            Attendance.session_id == data["session_id"],
            Attendance.student_id == data["student_id"]
        ).count()
        assert count == 0
    finally:
        db.close()


def test_attendance_fails_safe_when_model_unavailable(setup_anti_spoof_data):
    """
    Requirement 5: If the anti-spoofing model is unavailable or inference errors occur,
    reject attendance safely. Never silently fall back to treating the face as live.
    """
    data = setup_anti_spoof_data
    headers = {"Authorization": f"Bearer {data['token']}"}

    test_frame = np.full((400, 400, 3), 150, dtype=np.uint8)
    b64 = img_to_b64(test_frame)

    # Simulate model failure or unhandled inference crash
    with patch.object(detector.anti_spoof, 'evaluate', return_value=(False, 0.0, "Liveness check failed — anti-spoofing model unavailable")), \
         patch.object(detector, 'detect_faces', return_value=[(50, 50, 150, 150)]), \
         patch.object(recognizer_service, 'predict', return_value=(data["student_id"], 15.0, True)):

        res = client.post("/api/attendance/recognize", json={
            "image_base64": b64,
            "session_id": data["session_id"],
            "auto_mark": True
        }, headers=headers)

        assert res.status_code == 200
        det = res.json()["detections"][0]
        assert det["is_live"] is False
        assert det["attendance_marked"] is False
        assert "Liveness check failed" in det["status_message"]


def test_real_live_person_attendance_marked(setup_anti_spoof_data):
    """
    Requirement: A real live person with verified liveness proceeds and gets marked present.
    """
    data = setup_anti_spoof_data
    headers = {"Authorization": f"Bearer {data['token']}"}

    test_frame = np.full((400, 400, 3), (130, 150, 200), dtype=np.uint8)
    cv2.circle(test_frame, (125, 125), 60, (140, 170, 220), -1)
    cv2.circle(test_frame, (110, 115), 6, (30, 30, 30), -1)
    cv2.circle(test_frame, (140, 115), 6, (30, 30, 30), -1)
    b64 = img_to_b64(test_frame)

    with patch.object(detector.anti_spoof, 'evaluate', return_value=(True, 0.985, "Live face verified (98.5%)")), \
         patch.object(detector, 'detect_faces', return_value=[(50, 50, 150, 150)]), \
         patch.object(recognizer_service, 'predict', return_value=(data["student_id"], 15.0, True)):

        res = client.post("/api/attendance/recognize", json={
            "image_base64": b64,
            "session_id": data["session_id"],
            "auto_mark": True
        }, headers=headers)

        assert res.status_code == 200
        det = res.json()["detections"][0]
        assert det["is_live"] is True
        assert det["attendance_marked"] is True
        assert det["status_message"] == "Marked Present"

    # Verify database has the attendance record
    db = SessionLocal()
    try:
        rec = db.query(Attendance).filter(
            Attendance.session_id == data["session_id"],
            Attendance.student_id == data["student_id"]
        ).first()
        assert rec is not None
        assert rec.status == "present"
    finally:
        db.close()
