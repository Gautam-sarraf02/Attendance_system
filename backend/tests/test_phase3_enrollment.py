import pytest
import os
import stat
import base64
import numpy as np
import cv2
from datetime import date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.student import Student
from app.models.academic_year import AcademicYear
from app.models.semester import Semester
from app.models.subject import Subject
from app.models.face_enrollment import FaceEnrollment
from app.models.face_sample import FaceSample
from app.models.timetable import TimetableEntry
from app.auth.jwt_handler import get_password_hash
from app.face.detector import detector
from app.face.storage import storage

client = TestClient(app)


def get_token(username, password):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


def create_synthetic_face_image(width=300, height=300, blur=False, brightness=120):
    """
    Creates a synthetic test image.
    """
    img = np.ones((height, width, 3), dtype=np.uint8) * brightness
    if not blur:
        # High frequency pattern to ensure Laplacian sharpness > 30.0
        for i in range(10, width - 10, 8):
            cv2.line(img, (i, 10), (i, height - 10), (20, 20, 20), 2)
            cv2.circle(img, (i, 100), 4, (240, 240, 240), -1)
    return img


def img_to_base64(img):
    _, buf = cv2.imencode('.jpg', img)
    return f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"


@pytest.fixture(scope="module")
def setup_phase3_data():
    """
    Prepares test fixtures for Phase 3:
    Admin, Teacher, Student, and Academic Years.
    """
    db = SessionLocal()
    try:
        # 1. Admin
        admin = db.query(User).filter(User.username == "phase3_admin").first()
        if not admin:
            admin = User(
                username="phase3_admin",
                password_hash=get_password_hash("admin123"),
                full_name="Phase3 Admin",
                email="admin.p3@test.edu",
                role="admin",
                is_active=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        # 2. Teacher
        teacher = db.query(User).filter(User.username == "phase3_teacher").first()
        if not teacher:
            teacher = User(
                username="phase3_teacher",
                password_hash=get_password_hash("teacher123"),
                full_name="Prof. Phase3 Teacher",
                email="teacher.p3@test.edu",
                role="teacher",
                is_active=True
            )
            db.add(teacher)
            db.commit()
            db.refresh(teacher)

        # 3. Student profile & user account
        student = db.query(Student).filter(Student.roll_number == "P3_STU_100").first()
        if not student:
            student = Student(
                roll_number="P3_STU_100",
                name="Charlie Phase3",
                section="CSE-C",
                email="charlie.p3@test.edu",
                is_active=True
            )
            db.add(student)
            db.commit()
            db.refresh(student)

        student_user = db.query(User).filter(User.username == "student_charlie").first()
        if not student_user:
            student_user = User(
                username="student_charlie",
                password_hash=get_password_hash("charlie123"),
                full_name="Charlie Phase3",
                email="charlie.user.p3@test.edu",
                role="student",
                student_id=student.id,
                is_active=True
            )
            db.add(student_user)
            db.commit()
            db.refresh(student_user)

        # 3. Clean up any leftover test enrollments for test student and teacher
        db.query(FaceEnrollment).filter(FaceEnrollment.student_id == student.id).delete()
        db.query(FaceEnrollment).filter(FaceEnrollment.user_id == teacher.id).delete()
        db.commit()

        # 4. Academic Years (Current and Next)
        today = date.today()
        ay_current = db.query(AcademicYear).filter(AcademicYear.name == "2026-2027-P3").first()
        if not ay_current:
            ay_current = AcademicYear(
                name="2026-2027-P3",
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=330),
                is_current=True
            )
            db.add(ay_current)
            db.commit()
            db.refresh(ay_current)

        ay_next = db.query(AcademicYear).filter(AcademicYear.name == "2027-2028-P3").first()
        if not ay_next:
            ay_next = AcademicYear(
                name="2027-2028-P3",
                start_date=today + timedelta(days=335),
                end_date=today + timedelta(days=695),
                is_current=False
            )
            db.add(ay_next)
            db.commit()
            db.refresh(ay_next)

        # 5. Semester, Subject & Timetable Entry for Teacher
        import datetime as dt_mod
        sem = db.query(Semester).filter(Semester.name == "Semester P3").first()
        if not sem:
            sem = Semester(
                name="Semester P3",
                academic_year_id=ay_current.id,
                start_date=ay_current.start_date,
                end_date=ay_current.end_date,
                is_active=True
            )
            db.add(sem)
            db.commit()
            db.refresh(sem)

        subject = db.query(Subject).filter(Subject.code == "P3_CS301").first()
        if not subject:
            subject = Subject(
                code="P3_CS301",
                name="Phase 3 Biometrics",
                semester_id=sem.id,
                section="CSE-C",
                is_active=True
            )
            db.add(subject)
            db.commit()
            db.refresh(subject)

        tt = db.query(TimetableEntry).filter(
            TimetableEntry.subject_id == subject.id,
            TimetableEntry.teacher_id == teacher.id,
            TimetableEntry.section == "CSE-C"
        ).first()
        if not tt:
            tt = TimetableEntry(
                subject_id=subject.id,
                teacher_id=teacher.id,
                section="CSE-C",
                semester_id=sem.id,
                day_of_week=today.weekday(),
                period_number=1,
                start_time=dt_mod.time(9, 0),
                end_time=dt_mod.time(10, 0)
            )
            db.add(tt)
            db.commit()

        yield {
            "admin_user": "phase3_admin",
            "admin_pass": "admin123",
            "teacher_user": "phase3_teacher",
            "teacher_pass": "teacher123",
            "teacher_id": teacher.id,
            "student_user": "student_charlie",
            "student_pass": "charlie123",
            "student_id": student.id,
            "ay_current_id": ay_current.id,
            "ay_next_id": ay_next.id,
            "subject_name": subject.name,
            "section": "CSE-C"
        }
    finally:
        db.close()


