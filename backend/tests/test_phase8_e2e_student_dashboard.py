import base64
import json
import datetime
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
import pytest
import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.student import Student
from app.models.subject import Subject
from app.models.academic_year import AcademicYear
from app.models.semester import Semester
from app.models.timetable import TimetableEntry
from app.models.face_enrollment import FaceEnrollment
from app.models.face_sample import FaceSample
from app.models.substitute_auth import SubstituteAuthorization
from app.models.attendance_session import AttendanceSession
from app.models.attendance import Attendance
from app.models.attendance_correction import AttendanceCorrection
from app.models.audit_log import AuditLog
from app.auth.jwt_handler import get_password_hash
from app.face.detector import detector
from app.face.recognizer import recognizer_service
from app.face.storage import storage

client = TestClient(app)


def make_dummy_face_b64(width=200, height=200) -> str:
    img = np.ones((height, width, 3), dtype=np.uint8) * 120
    cv2.circle(img, (width // 2, height // 2), 60, (200, 200, 200), -1)
    _, buffer = cv2.imencode(".jpg", img)
    return base64.b64encode(buffer).decode("utf-8")


def get_token(username: str, password: str = "pass123") -> str:
    res = client.post(
        "/api/auth/login",
        json={"username": username, "password": password}
    )
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def setup_phase8_data():
    db = SessionLocal()
    today = date.today()
    dow = today.weekday()
    sec_name = "CSE-8A"

    # 1. Academic Year & Semester
    ay = db.query(AcademicYear).filter(AcademicYear.name == "AY-2026-P8").first()
    if not ay:
        ay = AcademicYear(
            name="AY-2026-P8",
            start_date=today - timedelta(days=60),
            end_date=today + timedelta(days=300),
            is_current=True
        )
        db.add(ay)
        db.commit()
        db.refresh(ay)

    sem = db.query(Semester).filter(Semester.name == "Sem 8 P8").first()
    if not sem:
        sem = Semester(
            name="Sem 8 P8",
            academic_year_id=ay.id,
            start_date=today - timedelta(days=60),
            end_date=today + timedelta(days=120)
        )
        db.add(sem)
        db.commit()
        db.refresh(sem)

    # 2. Subject
    subj = db.query(Subject).filter(Subject.code == "CS801-P8").first()
    if not subj:
        subj = Subject(
            code="CS801-P8",
            name="Distributed Cloud Systems",
            semester_id=sem.id,
            section=sec_name
        )
        db.add(subj)
        db.commit()
        db.refresh(subj)

    # 3. Users Helper
    def create_or_get_user(username, role, full_name, student_id=None):
        u = db.query(User).filter(User.username == username).first()
        if not u:
            u = User(
                username=username,
                email=f"{username}@college.edu",
                password_hash=get_password_hash("pass123"),
                role=role,
                full_name=full_name,
                student_id=student_id,
                is_active=True
            )
            db.add(u)
            db.commit()
            db.refresh(u)
        return u

    admin_u = create_or_get_user("admin_p8", "admin", "Admin Phase 8")
    teacher_u = create_or_get_user("teacher_p8", "teacher", "Prof. Primary P8")
    sub_u = create_or_get_user("sub_teacher_p8", "teacher", "Prof. Substitute P8")

    # 4. Students
    stu1 = db.query(Student).filter(Student.roll_number == "STU-P8-001").first()
    if not stu1:
        stu1 = Student(
            roll_number="STU-P8-001",
            name="Alice Walker",
            email="alice.p8@college.edu",
            section=sec_name,
            is_active=True
        )
        db.add(stu1)
        db.commit()
        db.refresh(stu1)

    stu1_u = create_or_get_user("STU-P8-001", "student", "Alice Walker", student_id=stu1.id)

    stu2 = db.query(Student).filter(Student.roll_number == "STU-P8-002").first()
    if not stu2:
        stu2 = Student(
            roll_number="STU-P8-002",
            name="Bob Martin",
            email="bob.p8@college.edu",
            section=sec_name,
            is_active=True
        )
        db.add(stu2)
        db.commit()
        db.refresh(stu2)

    stu2_u = create_or_get_user("STU-P8-002", "student", "Bob Martin", student_id=stu2.id)

    stu3 = db.query(Student).filter(Student.roll_number == "STU-P8-003").first()
    if not stu3:
        stu3 = Student(
            roll_number="STU-P8-003",
            name="Charlie Expired",
            email="charlie.p8@college.edu",
            section=sec_name,
            is_active=True
        )
        db.add(stu3)
        db.commit()
        db.refresh(stu3)

    stu3_u = create_or_get_user("STU-P8-003", "student", "Charlie Expired", student_id=stu3.id)

    # 5. Face Enrollments
    fe_teach = db.query(FaceEnrollment).filter(FaceEnrollment.user_id == teacher_u.id).first()
    if not fe_teach:
        fe_teach = FaceEnrollment(
            user_id=teacher_u.id,
            status="active",
            valid_from=today - timedelta(days=10),
            valid_until=today + timedelta(days=200),
            academic_year_id=ay.id
        )
        db.add(fe_teach)
        db.commit()
        db.refresh(fe_teach)

    fe_sub = db.query(FaceEnrollment).filter(FaceEnrollment.user_id == sub_u.id).first()
    if not fe_sub:
        fe_sub = FaceEnrollment(
            user_id=sub_u.id,
            status="active",
            valid_from=today - timedelta(days=10),
            valid_until=today + timedelta(days=200),
            academic_year_id=ay.id
        )
        db.add(fe_sub)
        db.commit()
        db.refresh(fe_sub)

    fe_stu1 = db.query(FaceEnrollment).filter(FaceEnrollment.student_id == stu1.id).first()
    if not fe_stu1:
        fe_stu1 = FaceEnrollment(
            student_id=stu1.id,
            status="active",
            valid_from=today - timedelta(days=30),
            valid_until=today + timedelta(days=180),
            academic_year_id=ay.id
        )
        db.add(fe_stu1)

    fe_stu2 = db.query(FaceEnrollment).filter(FaceEnrollment.student_id == stu2.id).first()
    if not fe_stu2:
        fe_stu2 = FaceEnrollment(
            student_id=stu2.id,
            status="active",
            valid_from=today - timedelta(days=30),
            valid_until=today + timedelta(days=180),
            academic_year_id=ay.id
        )
        db.add(fe_stu2)

    fe_stu3 = db.query(FaceEnrollment).filter(FaceEnrollment.student_id == stu3.id).first()
    if not fe_stu3:
        fe_stu3 = FaceEnrollment(
            student_id=stu3.id,
            status="expired",
            valid_from=today - timedelta(days=200),
            valid_until=today - timedelta(days=5),
            academic_year_id=ay.id
        )
        db.add(fe_stu3)

    db.commit()

    # Ensure teacher and substitute face sample files exist in secure storage
    sample_img = np.ones((200, 200, 3), dtype=np.uint8) * 120
    cv2.circle(sample_img, (100, 100), 50, (220, 220, 220), -1)

    t_path, t_name = storage.save_face_sample(
        entity_id=teacher_u.id,
        face_image=sample_img,
        sample_index=1,
        is_user=True
    )
    if not db.query(FaceSample).filter(FaceSample.user_id == teacher_u.id).first():
        db.add(FaceSample(
            user_id=teacher_u.id,
            enrollment_id=fe_teach.id,
            image_path=t_path,
            file_name=t_name
        ))

    sub_path, sub_name = storage.save_face_sample(
        entity_id=sub_u.id,
        face_image=sample_img,
        sample_index=1,
        is_user=True
    )
    if not db.query(FaceSample).filter(FaceSample.user_id == sub_u.id).first():
        db.add(FaceSample(
            user_id=sub_u.id,
            enrollment_id=fe_sub.id,
            image_path=sub_path,
            file_name=sub_name
        ))
    db.commit()

    # 6. Timetable Entry: Period 1 slot encompassing 10:00 to 11:00
    tt = db.query(TimetableEntry).filter(
        TimetableEntry.subject_id == subj.id,
        TimetableEntry.section == sec_name,
        TimetableEntry.day_of_week == dow
    ).first()

    if not tt:
        tt = TimetableEntry(
            day_of_week=dow,
            period_number=1,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(11, 0),
            subject_id=subj.id,
            teacher_id=teacher_u.id,
            semester_id=sem.id,
            section=sec_name,
            is_active=True
        )
        db.add(tt)
    else:
        tt.start_time = datetime.time(10, 0)
        tt.end_time = datetime.time(11, 0)
        tt.teacher_id = teacher_u.id
        tt.is_active = True

    db.commit()
    db.refresh(tt)

    info = {
        "admin_id": admin_u.id,
        "teacher_id": teacher_u.id,
        "sub_id": sub_u.id,
        "stu1_id": stu1.id,
        "stu2_id": stu2.id,
        "stu3_id": stu3.id,
        "ay_id": ay.id,
        "sem_id": sem.id,
        "subj_id": subj.id,
        "subj_name": subj.name,
        "section": sec_name,
        "timetable_id": tt.id
    }
    db.close()
    return info


# ==============================================================================
# TEST 1: Role Login and Permission Isolation (Requirement 8 & 9)
# ==============================================================================
def test_role_login_and_permission_isolation(setup_phase8_data):
    data = setup_phase8_data
    admin_token = get_token("admin_p8")
    teacher_token = get_token("teacher_p8")
    student_token = get_token("STU-P8-001")

    # 1. Admin accessing admin dashboard stats -> 200
    res = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200

    # 2. Teacher attempting to access admin-only substitute creation -> 403 Forbidden
    res = client.post(
        "/api/substitutes",
        json={"timetable_entry_id": data["timetable_id"]},
        headers={"Authorization": f"Bearer {teacher_token}"}
    )
    assert res.status_code == 403

    # 3. Student attempting to access admin-only substitute creation -> 403 Forbidden
    res = client.post(
        "/api/substitutes",
        json={"timetable_entry_id": data["timetable_id"]},
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert res.status_code == 403

    # 4. Student attempting to start session -> 403 Forbidden
    res = client.post(
        "/api/sessions",
        json={"subject": data["subj_name"], "section": data["section"]},
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert res.status_code == 403

    # 5. Student attempting manual attendance marking -> 403 Forbidden
    res = client.post(
        "/api/attendance/manual",
        json={"student_id": data["stu1_id"], "subject": data["subj_name"], "status": "present"},
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert res.status_code == 403

    # 6. Student attempting to inspect another student's records -> 403 Forbidden
    res = client.get(
        f"/api/dashboard/student?student_id={data['stu2_id']}",
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert res.status_code == 403

    # 7. Student querying own dashboard -> 200 OK
    res = client.get("/api/dashboard/student", headers={"Authorization": f"Bearer {student_token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["profile"]["roll_number"] == "STU-P8-001"
    assert body["profile"]["name"] == "Alice Walker"
    assert body["validity"]["is_valid"] is True


# ==============================================================================
# TEST 2: Complete End-to-End Workflow (Requirement 1, 2, 3, 4, 5, 8, 10)
# ==============================================================================
def test_complete_e2e_workflow(setup_phase8_data):
    data = setup_phase8_data
    teacher_token = get_token("teacher_p8")
    student1_token = get_token("STU-P8-001")
    student2_token = get_token("STU-P8-002")

    dummy_b64 = make_dummy_face_b64()

    # Clean existing sessions and attendance records for these students
    db = SessionLocal()
    db.query(Attendance).filter(Attendance.student_id.in_([data["stu1_id"], data["stu2_id"]])).delete()
    db.query(AttendanceSession).filter(AttendanceSession.timetable_entry_id == data["timetable_id"]).delete()
    db.commit()
    db.close()

    # 1. Teacher starts session with face verification
    with patch.object(detector, 'detect_faces', return_value=[(10, 10, 180, 180)]), \
         patch.object(detector, 'evaluate_liveness', return_value=(True, 0.95, "Live real face")), \
         patch.object(cv2.face.LBPHFaceRecognizer, 'predict', return_value=(data["teacher_id"], 12.0)):
        start_payload = {
            "timetable_entry_id": data["timetable_id"],
            "face_image": dummy_b64
        }
        res = client.post(
            "/api/sessions/authorized-start?time=10:15",
            json=start_payload,
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        assert res.status_code == 201, f"Session start failed: {res.text}"
        session_info = res.json()
        session_id = session_info["id"]
        assert session_info["status"] == "active"
        assert session_info["subject"] == data["subj_name"]

    # 2. Classroom camera frame auto-scanning student 1
    with patch.object(detector, 'detect_faces', return_value=[(50, 50, 160, 160)]), \
         patch.object(detector, 'evaluate_liveness', return_value=(True, 0.95, "Live face detected")), \
         patch.object(recognizer_service, 'predict', return_value=(data["stu1_id"], 22.4, True)):
        frame_payload = {
            "image_base64": dummy_b64,
            "session_id": session_id,
            "auto_mark": True
        }
        rec_res = client.post(
            "/api/attendance/recognize",
            json=frame_payload,
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        assert rec_res.status_code == 200
        rec_body = rec_res.json()
        print("\n\n>>> DETECTION MESSAGE:", rec_body["detections"][0]["status_message"])
        assert rec_body["known_faces_count"] == 1
        assert rec_body["detections"][0]["student_id"] == data["stu1_id"]
        assert rec_body["detections"][0]["attendance_marked"] is True

    # 3. Duplicate Prevention: Second scan in same session returns attendance_marked=False
    with patch.object(detector, 'detect_faces', return_value=[(50, 50, 160, 160)]), \
         patch.object(detector, 'evaluate_liveness', return_value=(True, 0.95, "Live face detected")), \
         patch.object(recognizer_service, 'predict', return_value=(data["stu1_id"], 22.4, True)):
        rec_res2 = client.post(
            "/api/attendance/recognize",
            json=frame_payload,
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        assert rec_res2.status_code == 200
        rec_body2 = rec_res2.json()
        assert rec_body2["known_faces_count"] == 1
        assert rec_body2["detections"][0]["attendance_marked"] is False

    # 4. Requirement 7: Active session must not show absent record for student 2 yet
    s2_res = client.get("/api/dashboard/student", headers={"Authorization": f"Bearer {student2_token}"})
    assert s2_res.status_code == 200
    s2_body = s2_res.json()
    active_absents = [p for p in s2_body["punch_history"] if p["session_id"] == session_id and p["status"] == "absent"]
    assert len(active_absents) == 0, "Requirement 7 violation: Unfinalized session showed absent record!"

    # 5. Teacher finalizes session (marking absent un-punched students)
    finalize_res = client.post(
        f"/api/sessions/{session_id}/finalize",
        json={"reason": "Lecture concluded normally"},
        headers={"Authorization": f"Bearer {teacher_token}"}
    )
    assert finalize_res.status_code == 200
    fin_data = finalize_res.json()
    assert fin_data["status"] == "closed"
    assert fin_data["absent_count"] >= 1

    # 6. Student 1 Dashboard Check (Present Student)
    s1_res = client.get("/api/dashboard/student", headers={"Authorization": f"Bearer {student1_token}"})
    assert s1_res.status_code == 200
    s1_body = s1_res.json()

    assert s1_body["validity"]["is_valid"] is True
    assert s1_body["validity"]["days_remaining"] > 0
    assert s1_body["stats"]["total_present"] >= 1
    assert s1_body["stats"]["overall_percentage"] == 100.0
    assert s1_body["stats"]["is_eligible_for_exams"] is True

    # Subject Stats
    sub_stat = next(s for s in s1_body["subject_stats"] if s["subject"] == data["subj_name"])
    assert sub_stat["present_count"] == 1
    assert sub_stat["absent_count"] == 0
    assert sub_stat["percentage"] == 100.0

    # Punch History
    punch = next(p for p in s1_body["punch_history"] if p["session_id"] == session_id)
    assert punch["status"] == "present"
    assert punch["period_number"] == 1
    assert punch["subject"] == data["subj_name"]
    assert punch["is_finalized"] is True

    # 7. Student 2 Dashboard Check (Absent Student after finalization)
    s2_res = client.get("/api/dashboard/student", headers={"Authorization": f"Bearer {student2_token}"})
    assert s2_res.status_code == 200
    s2_final_body = s2_res.json()
    finalized_absents = [p for p in s2_final_body["punch_history"] if p["session_id"] == session_id and p["status"] == "absent"]
    assert len(finalized_absents) == 1, "Finalized absent record should now be visible"
    assert s2_final_body["stats"]["total_absent"] >= 1


# ==============================================================================
# TEST 3: Attendance Correction Request Process (Requirement 6)
# ==============================================================================
def test_student_correction_request_lifecycle(setup_phase8_data):
    data = setup_phase8_data
    student2_token = get_token("STU-P8-002")
    admin_token = get_token("admin_p8")

    db = SessionLocal()
    # Clean previous corrections for Student 2
    db.query(AttendanceCorrection).filter(AttendanceCorrection.student_id == data["stu2_id"]).delete()
    db.commit()

    att = db.query(Attendance).filter(
        Attendance.student_id == data["stu2_id"],
        Attendance.status == "absent"
    ).first()

    if not att:
        sess = AttendanceSession(
            timetable_entry_id=data["timetable_id"],
            teacher_id=data["teacher_id"],
            subject=data["subj_name"],
            section=data["section"],
            semester_id=data["sem_id"],
            status="closed"
        )
        db.add(sess)
        db.commit()
        db.refresh(sess)

        # Ensure no duplicate attendance row exists for (student_id, session_id)
        att = db.query(Attendance).filter(
            Attendance.student_id == data["stu2_id"],
            Attendance.session_id == sess.id
        ).first()

        if not att:
            att = Attendance(
                student_id=data["stu2_id"],
                session_id=sess.id,
                subject=data["subj_name"],
                date=date.today(),
                time=datetime.datetime.now().time(),
                status="absent"
            )
            db.add(att)
            db.commit()
            db.refresh(att)
        else:
            att.status = "absent"
            db.commit()
            db.refresh(att)

    att_id = att.id
    sess_id = att.session_id
    db.close()

    # 1. Student submits correction request
    corr_payload = {
        "session_id": sess_id,
        "student_id": data["stu2_id"],
        "attendance_id": att_id,
        "reason": "Camera failed to detect face due to low lighting in room",
        "evidence_notes": "Signed roll sheet by faculty",
        "requested_status": "present"
    }
    sub_res = client.post(
        "/api/attendance/corrections",
        json=corr_payload,
        headers={"Authorization": f"Bearer {student2_token}"}
    )
    assert sub_res.status_code == 201
    corr_data = sub_res.json()
    assert corr_data["status"] == "pending"
    corr_id = corr_data["id"]

    # Verify original attendance record is NOT modified directly
    db = SessionLocal()
    att_check = db.query(Attendance).filter(Attendance.id == att_id).first()
    assert att_check.status == "absent", "Direct editing must not occur upon request submission"
    db.close()

    # 2. Student cannot review/approve correction
    unauth_decide = client.put(
        f"/api/attendance/corrections/{corr_id}/review",
        json={"decision": "approved", "review_notes": "Self approval attempt"},
        headers={"Authorization": f"Bearer {student2_token}"}
    )
    assert unauth_decide.status_code == 403

    # 3. Admin approves correction request
    admin_decide = client.put(
        f"/api/attendance/corrections/{corr_id}/review",
        json={"decision": "approved", "review_notes": "Verified with physical attendance sign-sheet"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert admin_decide.status_code == 200
    dec_body = admin_decide.json()
    assert dec_body["status"] == "approved"

    # 4. Verify attendance record is now updated to present
    db = SessionLocal()
    att_updated = db.query(Attendance).filter(Attendance.id == att_id).first()
    assert att_updated.status == "present", "Attendance should be converted to present upon approval"

    # Audit log check
    audit = db.query(AuditLog).filter(
        AuditLog.action.in_(["APPROVE_ATTENDANCE_CORRECTION", "REQUEST_ATTENDANCE_CORRECTION"])
    ).first()
    assert audit is not None, "Audit log must be created for correction decision"
    db.close()


# ==============================================================================
# TEST 4: Expired Enrollment Lockout (Requirement 11)
# ==============================================================================
def test_expired_enrollment_prevention(setup_phase8_data):
    data = setup_phase8_data
    teacher_token = get_token("teacher_p8")
    dummy_b64 = make_dummy_face_b64()

    db = SessionLocal()
    active_sess = db.query(AttendanceSession).filter(AttendanceSession.status == "active").first()
    if not active_sess:
        active_sess = AttendanceSession(
            timetable_entry_id=data["timetable_id"],
            teacher_id=data["teacher_id"],
            subject=data["subj_name"],
            section=data["section"],
            semester_id=data["sem_id"],
            status="active"
        )
        db.add(active_sess)
        db.commit()
    sess_id = active_sess.id
    db.close()

    # Match student 3 (expired enrollment)
    with patch.object(detector, 'detect_faces', return_value=[(50, 50, 160, 160)]), \
         patch.object(recognizer_service, 'predict', return_value=(data["stu3_id"], 22.4, True)):
        res = client.post(
            "/api/attendance/recognize",
            json={"image_base64": dummy_b64, "session_id": sess_id, "auto_mark": True},
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        assert res.status_code == 200
        body = res.json()
        assert body["detections"][0]["attendance_marked"] is False


# ==============================================================================
# TEST 5: Substitute Authorization Flow (Requirement 11)
# ==============================================================================
def test_substitute_authorization_flow(setup_phase8_data):
    data = setup_phase8_data
    admin_token = get_token("admin_p8")
    sub_token = get_token("sub_teacher_p8")
    dummy_b64 = make_dummy_face_b64()

    # Clean previous authorizations
    db = SessionLocal()
    db.query(SubstituteAuthorization).filter(
        SubstituteAuthorization.timetable_entry_id == data["timetable_id"],
        SubstituteAuthorization.date == date.today()
    ).delete()
    db.commit()
    db.close()

    # 1. Admin authorizes substitute teacher
    auth_payload = {
        "timetable_entry_id": data["timetable_id"],
        "original_teacher_id": data["teacher_id"],
        "substitute_teacher_id": data["sub_id"],
        "date": str(date.today()),
        "reason": "Primary faculty attending academic conference"
    }
    auth_res = client.post(
        "/api/substitutes",
        json=auth_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert auth_res.status_code == 201
    auth_data = auth_res.json()
    assert auth_data["status"] == "authorized"

    # Clean previous sessions for this slot before starting substitute session
    db = SessionLocal()
    db.query(AttendanceSession).filter(AttendanceSession.timetable_entry_id == data["timetable_id"]).delete()
    db.commit()
    db.close()

    # 2. Substitute teacher starts session with face verification
    with patch.object(detector, 'detect_faces', return_value=[(10, 10, 180, 180)]), \
         patch.object(detector, 'evaluate_liveness', return_value=(True, 0.95, "Live real face")), \
         patch.object(cv2.face.LBPHFaceRecognizer, 'predict', return_value=(data["sub_id"], 10.0)):
        start_res = client.post(
            "/api/sessions/authorized-start?time=10:15",
            json={"timetable_entry_id": data["timetable_id"], "face_image": dummy_b64},
            headers={"Authorization": f"Bearer {sub_token}"}
        )
        assert start_res.status_code == 201
        sess_info = start_res.json()
        assert sess_info["teacher_id"] == data["sub_id"]
        assert sess_info["status"] == "active"

        # Clean up session
        client.post(f"/api/sessions/{sess_info['id']}/close", headers={"Authorization": f"Bearer {sub_token}"})


# ==============================================================================
# TEST 6: Camera Failure / Review-Required Flow (Requirement 11 & 12)
# ==============================================================================
def test_camera_failure_review_required(setup_phase8_data):
    data = setup_phase8_data
    teacher_token = get_token("teacher_p8")

    db = SessionLocal()
    sess = AttendanceSession(
        timetable_entry_id=data["timetable_id"],
        teacher_id=data["teacher_id"],
        subject=data["subj_name"],
        section=data["section"],
        semester_id=data["sem_id"],
        status="active"
    )
    db.add(sess)
    db.commit()
    sess_id = sess.id
    db.close()

    # Flag review-required due to camera hardware failure
    flag_res = client.post(
        f"/api/sessions/{sess_id}/flag-review",
        json={"reason": "Camera feed degraded, frame capture timeout occurred"},
        headers={"Authorization": f"Bearer {teacher_token}"}
    )
    assert flag_res.status_code == 200
    body = flag_res.json()
    assert body["status"] == "review-required"

    # Verify session status in database
    db = SessionLocal()
    db_sess = db.query(AttendanceSession).filter(AttendanceSession.id == sess_id).first()
    assert db_sess.status == "review-required"
    db.close()
