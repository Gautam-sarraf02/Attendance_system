import pytest
import numpy as np
import cv2
from fastapi.testclient import TestClient
from app.main import app
from app.face.detector import detector
from app.face.recognizer import recognizer_service

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

def test_admin_login():
    # Valid login
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    token_data = res.json()
    assert "access_token" in token_data
    assert token_data["user"]["username"] == "admin"

    # Invalid login
    res_bad = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert res_bad.status_code == 401

def get_auth_header():
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_students_flow():
    headers = get_auth_header()

    # 1. Create a test student
    test_roll = f"TEST_{np.random.randint(10000, 99999)}"
    create_res = client.post("/api/students", json={
        "roll_number": test_roll,
        "name": "Test Student Automation",
        "section": "CSE-A",
        "email": "test.auto@college.edu"
    }, headers=headers)
    assert create_res.status_code == 201
    student = create_res.json()
    assert student["roll_number"] == test_roll
    student_id = student["id"]

    # 2. Duplicate roll number should fail
    dup_res = client.post("/api/students", json={
        "roll_number": test_roll,
        "name": "Duplicate Student",
        "section": "CSE-A"
    }, headers=headers)
    assert dup_res.status_code == 400

    # 3. Retrieve student
    get_res = client.get(f"/api/students/{student_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Test Student Automation"

    # 4. Cleanup/Delete student
    del_res = client.delete(f"/api/students/{student_id}", headers=headers)
    assert del_res.status_code == 200

def test_sessions_and_duplicate_attendance():
    headers = get_auth_header()

    # Create a unique student for session test
    roll = f"SESS_{np.random.randint(10000, 99999)}"
    s_res = client.post("/api/students", json={
        "roll_number": roll,
        "name": "Session Test Student",
        "section": "CSE-B"
    }, headers=headers)
    assert s_res.status_code == 201
    student_id = s_res.json()["id"]

    # Enroll student to satisfy Phase 3 attendance authorization
    from app.database import SessionLocal
    from app.models.academic_year import AcademicYear
    from app.models.face_enrollment import FaceEnrollment
    _db = SessionLocal()
    _ay = _db.query(AcademicYear).filter(AcademicYear.is_current == True).first() or _db.query(AcademicYear).first()
    if _ay:
        _enrollment = FaceEnrollment(
            student_id=student_id,
            academic_year_id=_ay.id,
            valid_from=_ay.start_date,
            valid_until=_ay.end_date,
            status="active"
        )
        _db.add(_enrollment)
        _db.commit()
    _db.close()

    # 1. Start a session
    sess_res = client.post("/api/sessions", json={
        "subject": "Deep Learning Automation",
        "section": "CSE-B"
    }, headers=headers)
    assert sess_res.status_code == 201
    session_id = sess_res.json()["id"]

    # 2. Mark manual attendance once
    att1 = client.post("/api/attendance/manual", json={
        "student_id": student_id,
        "session_id": session_id,
        "subject": "Deep Learning Automation",
        "status": "present"
    }, headers=headers)
    assert att1.status_code == 200

    # 3. Try marking duplicate attendance for the same student in the same session -> Must Fail
    att_dup = client.post("/api/attendance/manual", json={
        "student_id": student_id,
        "session_id": session_id,
        "subject": "Deep Learning Automation",
        "status": "present"
    }, headers=headers)
    assert att_dup.status_code == 400

    # 4. Stop session
    stop_res = client.post(f"/api/sessions/{session_id}/stop", headers=headers)
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "completed"

    # Clean up student
    client.delete(f"/api/students/{student_id}", headers=headers)

def test_reports_and_export():
    headers = get_auth_header()

    # 1. Dashboard stats
    dash_res = client.get("/api/dashboard/stats", headers=headers)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert "total_students" in dash_data
    assert "present_today" in dash_data

    # 2. Student attendance report
    stud_rep = client.get("/api/reports/students", headers=headers)
    assert stud_rep.status_code == 200
    assert isinstance(stud_rep.json(), list)

    # 3. CSV Export
    csv_res = client.get("/api/reports/export/csv?report_type=detailed", headers=headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]

    # 4. Excel Export
    excel_res = client.get("/api/reports/export/excel?report_type=detailed", headers=headers)
    assert excel_res.status_code == 200
    assert "spreadsheetml" in excel_res.headers["content-type"]

def test_face_recognition_pipeline_unit():
    # Test synthetic image processing with OpenCV
    test_face_1 = np.ones((200, 200), dtype=np.uint8) * 128
    # Add simple facial patterns for LBPH
    cv2.circle(test_face_1, (70, 70), 15, (50,), -1)
    cv2.circle(test_face_1, (130, 70), 15, (50,), -1)
    cv2.rectangle(test_face_1, (80, 130), (120, 150), (30,), -1)

    test_face_2 = np.ones((200, 200), dtype=np.uint8) * 200
    cv2.circle(test_face_2, (60, 60), 20, (100,), -1)
    cv2.circle(test_face_2, (140, 60), 20, (100,), -1)
    cv2.rectangle(test_face_2, (70, 140), (130, 160), (80,), -1)

    samples_dict = {
        101: [test_face_1, test_face_1],
        102: [test_face_2, test_face_2]
    }

    train_res = recognizer_service.train(samples_dict)
    assert train_res["success"] is True
    assert train_res["students_trained"] == 2
    assert recognizer_service.is_trained() is True

    # Test prediction on matching image
    pred_id, dist, is_known = recognizer_service.predict(test_face_1)
    assert pred_id == 101
    assert is_known is True
    assert dist < 10.0  # Exact match should have very low LBPH distance