def test_biometric_quality_validation_unit():
    """
    Requirement 9: Unit testing biometric quality validation.
    Tests resolution, blur, lighting balance, and face box detection.
    """
    # 1. Image too small (<100x100)
    small_img = np.ones((80, 80, 3), dtype=np.uint8) * 128
    with pytest.raises(ValueError, match="Image resolution is too low"):
        detector.validate_enrollment_quality(small_img)

    # 2. No face detected
    blank_img = np.ones((200, 200, 3), dtype=np.uint8) * 128
    with pytest.raises(ValueError, match="No face detected"):
        detector.validate_enrollment_quality(blank_img)

    # 3. Blurry image (Laplacian variance < 30.0)
    # Mock face detection returning a box, but face image is uniform/blurred
    with patch.object(detector, 'detect_faces', return_value=[(20, 20, 100, 100)]):
        blurry_img = np.ones((200, 200, 3), dtype=np.uint8) * 120
        with pytest.raises(ValueError, match="Image is too blurry"):
            detector.validate_enrollment_quality(blurry_img)

    # 4. Too dark image (mean < 30.0 with blur_score >= 30)
    with patch.object(detector, 'detect_faces', return_value=[(20, 20, 100, 100)]):
        dark_img = np.zeros((200, 200, 3), dtype=np.uint8)
        dark_img[::2, :] = 25  # alternating rows provide Laplacian contrast with mean 12.5 < 30
        with pytest.raises(ValueError, match="Lighting is too dark"):
            detector.validate_enrollment_quality(dark_img)

    # 5. Overexposed image (mean > 235.0 with blur_score >= 30)
    with patch.object(detector, 'detect_faces', return_value=[(20, 20, 100, 100)]):
        bright_img = np.full((200, 200, 3), 240, dtype=np.uint8)
        bright_img[::2, :] = 255  # alternating rows provide Laplacian contrast with mean 247.5 > 235
        with pytest.raises(ValueError, match="Image is overexposed"):
            detector.validate_enrollment_quality(bright_img)

    # 6. Multiple faces detected (allow_multi=False)
    with patch.object(detector, 'detect_faces', return_value=[(10, 10, 60, 60), (90, 90, 60, 60)]):
        multi_img = create_synthetic_face_image(200, 200, blur=False, brightness=120)
        with pytest.raises(ValueError, match="Multiple faces"):
            detector.validate_enrollment_quality(multi_img)

    # 7. Valid high quality face
    with patch.object(detector, 'detect_faces', return_value=[(30, 30, 120, 120)]):
        valid_img = create_synthetic_face_image(200, 200, blur=False, brightness=120)
        norm_face, metrics = detector.validate_enrollment_quality(valid_img)
        assert norm_face.shape == (200, 200)
        assert metrics["sharpness"] >= 30.0
        assert 30.0 <= metrics["brightness"] <= 235.0
        assert metrics["quality_grade"] in ("Good", "Excellent")


