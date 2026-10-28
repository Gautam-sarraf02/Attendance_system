import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
from app.database import get_db
from app.models.attendance import Attendance
from app.models.attendance_session import AttendanceSession
from app.models.student import Student
from app.models.user import User
from app.models.face_enrollment import FaceEnrollment

from app.schemas.attendance import (
    AttendanceSimple,
    AttendanceDetail,
    AttendanceHistoryResponse,
    ManualAttendanceCreate
)
from app.schemas.face import (
    RecognizeFrameRequest,
    RecognizeFrameResponse,
    RecognitionDetection,
    BoundingBox
)
from app.auth.deps import (
    get_current_user,
    get_current_admin,
    verify_teacher_class_access,
    get_teacher_assigned_classes,
    verify_student_access,
)
from app.face.detector import detector
from app.face.recognizer import recognizer_service

router = APIRouter(prefix="/attendance", tags=["Attendance Tracking"])


def normalize_section(sec: Optional[str]) -> str:
    if not sec:
        return ""
    s = sec.strip().upper()
    for prefix in ("CSE-", "SECTION-", "SECTION ", "SEC-", "IT-", "ECE-"):
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
    return s


def check_student_enrollment_validity(
    student_id: int,
    db: Session,
    target_date: Optional[datetime.date] = None,
    academic_year_id: Optional[int] = None
) -> tuple[bool, str]:
    """
    Validates that a student has an active face enrollment valid for target_date and academic year.
    Requirement: Expired or un-enrolled students must not authorize attendance.
    """
    check_date = target_date or datetime.date.today()
    query = db.query(FaceEnrollment).filter(FaceEnrollment.student_id == student_id)
    if academic_year_id:
        query = query.filter(FaceEnrollment.academic_year_id == academic_year_id)

    enrollments = query.all()
    if not enrollments:
        # If no enrollments exist in the whole system (e.g. uninitialized system), permit baseline operations
        if db.query(FaceEnrollment).count() == 0:
            return True, "Valid"
        return False, "No active face enrollment found for this student/academic year"

    # Check for active enrollment spanning check_date
    active_valid = [e for e in enrollments if e.status == "active" and e.valid_from <= check_date <= e.valid_until]
    if active_valid:
        return True, "Valid"

    for e in enrollments:
        if e.status == "revoked":
            return False, "Face enrollment has been revoked"
        if e.status == "expired" or e.valid_until < check_date:
            return False, f"Face enrollment expired on {e.valid_until}"

    return False, "Face enrollment is not active for this date"


