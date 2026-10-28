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
def setup_phase7_data():
    db = SessionLocal()
    today = date.today()
    dow = today.weekday()
    sec_name = "CSE-7A"

    # 1. Academic Year & Semester
    ay = db.query(AcademicYear).filter(AcademicYear.name == "AY-2026-P7").first()
    if not ay:
        ay = AcademicYear(
            name="AY-2026-P7",
            start_date=today - timedelta(days=60),
            end_date=today + timedelta(days=300),
            is_current=True
        )
        db.add(ay)
        db.commit()
        db.refresh(ay)

    sem = db.query(Semester).filter(Semester.name == "Sem 6 CSE P7").first()
    if not sem:
        sem = Semester(
            name="Sem 6 CSE P7",
            academic_year_id=ay.id,
            start_date=today - timedelta(days=60),
            end_date=today + timedelta(days=120)
        )
        db.add(sem)
        db.commit()
        db.refresh(sem)

    # 2. Subject
    subj = db.query(Subject).filter(Subject.code == "CS701").first()
    if not subj:
        subj = Subject(
            name="Distributed Systems",
            code="CS701",
            semester_id=sem.id,
            section=sec_name
        )
        db.add(subj)
        db.commit()
        db.refresh(subj)

    # 3. Users: Admin, Primary Teacher, Substitute Teacher, Student User
    def create_or_get_user(username, role, full_name):
        u = db.query(User).filter(User.username == username).first()
        if not u:
            u = User(
                username=username,
                email=f"{username}@inst.edu",
                password_hash=get_password_hash("pass123"),
                full_name=full_name,
                role=role,
                is_active=True
            )
            db.add(u)
            db.commit()
            db.refresh(u)
        return u

    admin = create_or_get_user("admin_p7", "admin", "P7 Admin")
    primary_teacher = create_or_get_user("teacher_primary_p7", "teacher", "Prof. Primary")
    substitute_teacher = create_or_get_user("teacher_sub_p7", "teacher", "Prof. Substitute")
    other_teacher = create_or_get_user("teacher_unauth_p7", "teacher", "Prof. Unauthorized")
    student_user = create_or_get_user("student_user_p7", "student", "Student P7")

    # 4. Students
    def create_or_get_student(roll, name, section):
        std = db.query(Student).filter(Student.roll_number == roll).first()
        if not std:
            std = Student(roll_number=roll, name=name, section=section, email=f"{roll}@inst.edu", is_active=True)
            db.add(std)
            db.commit()
            db.refresh(std)
        return std

    sec_name = "CSE-7A"
    student1 = create_or_get_student("CS701-01", "Alice Smith", sec_name)
    student2 = create_or_get_student("CS701-02", "Bob Jones", sec_name)

    # Associate student_user with student1
    student_user.student_id = student1.id
    db.commit()

    # 5. Face enrollments for substitute teacher
    enroll = db.query(FaceEnrollment).filter(FaceEnrollment.user_id == substitute_teacher.id).first()
    if not enroll:
        enroll = FaceEnrollment(
            user_id=substitute_teacher.id,
            academic_year_id=ay.id,
            valid_from=today,
            valid_until=today + timedelta(days=365),
            status="active",
            enrolled_by=admin.id
        )
        db.add(enroll)
        db.commit()
        db.refresh(enroll)

    # Save biometric template for substitute teacher
    sub_face_img = np.ones((200, 200, 3), dtype=np.uint8) * 120
    cv2.circle(sub_face_img, (100, 100), 50, (220, 220, 220), -1)
    file_path, file_name = storage.save_face_sample(
        entity_id=substitute_teacher.id,
        face_image=sub_face_img,
        sample_index=1,
        is_user=True
    )
    existing_sample = db.query(FaceSample).filter(FaceSample.user_id == substitute_teacher.id).first()
    if not existing_sample:
        sample = FaceSample(
            user_id=substitute_teacher.id,
            enrollment_id=enroll.id,
            image_path=file_path,
            file_name=file_name
        )
        db.add(sample)
        db.commit()

    # 6. Timetable Entry for Primary Teacher
    tt_entry = db.query(TimetableEntry).filter(
        TimetableEntry.teacher_id == primary_teacher.id,
        TimetableEntry.subject_id == subj.id,
        TimetableEntry.section == sec_name
    ).first()
    if not tt_entry:
        tt_entry = TimetableEntry(
            day_of_week=dow,
            period_number=3,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(11, 0),
            subject_id=subj.id,
            teacher_id=primary_teacher.id,
            semester_id=sem.id,
            section=sec_name
        )
        db.add(tt_entry)
        db.commit()
        db.refresh(tt_entry)
    else:
        tt_entry.day_of_week = dow
        tt_entry.is_active = True
        db.commit()


    yield {
        "admin_user": "admin_p7",
        "primary_user": "teacher_primary_p7",
        "sub_user": "teacher_sub_p7",
        "unauth_user": "teacher_unauth_p7",
        "student_user": "student_user_p7",
        "admin_id": admin.id,
        "primary_id": primary_teacher.id,
        "sub_id": substitute_teacher.id,
        "unauth_id": other_teacher.id,
        "student1_id": student1.id,
        "student2_id": student2.id,
        "student1_roll": student1.roll_number,
        "tt_id": tt_entry.id,
        "subject_name": subj.name,
        "section": sec_name,
        "semester_id": sem.id,
        "academic_year_id": ay.id,
        "today": today
    }
    db.close()