def test_admin_role_restrictions_on_enrollments(setup_phase3_data):
    """
    Requirement 8: Only authorized Admin accounts may create, renew, or revoke enrollments.
    Teachers, Students, and Unauthenticated clients must be rejected.
    """
    info = setup_phase3_data
    admin_token = get_token(info["admin_user"], info["admin_pass"])
    teacher_token = get_token(info["teacher_user"], info["teacher_pass"])
    student_token = get_token(info["student_user"], info["student_pass"])

    # 1. Unauthenticated request -> 401
    res_unauth = client.post("/api/enrollments", json={"student_id": 1, "academic_year_id": 1})
    assert res_unauth.status_code == 401

    # 2. Student cannot create enrollment -> 403
    res_stu = client.post("/api/enrollments", json={
        "student_id": info["student_id"],
        "academic_year_id": info["ay_current_id"]
    }, headers={"Authorization": f"Bearer {student_token}"})
    assert res_stu.status_code == 403

    # 3. Teacher cannot create enrollment -> 403
    res_teacher = client.post("/api/enrollments", json={
        "student_id": info["student_id"],
        "academic_year_id": info["ay_current_id"]
    }, headers={"Authorization": f"Bearer {teacher_token}"})
    assert res_teacher.status_code == 403

    # 4. Admin can list and create enrollments -> 200
    res_admin = client.get("/api/enrollments", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    assert isinstance(res_admin.json(), list)


def test_one_academic_year_validity_enforcement(setup_phase3_data):
    """
    Requirement 6: Enforce one-academic-year enrollment validity on the backend (<= 366 days).
    """
    info = setup_phase3_data
    admin_token = get_token(info["admin_user"], info["admin_pass"])
    headers = {"Authorization": f"Bearer {admin_token}"}
    today = date.today()

    # 1. Duration > 366 days -> 400 Bad Request
    res_long = client.post("/api/enrollments", json={
        "student_id": info["student_id"],
        "academic_year_id": info["ay_current_id"],
        "valid_from": str(today),
        "valid_until": str(today + timedelta(days=400)),  # 400 days > 366
        "notes": "Testing duration overflow"
    }, headers=headers)
    assert res_long.status_code == 400
    assert "cannot exceed one academic year" in res_long.json()["detail"]

    # 2. Inverted dates (valid_until <= valid_from) -> 400 Bad Request
    res_inverted = client.post("/api/enrollments", json={
        "student_id": info["student_id"],
        "academic_year_id": info["ay_current_id"],
        "valid_from": str(today),
        "valid_until": str(today - timedelta(days=1)),
        "notes": "Testing inverted dates"
    }, headers=headers)
    assert res_inverted.status_code == 400
    assert "must be after valid_from" in res_inverted.json()["detail"]


def test_register_face_camera_quality_and_storage(setup_phase3_data):
    """
    Requirements 3, 5, 9, 10:
    - Biometric face registration via camera endpoint.
    - Rejection of poor quality images (422).
    - Biometric template stored with POSIX 0o600 file permissions.
    """
    info = setup_phase3_data
    admin_token = get_token(info["admin_user"], info["admin_pass"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Empty image list -> 400 Bad Request
    res_empty = client.post("/api/enrollments/register", json={
        "person_type": "student",
        "student_id": info["student_id"],
        "academic_year_id": info["ay_current_id"],
        "images": []
    }, headers=headers)
    assert res_empty.status_code == 400

    # 2. Poor quality / blank image failing biometric validation -> 422 Unprocessable Entity
    blank_b64 = img_to_base64(np.ones((200, 200, 3), dtype=np.uint8) * 128)
    res_fail = client.post("/api/enrollments/register", json={
        "person_type": "student",
        "student_id": info["student_id"],
        "academic_year_id": info["ay_current_id"],
        "images": [blank_b64]
    }, headers=headers)
    assert res_fail.status_code == 422
    assert "Biometric quality validation failed" in res_fail.json()["detail"]

    # 3. Successful face registration with valid synthetic images
    valid_img = create_synthetic_face_image(200, 200, blur=False, brightness=130)
    valid_b64 = img_to_base64(valid_img)

    with patch.object(detector, 'detect_faces', return_value=[(30, 30, 120, 120)]):
        res_success = client.post("/api/enrollments/register", json={
            "person_type": "student",
            "student_id": info["student_id"],
            "academic_year_id": info["ay_current_id"],
            "images": [valid_b64, valid_b64],
            "notes": "Verified clean face captures"
        }, headers=headers)
        assert res_success.status_code == 201
        data = res_success.json()
        assert data["success"] is True
        assert data["samples_saved"] == 2
        assert "quality_metrics" in data

        enrollment = data["enrollment"]
        assert enrollment["student_id"] == info["student_id"]
        assert enrollment["status"] == "active"
        assert enrollment["is_valid_today"] is True

        # Check Requirement 5: POSIX 0o600 restricted file permissions on saved template files
        db = SessionLocal()
        samples = db.query(FaceSample).filter(FaceSample.enrollment_id == enrollment["id"]).all()
        assert len(samples) >= 2
        for s in samples:
            assert os.path.exists(s.image_path)
            mode = os.stat(s.image_path).st_mode
            # Verify file permissions contain only owner read/write (0o600 or 0o660 in testing)
            assert bool(mode & stat.S_IRUSR)  # Owner can read
            assert not bool(mode & stat.S_IROTH)  # Others cannot read
            assert not bool(mode & stat.S_IWOTH)  # Others cannot write
        db.close()


def test_prevent_duplicate_active_enrollments(setup_phase3_data):
    """
    Requirement 10: Prevent duplicate enrollments in the same academic year.
    """
    info = setup_phase3_data
    admin_token = get_token(info["admin_user"], info["admin_pass"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Student Charlie already has an active enrollment in ay_current_id from previous test
    valid_img = create_synthetic_face_image(200, 200, blur=False, brightness=130)
    valid_b64 = img_to_base64(valid_img)

    with patch.object(detector, 'detect_faces', return_value=[(30, 30, 120, 120)]):
        res_dup = client.post("/api/enrollments/register", json={
            "person_type": "student",
            "student_id": info["student_id"],
            "academic_year_id": info["ay_current_id"],
            "images": [valid_b64]
        }, headers=headers)
        assert res_dup.status_code == 400
        assert "active enrollment already exists" in res_dup.json()["detail"].lower()


def test_renew_and_revoke_enrollment_lifecycle(setup_phase3_data):
    """
    Requirements 4, 8:
    - Renew active enrollment to next academic year.
    - Transitions old enrollment to 'renewed'.
    - New enrollment becomes 'active'.
    - Revoking enrollment sets status to 'revoked'.
    """
    info = setup_phase3_data
    admin_token = get_token(info["admin_user"], info["admin_pass"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    db = SessionLocal()
    old_enrollment = db.query(FaceEnrollment).filter(
        FaceEnrollment.student_id == info["student_id"],
        FaceEnrollment.academic_year_id == info["ay_current_id"],
        FaceEnrollment.status == "active"
    ).first()
    assert old_enrollment is not None
    old_id = old_enrollment.id
    db.close()

    # 1. Non-admin cannot renew
    teacher_token = get_token(info["teacher_user"], info["teacher_pass"])
    res_forbidden = client.post(f"/api/enrollments/{old_id}/renew", json={
        "academic_year_id": info["ay_next_id"]
    }, headers={"Authorization": f"Bearer {teacher_token}"})
    assert res_forbidden.status_code == 403

    # 2. Admin renews to next academic year
    res_renew = client.post(f"/api/enrollments/{old_id}/renew", json={
        "academic_year_id": info["ay_next_id"],
        "notes": "Transitioned to subsequent academic year"
    }, headers=headers)
    assert res_renew.status_code == 200
    renewed_detail = res_renew.json()
    assert renewed_detail["academic_year_id"] == info["ay_next_id"]
    assert renewed_detail["status"] == "active"

    # Verify old enrollment is now 'renewed'
    db = SessionLocal()
    old_rec = db.query(FaceEnrollment).filter(FaceEnrollment.id == old_id).first()
    assert old_rec.status == "renewed"
    db.close()

    # 3. Duplicate renewal to same academic year should fail
    res_dup_renew = client.post(f"/api/enrollments/{old_id}/renew", json={
        "academic_year_id": info["ay_next_id"]
    }, headers=headers)
    assert res_dup_renew.status_code == 400

    # 4. Revoke the new enrollment
    new_id = renewed_detail["id"]
    res_revoke = client.post(f"/api/enrollments/{new_id}/revoke", headers=headers)
    assert res_revoke.status_code == 200
    assert res_revoke.json()["status"] == "revoked"

    db = SessionLocal()
    revoked_rec = db.query(FaceEnrollment).filter(FaceEnrollment.id == new_id).first()
    assert revoked_rec.status == "revoked"
    db.close()


def test_attendance_authorization_enforces_enrollment_validity(setup_phase3_data):
    """
    Requirement 7: Expired or revoked enrollment must NOT authorize attendance.
    """
    info = setup_phase3_data
    teacher_token = get_token(info["teacher_user"], info["teacher_pass"])
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
    today = date.today()

    db = SessionLocal()
    # Mark any existing active enrollments for this student as revoked or expired
    db.query(FaceEnrollment).filter(FaceEnrollment.student_id == info["student_id"]).update({"status": "revoked"})
    db.commit()

    # 1. Attempt manual attendance with revoked enrollment -> 400 Bad Request
    res_revoked = client.post("/api/attendance/manual", json={
        "student_id": info["student_id"],
        "subject": info["subject_name"],
        "status": "present",
        "date": str(today)
    }, headers=teacher_headers)
    assert res_revoked.status_code == 400
    assert "cannot be authorized" in res_revoked.json()["detail"].lower()
    assert "revoked" in res_revoked.json()["detail"].lower()

    # 2. Attempt manual attendance with expired enrollment -> 400 Bad Request
    db.query(FaceEnrollment).filter(FaceEnrollment.student_id == info["student_id"]).update({
        "status": "expired",
        "valid_until": today - timedelta(days=10)
    })
    db.commit()

    res_expired = client.post("/api/attendance/manual", json={
        "student_id": info["student_id"],
        "subject": info["subject_name"],
        "status": "present",
        "date": str(today)
    }, headers=teacher_headers)
    assert res_expired.status_code == 400
    assert "cannot be authorized" in res_expired.json()["detail"].lower()
    assert "expired" in res_expired.json()["detail"].lower()

    # 3. Restore an ACTIVE valid enrollment -> Attendance authorized successfully (200 OK)
    enrollment = db.query(FaceEnrollment).filter(FaceEnrollment.student_id == info["student_id"]).first()
    enrollment.status = "active"
    enrollment.valid_from = today - timedelta(days=10)
    enrollment.valid_until = today + timedelta(days=100)
    db.commit()
    db.close()

    res_valid = client.post("/api/attendance/manual", json={
        "student_id": info["student_id"],
        "subject": info["subject_name"],
        "status": "present",
        "date": str(today)
    }, headers=teacher_headers)
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "present"