@router.post("/recognize", response_model=RecognizeFrameResponse)
def recognize_and_mark_attendance(
    payload: RecognizeFrameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Phase 6 Classroom Automatic Multi-Face Recognition & Attendance Marking:
    1. Decodes incoming webcam frame.
    2. Detects all face bounding boxes in the classroom frame.
    3. Evaluates passive 2D liveness/anti-spoofing heuristics for each face.
    4. Crops and normalizes each face ROI.
    5. Runs OpenCV LBPH recognizer to match registered student templates.
    6. Enforces strict server-side rules:
       - Session must be active
       - Server 15-minute deadline has not passed
       - Student enrollment is valid for academic year
       - Student belongs to scheduled section
       - Match meets confidence threshold (distance <= threshold)
       - Duplicate prevention ignores already marked students
    7. Automatically logs valid attendance records.
    """
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot operate facial recognition scanners."
        )

    try:
        frame_image = detector.decode_image_base64(payload.image_base64)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image format: {str(e)}"
        )

    # 1. Multi-face detection on frame
    boxes = detector.detect_faces(frame_image)

    # 2. Check active session context
    session = None
    session_status = None
    session_section = None
    if payload.session_id:
        session = db.query(AttendanceSession).filter(
            AttendanceSession.id == payload.session_id
        ).first()
        if session:
            session_status = session.status
            session_section = session.section

    # Pre-fetch cache of active students
    students_map = {s.id: s for s in db.query(Student).filter(Student.is_active == True).all()}

    is_model_ready = recognizer_service.is_trained()
    detections: List[RecognitionDetection] = []
    known_count = 0
    unknown_count = 0

    today = datetime.date.today()
    current_time = datetime.datetime.now().time()

    for (x, y, w, h) in boxes:
        bbox = BoundingBox(x=x, y=y, width=w, height=h)

        # Crop raw face region and evaluate neural anti-spoofing / liveness
        img_h, img_w = frame_image.shape[:2]
        raw_crop = frame_image[max(0, y):min(img_h, y + h), max(0, x):min(img_w, x + w)]
        is_live, liveness_score, liveness_msg = detector.evaluate_liveness(
            face_roi=raw_crop,
            full_image=frame_image,
            bbox=(x, y, w, h)
        )

        if not is_model_ready:
            detections.append(RecognitionDetection(
                box=bbox,
                student_id=None,
                roll_number=None,
                name="Unknown",
                section=None,
                confidence=999.0,
                is_known=False,
                attendance_marked=False,
                status_message="Model not trained",
                liveness_score=liveness_score,
                is_live=is_live
            ))
            unknown_count += 1
            continue

        try:
            face_roi = detector.extract_and_normalize_face(frame_image, (x, y, w, h))
            pred_id, distance, is_known = recognizer_service.predict(face_roi)

            if is_known and pred_id in students_map:
                student = students_map[pred_id]
                known_count += 1
                attendance_marked = False
                status_message = "Recognized"

                # Check Liveness / Anti-spoofing: Block attendance if spoof detected or liveness fails
                if not is_live:
                    status_message = f"Liveness check failed — attendance not marked ({liveness_msg})"
                    attendance_marked = False
                elif not session:
                    status_message = "Recognized (No Active Session)"
                    attendance_marked = False
                elif session.status != "active":
                    status_message = f"Session is not active ({session.status})"
                    attendance_marked = False
                else:
                    # Session is active. Check remaining 4 constraints:
                    # Constraint 1: Check enrollment validity for session's academic year
                    is_enrolled_valid, enroll_msg = check_student_enrollment_validity(
                        student.id,
                        db,
                        today,
                        academic_year_id=session.academic_year_id
                    )
                    if not is_enrolled_valid:
                        status_message = f"Enrollment Invalid ({enroll_msg})"
                        attendance_marked = False

                    # Constraint 2: Verify student belongs to scheduled section
                    elif session.section and (not student.section or normalize_section(session.section) != normalize_section(student.section)):
                        status_message = f"Wrong Section (Student is {student.section or 'Unassigned'}, Class is {session.section})"
                        attendance_marked = False

                    # Constraint 3: Check 15-minute deadline window
                    else:
                        now_utc = datetime.datetime.now(datetime.timezone.utc)
                        deadline_passed = False
                        if session.recognition_window_end:
                            rw_end = session.recognition_window_end
                            if rw_end.tzinfo is None:
                                rw_end = rw_end.replace(tzinfo=datetime.timezone.utc)
                            if now_utc > rw_end:
                                deadline_passed = True

                        if deadline_passed:
                            status_message = "Deadline Expired (15-min window passed)"
                            attendance_marked = False
                        elif payload.auto_mark:
                            # Constraint 4: Check duplicate attendance in this session
                            already_marked = db.query(Attendance).filter(
                                Attendance.student_id == student.id,
                                Attendance.session_id == session.id
                            ).first()

                            if already_marked:
                                status_message = "Already Marked Present"
                                attendance_marked = False
                            else:
                                try:
                                    # Insert new attendance record automatically
                                    new_attendance = Attendance(
                                        student_id=student.id,
                                        session_id=session.id,
                                        subject=session.subject,
                                        date=today,
                                        time=current_time,
                                        status="present",
                                        confidence_score=distance
                                    )
                                    db.add(new_attendance)
                                    db.commit()
                                    attendance_marked = True
                                    status_message = "Marked Present"
                                except Exception:
                                    db.rollback()
                                    # Concurrent duplicate caught by unique DB constraint
                                    status_message = "Already Marked Present"
                                    attendance_marked = False
                        else:
                            status_message = "Recognized (Auto-mark off)"

                detections.append(RecognitionDetection(
                    box=bbox,
                    student_id=student.id,
                    roll_number=student.roll_number,
                    name=student.name,
                    section=student.section,
                    confidence=distance,
                    is_known=True,
                    attendance_marked=attendance_marked,
                    status_message=status_message,
                    liveness_score=liveness_score,
                    is_live=is_live
                ))
            else:
                unknown_count += 1
                detections.append(RecognitionDetection(
                    box=bbox,
                    student_id=None,
                    roll_number=None,
                    name="Unknown",
                    section=None,
                    confidence=distance,
                    is_known=False,
                    attendance_marked=False,
                    status_message="Unknown Face",
                    liveness_score=liveness_score,
                    is_live=is_live
                ))

        except Exception as e:
            unknown_count += 1
            detections.append(RecognitionDetection(
                box=bbox,
                student_id=None,
                roll_number=None,
                name="Unknown",
                section=None,
                confidence=999.0,
                is_known=False,
                attendance_marked=False,
                status_message=f"Error: {str(e)[:30]}",
                liveness_score=liveness_score,
                is_live=is_live
            ))

    return RecognizeFrameResponse(
        session_id=session.id if session else None,
        session_status=session_status,
        session_section=session_section,
        total_faces_detected=len(boxes),
        known_faces_count=known_count,
        unknown_faces_count=unknown_count,
        detections=detections,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

@router.get("/history", response_model=AttendanceHistoryResponse)
def get_attendance_history(
    date_val: Optional[datetime.date] = Query(None, alias="date"),
    subject: Optional[str] = None,
    section: Optional[str] = None,
    student_id: Optional[int] = None,
    session_id: Optional[int] = None,
    status_val: Optional[str] = Query(None, alias="status"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = (
        db.query(Attendance, Student)
        .join(Student, Attendance.student_id == Student.id)
    )

    # 1. Student access control: students may strictly view only their own records
    if current_user.role == "student":
        target_sid = current_user.student_id
        if not target_sid:
            st = db.query(Student).filter(Student.roll_number == current_user.username).first()
            if st:
                target_sid = st.id

        if student_id and target_sid and student_id != target_sid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students can only view their own attendance records."
            )
        query = query.filter(Attendance.student_id == target_sid)
        # Requirement 7: Absent records are shown ONLY after attendance has been finalized
        query = query.outerjoin(AttendanceSession, Attendance.session_id == AttendanceSession.id)
        query = query.filter(
            or_(
                Attendance.status != "absent",
                AttendanceSession.status.in_(["closed", "completed"])
            )
        )
    else:
        if student_id:
            query = query.filter(Attendance.student_id == student_id)

    # 2. Teacher access control: teachers can only view attendance for their assigned classes
    if current_user.role in ("teacher", "faculty"):
        if subject and section:
            verify_teacher_class_access(current_user, db, subject=subject, section=section)
        elif not student_id:
            # If no specific filters, scope query to teacher's classes if timetable entries exist
            assigned = get_teacher_assigned_classes(current_user, db)
            if assigned:
                subj_names = {s[0] for s in assigned}
                sec_names = {s[1] for s in assigned}
                query = query.filter(Attendance.subject.in_(subj_names), Student.section.in_(sec_names))

    if date_val:
        query = query.filter(Attendance.date == date_val)
    if subject:
        query = query.filter(Attendance.subject.ilike(f"%{subject}%"))
    if section:
        query = query.filter(Student.section == section)
    if session_id:
        query = query.filter(Attendance.session_id == session_id)
    if status_val:
        query = query.filter(Attendance.status == status_val)

    total = query.count()
    records = query.order_by(desc(Attendance.date), desc(Attendance.time)).offset(skip).limit(limit).all()

    formatted_records = []
    for att, std in records:
        formatted_records.append(AttendanceDetail(
            id=att.id,
            student_id=std.id,
            roll_number=std.roll_number,
            student_name=std.name,
            section=std.section,
            subject=att.subject,
            date=str(att.date),
            time=str(att.time)[:8],
            status=att.status,
            confidence_score=att.confidence_score,
            session_id=att.session_id
        ))

    return AttendanceHistoryResponse(total=total, records=formatted_records)

@router.post("/manual", response_model=AttendanceSimple)
def mark_manual_attendance(
    manual_in: ManualAttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot mark manual attendance."
        )

    student = db.query(Student).filter(Student.id == manual_in.student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    # If teacher, verify class access
    if current_user.role in ("teacher", "faculty"):
        verify_teacher_class_access(
            current_user=current_user,
            db=db,
            subject=manual_in.subject,
            section=student.section,
            session_id=manual_in.session_id
        )

    target_date = manual_in.date or datetime.date.today()

    # Check enrollment validity (Requirement 7: Expired enrollment must not authorize attendance)
    is_valid, msg = check_student_enrollment_validity(student.id, db, target_date)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Attendance cannot be authorized: {msg}. Enrollment renewal required."
        )
    
    # Check if duplicate in session if session_id is provided

    if manual_in.session_id:
        sess = db.query(AttendanceSession).filter(AttendanceSession.id == manual_in.session_id).first()
        if sess and sess.status in ("closed", "completed"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Attendance cannot be recorded: Session #{sess.id} is already closed."
            )

        existing = db.query(Attendance).filter(
            Attendance.student_id == student.id,
            Attendance.session_id == manual_in.session_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Attendance already marked for {student.name} in this session."
            )

    att = Attendance(
        student_id=student.id,
        session_id=manual_in.session_id,
        subject=manual_in.subject.strip(),
        date=target_date,
        time=datetime.datetime.now().time(),
        status=manual_in.status.lower(),
        confidence_score=None
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att

@router.delete("/{attendance_id}")
def delete_attendance_record(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    record = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")
    
    db.delete(record)
    db.commit()
    return {"success": True, "message": "Attendance record deleted successfully"}