def test_substitute_authorization_creation_and_audit(setup_phase7_data):
    """
    Requirements 1, 2, 5:
    - Admin authorizes a substitute teacher for a specific timetable slot.
    - Records original teacher, substitute teacher, authorizing admin, class, subject, date, and reason.
    - Complete audit trail is maintained.
    """
    info = setup_phase7_data
    admin_tok = get_token(info["admin_user"])

    db = SessionLocal()
    # Clean previous auth for this slot and date
    db.query(SubstituteAuthorization).filter(
        SubstituteAuthorization.timetable_entry_id == info["tt_id"],
        SubstituteAuthorization.date == info["today"]
    ).delete()
    db.commit()

    payload = {
        "timetable_entry_id": info["tt_id"],
        "original_teacher_id": info["primary_id"],
        "substitute_teacher_id": info["sub_id"],
        "date": str(info["today"]),
        "reason": "Prof. Primary on jury duty"
    }

    res = client.post(
        "/api/substitutes",
        json=payload,
        headers={"Authorization": f"Bearer {admin_tok}"}
    )
    assert res.status_code == 201
    auth_data = res.json()
    assert auth_data["timetable_entry_id"] == info["tt_id"]
    assert auth_data["original_teacher_id"] == info["primary_id"]
    assert auth_data["substitute_teacher_id"] == info["sub_id"]
    assert auth_data["authorized_by"] == info["admin_id"]
    assert auth_data["reason"] == "Prof. Primary on jury duty"
    assert auth_data["status"] == "authorized"

    # Verify Audit Log
    audit = db.query(AuditLog).filter(
        AuditLog.action == "AUTHORIZE_SUBSTITUTE_TEACHER",
        AuditLog.entity_id == auth_data["id"]
    ).first()
    assert audit is not None
    assert audit.user_id == info["admin_id"]
    details = json.loads(audit.details)
    assert details["substitute_teacher_id"] == info["sub_id"]
    assert details["original_teacher_id"] == info["primary_id"]
    assert details["reason"] == "Prof. Primary on jury duty"
    db.close()


def test_substitute_teacher_face_verification_and_session_access(setup_phase7_data):
    """
    Requirements 3, 4:
    - Substitute teacher logs in and verifies registered face biometrics.
    - Permits substitute to open only the specifically authorized session.
    """
    info = setup_phase7_data
    sub_tok = get_token(info["sub_user"])
    dummy_face = make_dummy_face_b64()

    db = SessionLocal()
    # Ensure active session on tt_id is cleared
    db.query(AttendanceSession).filter(AttendanceSession.timetable_entry_id == info["tt_id"]).delete()
    db.query(AttendanceSession).filter(AttendanceSession.teacher_id == info["sub_id"]).delete()
    db.commit()

    # Substitute opens authorized slot with biometric verification
    with patch.object(detector, 'detect_faces', return_value=[(10, 10, 180, 180)]), \
         patch.object(detector, 'evaluate_liveness', return_value=(True, 0.95, "Live real face")), \
         patch.object(cv2.face.LBPHFaceRecognizer, 'predict', return_value=(info["sub_id"], 10.0)):
        res = client.post(
            "/api/sessions/authorized-start?time=10:15",
            json={
                "timetable_entry_id": info["tt_id"],
                "face_image": dummy_face
            },
            headers={"Authorization": f"Bearer {sub_tok}"}
        )
        assert res.status_code == 201
        sess = res.json()
        assert sess["status"] == "active"
        assert sess["teacher_id"] == info["sub_id"]
        assert sess["timetable_entry_id"] == info["tt_id"]
        assert sess["section"] == info["section"]

    db.close()


