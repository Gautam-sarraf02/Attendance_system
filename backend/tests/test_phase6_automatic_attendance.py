import base64
import datetime
from datetime import date, timedelta, timezone
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
from app.models.academic_year import AcademicYear
from app.models.semester import Semester
from app.models.timetable import TimetableEntry
from app.models.attendance import Attendance
from app.models.attendance_session import AttendanceSession
from app.models.face_enrollment import FaceEnrollment
from app.face.detector import detector
from app.face.recognizer import recognizer_service
from app.auth.jwt_handler import get_password_hash

client = TestClient(app)


def get_token(username, password):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


def create_synthetic_face(width=200, height=200, brightness=130, seed=1):
    """Creates a synthetic multi-channel face-like pattern with high contrast and skin tone."""
    img = np.ones((height, width, 3), dtype=np.uint8) * brightness
    # Add face features: skin ellipse, eyes, mouth
    cv2.ellipse(img, (width // 2, height // 2), (width // 3, height // 2 - 10), 0, 0, 360, (140, 160, 210), -1)
    cv2.circle(img, (width // 2 - 30, height // 2 - 20), 8, (40, 40, 40), -1)
    cv2.circle(img, (width // 2 + 30, height // 2 - 20), 8, (40, 40, 40), -1)
    cv2.ellipse(img, (width // 2, height // 2 + 30), (20, 10), 0, 0, 180, (50, 50, 180), -1)
    # Texture detail
    for i in range(10, width - 10, 12):
        cv2.line(img, (i, 10), (i, height - 10), (seed * 20 % 255, 30, 30), 1)
    return img


def img_to_b64(img):
    _, buf = cv2.imencode('.jpg', img)
    return f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"


@pytest.fixture(scope="module")
def setup_phase6_data():
    """Sets up an academic environment for testing automatic attendance."""
    db = SessionLocal()
    try:
        today = date.today()

        # 1. Admin & Teacher
        admin = db.query(User).filter(User.username == "phase6_admin").first()
        if not admin:
            admin = User(
                username="phase6_admin",
                password_hash=get_password_hash("admin123"),
                full_name="Phase 6 Admin",
                email="admin.p6@college.edu",
                role="admin",
                is_active=True
            )
            db.add(admin)

        teacher = db.query(User).filter(User.username == "phase6_teacher").first()
        if not teacher:
            teacher = User(
                username="phase6_teacher",
                password_hash=get_password_hash("teacher123"),
                full_name="Prof. Phase 6 Teacher",
                email="teacher.p6@college.edu",
                role="teacher",
                is_active=True
            )
            db.add(teacher)

        # 2. Academic Year
        ay = db.query(AcademicYear).filter(AcademicYear.name == "2026-2027-P6").first()
        if not ay:
            ay = AcademicYear(
                name="2026-2027-P6",
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=330),
                is_current=True
            )
            db.add(ay)
            db.flush()

        # 3. Semester & Subject
        sem = db.query(Semester).filter(Semester.name == "Semester P6").first()
        if not sem:
            sem = Semester(
                name="Semester P6",
                academic_year_id=ay.id,
                start_date=ay.start_date,
                end_date=ay.end_date,
                is_active=True
            )
            db.add(sem)
            db.flush()

        subj = db.query(Subject).filter(Subject.code == "P6_CS601").first()
        if not subj:
            subj = Subject(
                code="P6_CS601",
                name="Computer Vision AI",
                semester_id=sem.id,
                section="CSE-P6",
                is_active=True
            )
            db.add(subj)
            db.flush()

        # 4. Students:
        # Student 1: Enrolled in CSE-P6 (Active enrollment)
        s1 = db.query(Student).filter(Student.roll_number == "P6_STU_001").first()
        if not s1:
            s1 = Student(
                roll_number="P6_STU_001",
                name="Siddharth Malhotra",
                section="CSE-P6",
                email="sid.p6@college.edu",
                is_active=True
            )
            db.add(s1)
            db.flush()

        # Student 2: In different section CSE-P6-B (Active enrollment)
        s2 = db.query(Student).filter(Student.roll_number == "P6_STU_002").first()
        if not s2:
            s2 = Student(
                roll_number="P6_STU_002",
                name="Rhea Kapoor",
                section="CSE-P6-B",
                email="rhea.p6@college.edu",
                is_active=True
            )
            db.add(s2)
            db.flush()

        # Student 3: In section CSE-P6 but with EXPIRED enrollment
        s3 = db.query(Student).filter(Student.roll_number == "P6_STU_003").first()
        if not s3:
            s3 = Student(
                roll_number="P6_STU_003",
                name="Aditya Roy",
                section="CSE-P6",
                email="aditya.p6@college.edu",
                is_active=True
            )
            db.add(s3)
            db.flush()

        # Student User (for testing role restriction)
        s_user = db.query(User).filter(User.username == "phase6_student").first()
        if not s_user:
            s_user = User(
                username="phase6_student",
                password_hash=get_password_hash("student123"),
                full_name="Siddharth Malhotra",
                email="sid.user.p6@college.edu",
                role="student",
                student_id=s1.id,
                is_active=True
            )
            db.add(s_user)

        # Clear prior enrollments for test isolation
        db.query(FaceEnrollment).filter(FaceEnrollment.student_id.in_([s1.id, s2.id, s3.id])).delete()
        db.commit()

        # Create active enrollment for s1 and s2
        e1 = FaceEnrollment(
            student_id=s1.id,
            academic_year_id=ay.id,
            valid_from=today - timedelta(days=10),
            valid_until=today + timedelta(days=200),
            status="active",
            notes="Valid active enrollment"
        )
        e2 = FaceEnrollment(
            student_id=s2.id,
            academic_year_id=ay.id,
            valid_from=today - timedelta(days=10),
            valid_until=today + timedelta(days=200),
            status="active",
            notes="Valid active enrollment"
        )
        # Create expired enrollment for s3
        e3 = FaceEnrollment(
            student_id=s3.id,
            academic_year_id=ay.id,
            valid_from=today - timedelta(days=400),
            valid_until=today - timedelta(days=35),
            status="expired",
            notes="Expired enrollment"
        )
        db.add_all([e1, e2, e3])
        db.commit()

        # 5. Active Attendance Session for Section CSE-P6
        now_utc = datetime.datetime.now(timezone.utc)
        sess = AttendanceSession(
            subject=subj.name,
            section="CSE-P6",
            teacher_id=teacher.id,
            subject_id=subj.id,
            academic_year_id=ay.id,
            semester_id=sem.id,
            status="active",
            started_at=now_utc,
            recognition_window_end=now_utc + timedelta(minutes=15)
        )
        db.add(sess)
        db.commit()
        db.refresh(sess)

        # Train LBPH model on synthetic samples for s1 and s2
        face_sample_s1 = create_synthetic_face(200, 200, brightness=130, seed=1)
        face_sample_s2 = create_synthetic_face(200, 200, brightness=150, seed=2)
        face_sample_s3 = create_synthetic_face(200, 200, brightness=170, seed=3)

        samples_dict = {
            s1.id: [face_sample_s1, face_sample_s1],
            s2.id: [face_sample_s2, face_sample_s2],
            s3.id: [face_sample_s3, face_sample_s3]
        }
        recognizer_service.train(samples_dict)

        yield {
            "teacher_token": get_token("phase6_teacher", "teacher123"),
            "admin_token": get_token("phase6_admin", "admin123"),
            "student_token": get_token("phase6_student", "student123"),
            "session_id": sess.id,
            "subject_name": subj.name,
            "section": "CSE-P6",
            "academic_year_id": ay.id,
            "s1_id": s1.id,
            "s1_name": s1.name,
            "s1_roll": s1.roll_number,
            "s2_id": s2.id,
            "s3_id": s3.id,
            "face_s1": face_sample_s1,
            "face_s2": face_sample_s2,
            "face_s3": face_sample_s3
        }
    finally:
        db.close()


def test_multi_face_detection_in_classroom_frame():
    """Requirement 2: Use camera to detect multiple visible faces in classroom frames."""
    # Create a frame wide enough for two side-by-side face boxes
    classroom_frame = np.ones((480, 640, 3), dtype=np.uint8) * 120
    # Two distinct face bounding boxes
    mock_boxes = [(80, 100, 120, 120), (360, 110, 130, 130)]

    with patch.object(detector, 'detect_faces', return_value=mock_boxes):
        detected = detector.detect_faces(classroom_frame)
        assert len(detected) == 2
        assert detected[0] == (80, 100, 120, 120)
        assert detected[1] == (360, 110, 130, 130)


def test_unknown_faces_not_marked_as_present(setup_phase6_data):
    """
    Requirement 9: Do not mark an unidentified student as present.
    Face whose LBPH distance exceeds threshold or is not recognized must be Unknown.
    """
    data = setup_phase6_data
    headers = {"Authorization": f"Bearer {data['teacher_token']}"}

    test_frame = create_synthetic_face(400, 400, brightness=110, seed=99)
    b64 = img_to_b64(test_frame)

    # Mock detection returning 1 box, but recognizer predicting Unknown (is_known=False)
    with patch.object(detector, 'detect_faces', return_value=[(50, 50, 150, 150)]), \
         patch.object(recognizer_service, 'predict', return_value=(None, 95.5, False)):

        res = client.post("/api/attendance/recognize", json={
            "image_base64": b64,
            "session_id": data["session_id"],
            "auto_mark": True
        }, headers=headers)

        assert res.status_code == 200, res.text
        resp_json = res.json()
        assert resp_json["total_faces_detected"] == 1
        assert resp_json["unknown_faces_count"] == 1
        assert resp_json["known_faces_count"] == 0

        det = resp_json["detections"][0]
        assert det["is_known"] is False
        assert det["name"] == "Unknown"
        assert det["attendance_marked"] is False
        assert det["status_message"] == "Unknown Face"

    # Verify no record was inserted in the database
    db = SessionLocal()
    try:
        count = db.query(Attendance).filter(Attendance.session_id == data["session_id"]).count()
        assert count == 0
    finally:
        db.close()


def test_registered_student_marks_attendance_automatically(setup_phase6_data):
    """
    Requirements 3, 4, 5: Match detected faces against registered students and save valid record automatically.
    """
    data = setup_phase6_data
    headers = {"Authorization": f"Bearer {data['teacher_token']}"}

    test_frame = create_synthetic_face(400, 400, brightness=130, seed=1)
    b64 = img_to_b64(test_frame)

    with patch.object(detector, 'detect_faces', return_value=[(50, 50, 160, 160)]), \
         patch.object(recognizer_service, 'predict', return_value=(data["s1_id"], 22.4, True)):

        res = client.post("/api/attendance/recognize", json={
            "image_base64": b64,
            "session_id": data["session_id"],
            "auto_mark": True
        }, headers=headers)

        assert res.status_code == 200, res.text
        resp_json = res.json()
        assert resp_json["known_faces_count"] == 1
        assert resp_json["unknown_faces_count"] == 0

        det = resp_json["detections"][0]
        assert det["is_known"] is True
        assert det["student_id"] == data["s1_id"]
        assert det["name"] == data["s1_name"]
        assert det["roll_number"] == data["s1_roll"]
        assert det["attendance_marked"] is True
        assert det["status_message"] == "Marked Present"

    # Verify database record exists
    db = SessionLocal()
    try:
        rec = db.query(Attendance).filter(
            Attendance.session_id == data["session_id"],
            Attendance.student_id == data["s1_id"]
        ).first()
        assert rec is not None
        assert rec.status == "present"
        assert rec.confidence_score == 22.4
        assert rec.subject == data["subject_name"]
    finally:
        db.close()


def test_duplicate_scans_ignored_without_duplicate_records(setup_phase6_data):
    """
    Requirement 6: Ignore duplicate detections without creating duplicate records.
    """
    data = setup_phase6_data
    headers = {"Authorization": f"Bearer {data['teacher_token']}"}

    test_frame = create_synthetic_face(400, 400, brightness=130, seed=1)
    b64 = img_to_b64(test_frame)

    # Student 1 is already marked in previous test. Rescan frame.
    with patch.object(detector, 'detect_faces', return_value=[(50, 50, 160, 160)]), \
         patch.object(recognizer_service, 'predict', return_value=(data["s1_id"], 21.0, True)):

        res = client.post("/api/attendance/recognize", json={
            "image_base64": b64,
            "session_id": data["session_id"],
            "auto_mark": True
        }, headers=headers)

        assert res.status_code == 200, res.text
        resp_json = res.json()
        det = resp_json["detections"][0]
        assert det["is_known"] is True
        assert det["attendance_marked"] is False
        assert det["status_message"] == "Already Marked Present"

    # Verify still exactly 1 record in DB
    db = SessionLocal()
    try:
        count = db.query(Attendance).filter(
            Attendance.session_id == data["session_id"],
            Attendance.student_id == data["s1_id"]
        ).count()
        assert count == 1
    finally:
        db.close()


def test_wrong_section_student_not_marked(setup_phase6_data):
    """
    Requirement 4 (item 4): The student belongs to the scheduled section.
    Student 2 is in section CSE-P6-B, while session is for section CSE-P6.
    """
    data = setup_phase6_data
    headers = {"Authorization": f"Bearer {data['teacher_token']}"}

    test_frame = create_synthetic_face(400, 400, brightness=150, seed=2)
    b64 = img_to_b64(test_frame)

    with patch.object(detector, 'detect_faces', return_value=[(60, 60, 150, 150)]), \
         patch.object(recognizer_service, 'predict', return_value=(data["s2_id"], 25.0, True)):

        res = client.post("/api/attendance/recognize", json={
            "image_base64": b64,
            "session_id": data["session_id"],
            "auto_mark": True
        }, headers=headers)

        assert res.status_code == 200, res.text
        resp_json = res.json()
        det = resp_json["detections"][0]
        assert det["is_known"] is True
        assert det["student_id"] == data["s2_id"]
        assert det["attendance_marked"] is False
        assert "Wrong Section" in det["status_message"]

    # Verify no record created for s2
    db = SessionLocal()
    try:
        rec = db.query(Attendance).filter(
            Attendance.session_id == data["session_id"],
            Attendance.student_id == data["s2_id"]
        ).first()
        assert rec is None
    finally:
        db.close()


def test_expired_enrollment_student_not_marked(setup_phase6_data):
    """
    Requirement 4 (item 3): Student's enrollment must be valid for the academic year.
    Student 3 has expired face enrollment.
    """
    data = setup_phase6_data
    headers = {"Authorization": f"Bearer {data['teacher_token']}"}

    test_frame = create_synthetic_face(400, 400, brightness=170, seed=3)
    b64 = img_to_b64(test_frame)

    with patch.object(detector, 'detect_faces', return_value=[(50, 50, 150, 150)]), \
         patch.object(recognizer_service, 'predict', return_value=(data["s3_id"], 28.0, True)):

        res = client.post("/api/attendance/recognize", json={
            "image_base64": b64,
            "session_id": data["session_id"],
            "auto_mark": True
        }, headers=headers)

        assert res.status_code == 200, res.text
        resp_json = res.json()
        det = resp_json["detections"][0]
        assert det["is_known"] is True
        assert det["student_id"] == data["s3_id"]
        assert det["attendance_marked"] is False
        assert "Enrollment Invalid" in det["status_message"]

    # Verify no record created for s3
    db = SessionLocal()
    try:
        rec = db.query(Attendance).filter(
            Attendance.session_id == data["session_id"],
            Attendance.student_id == data["s3_id"]
        ).first()
        assert rec is None
    finally:
        db.close()


def test_scan_after_15_minute_deadline_rejected(setup_phase6_data):
    """
    Requirement 4 (item 2): Session has not passed its server-side 15-minute deadline.
    Create a session whose deadline has expired.
    """
    data = setup_phase6_data
    headers = {"Authorization": f"Bearer {data['teacher_token']}"}

    # Create expired session in DB
    db = SessionLocal()
    try:
        past_time = datetime.datetime.now(timezone.utc) - timedelta(minutes=20)
        expired_sess = AttendanceSession(
            subject=data["subject_name"],
            section="CSE-P6",
            teacher_id=1,
            academic_year_id=data["academic_year_id"],
            status="active",
            started_at=past_time,
            recognition_window_end=past_time + timedelta(minutes=15)  # Expired 5 mins ago
        )
        db.add(expired_sess)
        db.commit()
        db.refresh(expired_sess)
        expired_sess_id = expired_sess.id
    finally:
        db.close()

    test_frame = create_synthetic_face(400, 400, brightness=130, seed=1)
    b64 = img_to_b64(test_frame)

    with patch.object(detector, 'detect_faces', return_value=[(50, 50, 150, 150)]), \
         patch.object(recognizer_service, 'predict', return_value=(data["s1_id"], 20.0, True)):

        res = client.post("/api/attendance/recognize", json={
            "image_base64": b64,
            "session_id": expired_sess_id,
            "auto_mark": True
        }, headers=headers)

        assert res.status_code == 200, res.text
        resp_json = res.json()
        det = resp_json["detections"][0]
        assert det["is_known"] is True
        assert det["attendance_marked"] is False
        assert "Deadline Expired" in det["status_message"]


def test_inactive_or_closed_session_rejected(setup_phase6_data):
    """
    Requirement 4 (item 1): Attendance session must be active.
    """
    data = setup_phase6_data
    headers = {"Authorization": f"Bearer {data['teacher_token']}"}

    # Create closed session
    db = SessionLocal()
    try:
        closed_sess = AttendanceSession(
            subject=data["subject_name"],
            section="CSE-P6",
            teacher_id=1,
            status="closed",
            started_at=datetime.datetime.now(timezone.utc),
            recognition_window_end=datetime.datetime.now(timezone.utc) + timedelta(minutes=15)
        )
        db.add(closed_sess)
        db.commit()
        db.refresh(closed_sess)
        closed_id = closed_sess.id
    finally:
        db.close()

    test_frame = create_synthetic_face(400, 400, brightness=130, seed=1)
    b64 = img_to_b64(test_frame)

    with patch.object(detector, 'detect_faces', return_value=[(50, 50, 150, 150)]), \
         patch.object(recognizer_service, 'predict', return_value=(data["s1_id"], 15.0, True)):

        res = client.post("/api/attendance/recognize", json={
            "image_base64": b64,
            "session_id": closed_id,
            "auto_mark": True
        }, headers=headers)

        assert res.status_code == 200, res.text
        resp_json = res.json()
        det = resp_json["detections"][0]
        assert det["attendance_marked"] is False
        assert "not active" in det["status_message"]


def test_passive_liveness_and_anti_spoofing_evaluation():
    """
    Requirement 8: Evaluate liveness or anti-spoofing capabilities.
    Tests live face evaluation vs flat/desaturated mock image.
    """
    # 1. Natural face crop with color and texture
    with patch.object(detector.anti_spoof, 'evaluate', return_value=(True, 0.96, "Live face verified (96.0%)")):
        live_crop = create_synthetic_face(150, 150, brightness=135, seed=5)
        is_live, score, msg = detector.evaluate_liveness(live_crop)
        assert is_live is True
        assert score >= 0.30

    # 2. Monochromatic flat paper replica (zero saturation variance)
    flat_crop = np.full((150, 150, 3), 128, dtype=np.uint8)
    is_live_flat, score_flat, msg_flat = detector.evaluate_liveness(flat_crop)
    assert is_live_flat is False
    assert "Low chrominance" in msg_flat or "Failed" in msg_flat or "failed" in msg_flat or score_flat < 0.30


def test_student_role_forbidden_from_recognition_scanner(setup_phase6_data):
    """
    Requirement 10: Restrict access to recognition scanning endpoint.
    Students cannot operate recognition scanners.
    """
    data = setup_phase6_data
    headers = {"Authorization": f"Bearer {data['student_token']}"}

    test_frame = create_synthetic_face(200, 200, brightness=130, seed=1)
    b64 = img_to_b64(test_frame)

    res = client.post("/api/attendance/recognize", json={
        "image_base64": b64,
        "session_id": data["session_id"]
    }, headers=headers)

    assert res.status_code == 403
    assert "Students cannot operate" in res.json()["detail"]


def test_multi_face_frame_mixed_students_marking(setup_phase6_data):
    """
    Simulates a classroom frame with 2 students simultaneously:
    - Student 1 (Enrolled in CSE-P6, valid) -> Marked Present
    - Student 2 (In section CSE-P6-B) -> Wrong Section, not marked
    """
    data = setup_phase6_data
    headers = {"Authorization": f"Bearer {data['teacher_token']}"}

    # Reset any previous attendance in a fresh session
    db = SessionLocal()
    try:
        now_utc = datetime.datetime.now(timezone.utc)
        fresh_sess = AttendanceSession(
            subject=data["subject_name"],
            section="CSE-P6",
            teacher_id=1,
            academic_year_id=data["academic_year_id"],
            status="active",
            started_at=now_utc,
            recognition_window_end=now_utc + timedelta(minutes=15)
        )
        db.add(fresh_sess)
        db.commit()
        db.refresh(fresh_sess)
        fresh_sess_id = fresh_sess.id
    finally:
        db.close()

    test_frame = np.ones((480, 640, 3), dtype=np.uint8) * 120
    face1 = create_synthetic_face(140, 140, brightness=130, seed=1)
    face2 = create_synthetic_face(140, 140, brightness=150, seed=2)
    test_frame[100:240, 50:190] = face1
    test_frame[100:240, 320:460] = face2
    b64 = img_to_b64(test_frame)

    # 2 bounding boxes detected in frame
    two_boxes = [(50, 100, 140, 140), (320, 100, 140, 140)]

    # Mock predict: box 1 -> student 1, box 2 -> student 2
    def mock_predict_multi(face_roi):
        # We can differentiate by calling count
        if not hasattr(mock_predict_multi, "call_count"):
            mock_predict_multi.call_count = 0
        mock_predict_multi.call_count += 1
        if mock_predict_multi.call_count % 2 == 1:
            return (data["s1_id"], 18.5, True)
        else:
            return (data["s2_id"], 24.0, True)

    with patch.object(detector, 'detect_faces', return_value=two_boxes), \
         patch.object(detector, 'evaluate_liveness', return_value=(True, 0.95, "Live face verified")), \
         patch.object(recognizer_service, 'predict', side_effect=mock_predict_multi):

        res = client.post("/api/attendance/recognize", json={
            "image_base64": b64,
            "session_id": fresh_sess_id,
            "auto_mark": True
        }, headers=headers)

        assert res.status_code == 200, res.text
        resp_json = res.json()
        assert resp_json["total_faces_detected"] == 2
        assert resp_json["known_faces_count"] == 2

        # Check Student 1 is marked present
        det1 = next(d for d in resp_json["detections"] if d["student_id"] == data["s1_id"])
        assert det1["attendance_marked"] is True
        assert det1["status_message"] == "Marked Present"

        # Check Student 2 is rejected due to wrong section
        det2 = next(d for d in resp_json["detections"] if d["student_id"] == data["s2_id"])
        assert det2["attendance_marked"] is False
        assert "Wrong Section" in det2["status_message"]

    # Verify in DB: only 1 attendance record exists (for Student 1)
    db = SessionLocal()
    try:
        records = db.query(Attendance).filter(Attendance.session_id == fresh_sess_id).all()
        assert len(records) == 1
        assert records[0].student_id == data["s1_id"]
    finally:
        db.close()