def test_unauthorized_override_blocked(setup_phase7_data):
    """
    Requirement 4 & 6:
    - Teacher without assignment or substitute authorization is blocked with 403 Forbidden.
    """
    info = setup_phase7_data
    unauth_tok = get_token(info["unauth_user"])
    dummy_face = make_dummy_face_b64()

    # Unauthorized teacher attempts to open session on primary teacher's slot
    with patch.object(detector, 'detect_faces', return_value=[(10, 10, 180, 180)]), \
         patch.object(detector, 'evaluate_liveness', return_value=(True, 0.95, "Live real face")), \
         patch.object(cv2.face.LBPHFaceRecognizer, 'predict', return_value=(info["unauth_id"], 10.0)):
        res = client.post(
            "/api/sessions/authorized-start?time=10:15",
            json={
                "timetable_entry_id": info["tt_id"],
                "face_image": dummy_face
            },
            headers={"Authorization": f"Bearer {unauth_tok}"}
        )
        assert res.status_code == 403
        assert "Unauthorized instructor" in res.json()["detail"]


def test_attendance_finalization_marks_unrecorded_students_absent(setup_phase7_data):
    """
    Requirements 6 & 5:
    - Finalize attendance after session deadline using valid timetable and session records.
    - Active eligible students in the section not marked present are marked absent.
    - Session status transitions to 'closed'.
    - Comprehensive audit trail recorded.
    """
    info = setup_phase7_data
    sub_tok = get_token(info["sub_user"])
    db = SessionLocal()

    # Find the active session started by substitute
    session = db.query(AttendanceSession).filter(
        AttendanceSession.timetable_entry_id == info["tt_id"],
        AttendanceSession.status == "active"
    ).first()
    assert session is not None

    # Clean any leftover attendance on this session
    db.query(Attendance).filter(Attendance.session_id == session.id).delete()
    db.commit()

    # Mark Student 1 present manually or via recognition
    att1 = Attendance(
        student_id=info["student1_id"],
        session_id=session.id,
        subject=session.subject,
        date=info["today"],
        time=datetime.time(10, 5),
        status="present",
        confidence_score=14.2
    )
    db.add(att1)
    db.commit()

    # Now substitute teacher finalizes session
    res = client.post(
        f"/api/sessions/{session.id}/finalize",
        json={"reason": "Lecture ended normally"},
        headers={"Authorization": f"Bearer {sub_tok}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == session.id
    assert data["status"] == "closed"
    assert data["present_count"] >= 1
    assert data["absent_count"] >= 1  # Student 2 was marked absent
    assert data["review_required"] is False

    # Check Student 2 attendance record
    att2 = db.query(Attendance).filter(
        Attendance.student_id == info["student2_id"],
        Attendance.session_id == session.id
    ).first()
    assert att2 is not None
    assert att2.status == "absent"

    # Check audit log
    audit = db.query(AuditLog).filter(
        AuditLog.action == "FINALIZE_SESSION_ATTENDANCE",
        AuditLog.entity_id == session.id
    ).first()
    assert audit is not None
    details = json.loads(audit.details)
    assert details["present_count"] >= 1
    assert details["absent_count"] >= 1
    db.close()


def test_camera_failure_review_required_without_penalties(setup_phase7_data):
    """
    Requirement 7:
    - Handle camera failures and technical problems using a review-required state
      rather than automatically penalizing students with absences!
    """
    info = setup_phase7_data
    admin_tok = get_token(info["admin_user"])
    db = SessionLocal()

    # Create a fresh active session
    fresh_session = AttendanceSession(
        subject=info["subject_name"],
        section=info["section"],
        started_at=datetime.datetime.now(datetime.timezone.utc),
        created_by=info["admin_id"],
        teacher_id=info["primary_id"],
        timetable_entry_id=info["tt_id"],
        semester_id=info["semester_id"],
        academic_year_id=info["academic_year_id"],
        status="active"
    )
    db.add(fresh_session)
    db.commit()
    db.refresh(fresh_session)

    # Finalize reporting camera hardware failure
    res = client.post(
        f"/api/sessions/{fresh_session.id}/finalize",
        json={
            "camera_failed": True,
            "technical_issue": True,
            "reason": "Classroom USB camera disconnected during lecture"
        },
        headers={"Authorization": f"Bearer {admin_tok}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "review-required"
    assert data["review_required"] is True
    assert data["absent_count"] == 0  # CRITICAL: No absent penalties applied!
    assert "review-required" in data["message"].lower() or "not penalized" in data["message"].lower()

    # Ensure no absent records were inserted
    absent_records = db.query(Attendance).filter(
        Attendance.session_id == fresh_session.id,
        Attendance.status == "absent"
    ).all()
    assert len(absent_records) == 0

    # Ensure audit log captures technical review flag
    audit = db.query(AuditLog).filter(
        AuditLog.action == "FLAG_SESSION_TECHNICAL_REVIEW",
        AuditLog.entity_id == fresh_session.id
    ).first()
    assert audit is not None
    details = json.loads(audit.details)
    assert details["students_penalized"] is False
    assert details["camera_failed"] is True
    db.close()


def test_attendance_correction_request_and_approval_workflow(setup_phase7_data):
    """
    Requirements 8 & 5:
    - Controlled attendance correction request and approval process.
    - Records who approved it, when, and why.
    - Manual correction remains a controlled exception with audit trail.
    - Non-admin cannot approve corrections.
    """
    info = setup_phase7_data
    student_tok = get_token(info["student_user"])
    teacher_tok = get_token(info["sub_user"])
    admin_tok = get_token(info["admin_user"])
    db = SessionLocal()

    # Find the absent record created for student2
    absent_att = db.query(Attendance).filter(
        Attendance.student_id == info["student2_id"],
        Attendance.status == "absent"
    ).order_by(Attendance.id.desc()).first()
    assert absent_att is not None

    # 1. Verify student role isolation: Student 1 cannot request correction for Student 2
    req_payload = {
        "session_id": absent_att.session_id,
        "student_id": info["student2_id"],
        "requested_status": "present",
        "reason": "Student was seated outside wide-angle camera view; submitted handwritten lab notes as evidence.",
        "evidence_notes": "Verified by lab assistant John Doe"
    }
    res_forbidden = client.post(
        "/api/attendance/corrections",
        json=req_payload,
        headers={"Authorization": f"Bearer {student_tok}"}
    )
    assert res_forbidden.status_code == 403
    assert "Students can only request attendance corrections for themselves" in res_forbidden.json()["detail"]

    # Teacher submits correction request for student 2
    res_req = client.post(
        "/api/attendance/corrections",
        json=req_payload,
        headers={"Authorization": f"Bearer {teacher_tok}"}
    )
    assert res_req.status_code == 201
    corr_data = res_req.json()
    corr_id = corr_data["id"]
    assert corr_data["status"] == "pending"
    assert corr_data["previous_status"] == "absent"
    assert corr_data["requested_status"] == "present"

    # 2. Non-admin (teacher) attempts to approve correction -> 403 Forbidden
    res_unauth = client.put(
        f"/api/attendance/corrections/{corr_id}/review",
        json={"decision": "approved", "review_notes": "Looks good"},
        headers={"Authorization": f"Bearer {teacher_tok}"}
    )
    assert res_unauth.status_code == 403

    # 3. Admin reviews and approves correction
    res_approve = client.put(
        f"/api/attendance/corrections/{corr_id}/review",
        json={
            "decision": "approved",
            "review_notes": "Reviewed lab notes; physical attendance confirmed by lab instructor."
        },
        headers={"Authorization": f"Bearer {admin_tok}"}
    )
    assert res_approve.status_code == 200
    appr_data = res_approve.json()
    assert appr_data["status"] == "approved"
    assert appr_data["reviewed_by"] == info["admin_id"]
    assert appr_data["reviewed_at"] is not None
    assert "Reviewed lab notes" in appr_data["review_notes"]

    # 4. Verify Attendance record updated atomically
    db.refresh(absent_att)
    assert absent_att.status == "present"

    # 5. Verify Audit Log recorded approval details
    audit = db.query(AuditLog).filter(
        AuditLog.action == "APPROVE_ATTENDANCE_CORRECTION",
        AuditLog.entity_id == corr_id
    ).first()
    assert audit is not None
    assert audit.user_id == info["admin_id"]
    details = json.loads(audit.details)
    assert details["previous_status"] == "absent"
    assert details["new_status"] == "present"
    assert "Reviewed lab notes" in details["review_notes"]
    db.close()


def test_attendance_correction_rejection(setup_phase7_data):
    """
    Requirement 8:
    - Admin can reject attendance correction request with notes.
    - Attendance record remains unchanged.
    """
    info = setup_phase7_data
    student_tok = get_token(info["student_user"])
    admin_tok = get_token(info["admin_user"])
    db = SessionLocal()

    # Find a session and student
    session = db.query(AttendanceSession).filter(AttendanceSession.timetable_entry_id == info["tt_id"]).first()
    assert session is not None

    # Clean existing pending corrections for this student and session
    db.query(AttendanceCorrection).filter(
        AttendanceCorrection.session_id == session.id,
        AttendanceCorrection.student_id == info["student1_id"]
    ).delete()
    db.commit()

    # Ensure attendance record is absent so correction from absent -> present is valid
    att = db.query(Attendance).filter(
        Attendance.session_id == session.id,
        Attendance.student_id == info["student1_id"]
    ).first()
    if att:
        att.status = "absent"
    else:
        att = Attendance(
            student_id=info["student1_id"],
            session_id=session.id,
            subject=session.subject,
            date=info["today"],
            time=datetime.time(10, 0),
            status="absent"
        )
        db.add(att)
    db.commit()

    req_payload = {
        "session_id": session.id,
        "student_id": info["student1_id"],
        "requested_status": "present",
        "reason": "Submitted excuse note without medical certificate."
    }
    res_req = client.post(
        "/api/attendance/corrections",
        json=req_payload,
        headers={"Authorization": f"Bearer {student_tok}"}
    )
    assert res_req.status_code == 201
    corr_id = res_req.json()["id"]

    # Admin rejects
    res_rej = client.put(
        f"/api/attendance/corrections/{corr_id}/review",
        json={"decision": "rejected", "review_notes": "Incomplete documentation; medical certificate required."},
        headers={"Authorization": f"Bearer {admin_tok}"}
    )
    assert res_rej.status_code == 200
    assert res_rej.json()["status"] == "rejected"
    assert "Incomplete documentation" in res_rej.json()["review_notes"]

    # Verify attendance remains absent
    db.refresh(att)
    assert att.status == "absent"

    # Verify Audit Log
    audit = db.query(AuditLog).filter(
        AuditLog.action == "REJECT_ATTENDANCE_CORRECTION",
        AuditLog.entity_id == corr_id
    ).first()
    assert audit is not None
    db.close()


def test_multidimensional_reports_and_excel_export(setup_phase7_data):
    """
    Requirements 9 & 10:
    - Generate date-wise, subject-wise, semester-wise, and section-wise reports.
    - Support Excel export as appropriate for existing stack.
    """
    info = setup_phase7_data
    admin_tok = get_token(info["admin_user"])

    # 1. Test semester-wise report endpoint
    res_sem = client.get("/api/reports/semesters", headers={"Authorization": f"Bearer {admin_tok}"})
    assert res_sem.status_code == 200
    sems = res_sem.json()
    assert isinstance(sems, list)
    assert len(sems) > 0
    assert "semester_name" in sems[0]
    assert "average_attendance_rate" in sems[0]

    # 2. Test section-wise report endpoint
    res_sec = client.get("/api/reports/sections", headers={"Authorization": f"Bearer {admin_tok}"})
    assert res_sec.status_code == 200
    secs = res_sec.json()
    assert isinstance(secs, list)
    assert len(secs) > 0
    assert "section" in secs[0]
    assert "attendance_percentage" in secs[0]

    # 3. Test comprehensive report endpoint
    res_comp = client.get("/api/reports/comprehensive", headers={"Authorization": f"Bearer {admin_tok}"})
    assert res_comp.status_code == 200
    comp = res_comp.json()
    assert "overall" in comp
    assert "date_wise" in comp
    assert "subject_wise" in comp
    assert "semester_wise" in comp
    assert "section_wise" in comp
    assert comp["overall"]["total_students"] > 0

    # 4. Test Excel Export (Comprehensive Multi-Sheet Workbook)
    res_excel = client.get(
        "/api/reports/export/excel?report_type=comprehensive",
        headers={"Authorization": f"Bearer {admin_tok}"}
    )
    assert res_excel.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res_excel.headers["content-type"]
    assert len(res_excel.content) > 1000  # Valid binary Excel file
