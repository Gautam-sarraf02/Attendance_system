import json
import logging
import datetime as dt
from datetime import datetime, timezone, timedelta, date, time
from typing import Optional, Tuple, Dict, Any, List
import cv2
import numpy as np
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models.attendance_session import AttendanceSession
from app.models.attendance import Attendance
from app.models.timetable import TimetableEntry, get_section_variants, normalize_section
from app.models.holiday import Holiday
from app.models.substitute_auth import SubstituteAuthorization
from app.models.face_enrollment import FaceEnrollment
from app.models.user import User
from app.models.subject import Subject
from app.models.semester import Semester
from app.models.academic_year import AcademicYear
from app.models.audit_log import AuditLog
from app.face.detector import detector
from app.face.storage import storage
from app.schemas.session import SessionOut, TeacherSlotOut

logger = logging.getLogger(__name__)


def time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def log_audit_event(
    db: Session,
    user_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    """Creates a secure audit record without sensitive biometric or password data."""
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details or {}),
        ip_address=ip_address,
        created_at=datetime.now(timezone.utc)
    )
    db.add(log)
    try:
        db.commit()
        db.refresh(log)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to record audit log: {e}")
    return log


def verify_teacher_biometrics(
    teacher: User,
    face_image_b64: Optional[str],
    db: Session,
    ip_address: Optional[str] = None
) -> Tuple[bool, float, str]:
    """
    Validates teacher's active face enrollment and verifies live camera capture against stored templates.
    Enforces Requirement 3, 6, 10.
    """
    today = date.today()

    # 1. Check for registered face enrollment
    enrollment = db.query(FaceEnrollment).filter(
        FaceEnrollment.user_id == teacher.id,
        FaceEnrollment.status == "active"
    ).first()

    if not enrollment:
        # Check if there is an expired or revoked enrollment to provide precise diagnostic
        any_enrollment = db.query(FaceEnrollment).filter(
            FaceEnrollment.user_id == teacher.id
        ).order_by(FaceEnrollment.created_at.desc()).first()

        if any_enrollment and (any_enrollment.status == "expired" or any_enrollment.valid_until < today):
            log_audit_event(
                db, teacher.id, "TEACHER_FACE_VERIFICATION_FAILURE", "user", teacher.id,
                {"reason": "Enrollment expired", "valid_until": str(any_enrollment.valid_until)},
                ip_address
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Instructor biometric face enrollment expired on {any_enrollment.valid_until}. Please contact Admin to renew enrollment."
            )
        elif any_enrollment and any_enrollment.status != "active":
            log_audit_event(
                db, teacher.id, "TEACHER_FACE_VERIFICATION_FAILURE", "user", teacher.id,
                {"reason": f"Enrollment {any_enrollment.status}"},
                ip_address
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Instructor biometric face enrollment is {any_enrollment.status}. Active enrollment is required to start sessions."
            )
        else:
            log_audit_event(
                db, teacher.id, "TEACHER_FACE_VERIFICATION_FAILURE", "user", teacher.id,
                {"reason": "No enrollment record"},
                ip_address
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Instructor has no registered face biometrics. Please register biometrics in the Admin portal before starting sessions."
            )

    # Enforce current date within validity period
    if enrollment.valid_until < today:
        log_audit_event(
            db, teacher.id, "TEACHER_FACE_VERIFICATION_FAILURE", "user", teacher.id,
            {"reason": "Enrollment expired", "valid_until": str(enrollment.valid_until)},
            ip_address
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Instructor biometric enrollment validity expired on {enrollment.valid_until}. Renewal required."
        )

    # 2. Check stored templates on disk
    samples = storage.load_entity_samples(teacher.id, is_user=True)
    if not samples or len(samples) == 0:
        log_audit_event(
            db, teacher.id, "TEACHER_FACE_VERIFICATION_FAILURE", "user", teacher.id,
            {"reason": "No template files on disk"},
            ip_address
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Biometric template files missing from secure storage. Contact Admin to re-enroll biometrics."
        )

    # 3. Validate camera input safely (Requirement 10)
    if not face_image_b64 or not face_image_b64.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing live camera capture image. Live teacher face verification is required to start session."
        )

    try:
        cv_img = detector.decode_image_base64(face_image_b64)
    except Exception as e:
        logger.warning(f"Failed to decode face image: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Camera stream capture error: Unable to decode image buffer. Please ensure camera hardware is working."
        )

    # 4. Detect face
    try:
        boxes = detector.detect_faces(cv_img, min_neighbors=4)
    except Exception as e:
        logger.error(f"Detector error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Biometric face detector engine encountered an error."
        )

    if len(boxes) == 0:
        log_audit_event(
            db, teacher.id, "TEACHER_FACE_VERIFICATION_FAILURE", "user", teacher.id,
            {"reason": "No face detected"},
            ip_address
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Face verification failed: No face detected in camera frame. Center your face with sufficient lighting."
        )

    if len(boxes) > 1:
        log_audit_event(
            db, teacher.id, "TEACHER_FACE_VERIFICATION_FAILURE", "user", teacher.id,
            {"reason": "Multiple faces detected", "count": len(boxes)},
            ip_address
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Face verification failed: Multiple faces ({len(boxes)}) detected in camera frame. Only the instructor must be present."
        )

    # 5. Extract normalized face ROI
    norm_face = detector.extract_and_normalize_face(cv_img, boxes[0])

    # 5b. Anti-Spoofing & Liveness Verification (blocks photos, screens, replays)
    is_live, liveness_score, liveness_msg = detector.evaluate_liveness(
        face_roi=norm_face,
        full_image=cv_img,
        bbox=boxes[0]
    )
    if not is_live:
        log_audit_event(
            db, teacher.id, "TEACHER_FACE_VERIFICATION_FAILURE", "user", teacher.id,
            {"reason": f"Anti-spoofing check failed: {liveness_msg}", "score": liveness_score},
            ip_address
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Biometric face verification failed: Anti-spoofing check failed ({liveness_msg}). Please present a live face to the camera."
        )

    # 6. Biometric template matching
    # Multi-method comparison: LBPH model + cross-correlation template matching
    try:
        rec = cv2.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
        rec.train(samples, np.array([teacher.id] * len(samples), dtype=np.int32))
        pred_id, dist = rec.predict(norm_face)
        dist = round(float(dist), 2)
    except Exception as e:
        logger.error(f"LBPH verification error: {e}")
        dist = 999.0

    # Cross-correlation with stored template samples
    correlations = []
    for s in samples:
        try:
            res = cv2.matchTemplate(norm_face, s, cv2.TM_CCOEFF_NORMED)
            correlations.append(float(res[0][0]))
        except Exception:
            pass

    max_corr = round(max(correlations), 3) if correlations else 0.0

    # Verification threshold: LBPH must match teacher identity with distance <= 75.0
    is_match = (pred_id == teacher.id and dist <= 75.0)

    if not is_match:
        log_audit_event(
            db, teacher.id, "TEACHER_FACE_VERIFICATION_FAILURE", "user", teacher.id,
            {"distance": dist, "correlation": max_corr, "reason": "Biometric threshold not met"},
            ip_address
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Biometric face verification failed: Face does not match registered instructor profile (similarity distance: {dist})."
        )

    log_audit_event(
        db, teacher.id, "TEACHER_FACE_VERIFICATION_SUCCESS", "user", teacher.id,
        {"distance": dist, "correlation": max_corr},
        ip_address
    )
    return True, dist, f"Verified (dist: {dist}, corr: {max_corr})"


def validate_session_slot_and_teacher(
    current_user: User,
    db: Session,
    timetable_entry_id: Optional[int] = None,
    subject: Optional[str] = None,
    section: Optional[str] = None,
    simulated_date: Optional[date] = None,
    simulated_time: Optional[time] = None
) -> Tuple[TimetableEntry, bool, Optional[str]]:
    """
    Validates:
    - Teacher assignment (assigned teacher or authorized substitute).
    - Current timetable slot, day of week, and time window.
    - Holiday calendar and non-instructional days.
    - Prevents duplicate active sessions.
    Returns: (timetable_entry, is_substitute, original_teacher_name)
    """
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot manage or initiate attendance sessions."
        )

    today = simulated_date or date.today()
    current_t = simulated_time or datetime.now().time()
    today_dow = today.weekday()

    # 1. Holiday Check (Requirement 9)
    holiday = db.query(Holiday).filter(Holiday.date == today).first()
    if holiday:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start session on scheduled holiday: '{holiday.name}'."
        )

    # 2. Sunday / Non-working day Check
    if today_dow == 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot start attendance session on non-working day (Sunday)."
        )

    # 3. Locate Timetable Entry
    slot: Optional[TimetableEntry] = None
    cur_mins = time_to_minutes(current_t)

    if timetable_entry_id:
        slot = db.query(TimetableEntry).filter(TimetableEntry.id == timetable_entry_id).first()
        if not slot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Timetable slot #{timetable_entry_id} not found."
            )

        # If slot is inactive, check if a valid active entry exists for the same scheduled class
        if not getattr(slot, 'is_active', True):
            sec_vars = get_section_variants(slot.section)
            # Prioritize active replacement on today_dow
            active_replacements = db.query(TimetableEntry).filter(
                TimetableEntry.is_active == True,
                TimetableEntry.subject_id == slot.subject_id,
                TimetableEntry.section.in_(sec_vars),
                TimetableEntry.day_of_week == today_dow
            ).all()

            if not active_replacements:
                active_replacements = db.query(TimetableEntry).filter(
                    TimetableEntry.is_active == True,
                    TimetableEntry.subject_id == slot.subject_id,
                    TimetableEntry.section.in_(sec_vars),
                    TimetableEntry.day_of_week == slot.day_of_week
                ).all()

            replacement: Optional[TimetableEntry] = None
            if active_replacements:
                if current_user.role != "admin":
                    teacher_reps = [
                        r for r in active_replacements
                        if r.teacher_id == current_user.id or db.query(SubstituteAuthorization).filter(
                            SubstituteAuthorization.timetable_entry_id == r.id,
                            SubstituteAuthorization.substitute_teacher_id == current_user.id,
                            SubstituteAuthorization.date == today,
                            SubstituteAuthorization.status.in_(["authorized", "active"])
                        ).first() is not None
                    ]
                    candidates = teacher_reps if teacher_reps else active_replacements
                else:
                    candidates = active_replacements

                # Match period or current time window
                for c in candidates:
                    s_m = time_to_minutes(c.start_time)
                    e_m = time_to_minutes(c.end_time)
                    if (s_m - 15) <= cur_mins <= e_m or c.period_number == slot.period_number:
                        replacement = c
                        break
                if not replacement and candidates:
                    replacement = candidates[0]

            if replacement:
                slot = replacement
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Timetable slot #{slot.id} ({slot.section} - {slot.subject.name if slot.subject else 'Slot'}) is inactive/archived and cannot authorize new attendance sessions."
                )

    elif subject and section:
        norm_subj = subject.strip()
        sec_vars = get_section_variants(section)

        # 1. Search for active slots for today matching subject and section variants
        active_slots_today = db.query(TimetableEntry).join(Subject).filter(
            TimetableEntry.is_active == True,
            TimetableEntry.section.in_(sec_vars),
            TimetableEntry.day_of_week == today_dow,
            or_(
                Subject.name.ilike(norm_subj),
                Subject.code.ilike(norm_subj)
            )
        ).all()

        if active_slots_today:
            # If current_user is faculty/teacher (not admin), filter/prioritize matching instructor
            if current_user.role != "admin":
                assigned_active = [
                    s for s in active_slots_today
                    if s.teacher_id == current_user.id or db.query(SubstituteAuthorization).filter(
                        SubstituteAuthorization.timetable_entry_id == s.id,
                        SubstituteAuthorization.substitute_teacher_id == current_user.id,
                        SubstituteAuthorization.date == today,
                        SubstituteAuthorization.status.in_(["authorized", "active"])
                    ).first() is not None
                ]
                candidates = assigned_active if assigned_active else active_slots_today
            else:
                candidates = active_slots_today

            # Pick candidate whose time window fits current_t (start - 15 mins <= current_t <= end)
            time_matching = [
                c for c in candidates
                if (time_to_minutes(c.start_time) - 15) <= cur_mins <= time_to_minutes(c.end_time)
            ]
            if time_matching:
                slot = time_matching[0]
            else:
                slot = candidates[0]

        else:
            # No active slot found for today. Check if an active slot exists on another day
            other_day_active = db.query(TimetableEntry).join(Subject).filter(
                TimetableEntry.is_active == True,
                TimetableEntry.section.in_(sec_vars),
                or_(
                    Subject.name.ilike(norm_subj),
                    Subject.code.ilike(norm_subj)
                )
            ).first()

            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            if other_day_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Scheduled day mismatch: {subject} (Section {section}) is scheduled on {day_names[other_day_active.day_of_week]}, but today is {day_names[today_dow]}."
                )

            # Check if only archived slots exist
            archived_slot = db.query(TimetableEntry).join(Subject).filter(
                TimetableEntry.is_active == False,
                TimetableEntry.section.in_(sec_vars),
                or_(
                    Subject.name.ilike(norm_subj),
                    Subject.code.ilike(norm_subj)
                )
            ).first()

            if archived_slot:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Timetable slot #{archived_slot.id} ({archived_slot.section} - {archived_slot.subject.name if archived_slot.subject else 'Slot'}) is inactive/archived and cannot authorize new attendance sessions."
                )

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No timetable entry found for {subject} ({section})."
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please specify either timetable_entry_id or both subject and section."
        )

    # 3b. Verify slot is active (not obsolete or archived)
    if not getattr(slot, 'is_active', True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Timetable slot #{slot.id} ({slot.section} - {slot.subject.name if slot.subject else 'Slot'}) is inactive/archived and cannot authorize new attendance sessions."
        )

    # 4. Validate Teacher Assignment & Substitute Authorization (Requirement 2, 6)
    is_substitute = False
    original_teacher_name = None

    if current_user.role != "admin":
        is_assigned_teacher = (slot.teacher_id == current_user.id)
        if not is_assigned_teacher:
            # Check for active substitute authorization
            sub_auth = db.query(SubstituteAuthorization).filter(
                SubstituteAuthorization.timetable_entry_id == slot.id,
                SubstituteAuthorization.substitute_teacher_id == current_user.id,
                SubstituteAuthorization.date == today,
                SubstituteAuthorization.status.in_(["authorized", "active"])
            ).first()

            if sub_auth:
                is_substitute = True
                orig_teacher = db.query(User).filter(User.id == slot.teacher_id).first()
                original_teacher_name = orig_teacher.full_name or orig_teacher.username if orig_teacher else "Assigned Teacher"
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Unauthorized instructor: You are not assigned to teach {slot.subject.name} (Section {slot.section}) and have no substitute authorization for today."
                )

    # 5. Validate Day of Week (Requirement 2)
    if slot.day_of_week != today_dow:
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scheduled day mismatch: This slot is scheduled on {day_names[slot.day_of_week]}, but today is {day_names[today_dow]}."
        )

    # 6. Validate Time Slot Window (Requirement 2)
    cur_mins = time_to_minutes(current_t)
    start_mins = time_to_minutes(slot.start_time)
    end_mins = time_to_minutes(slot.end_time)

    if cur_mins < (start_mins - 15) or cur_mins > end_mins:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Time slot mismatch: Class is scheduled for {slot.start_time.strftime('%H:%M')} - "
                f"{slot.end_time.strftime('%H:%M')}. Current time {current_t.strftime('%H:%M')} is outside "
                f"the permitted window (available 15 mins prior until slot end)."
            )
        )

    # 7. Prevent Duplicate Active Session on Same Timetable Slot (Requirement 7)
    existing_slot_session = db.query(AttendanceSession).filter(
        AttendanceSession.timetable_entry_id == slot.id,
        AttendanceSession.status == "active"
    ).first()

    if existing_slot_session:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active attendance session is already open for this timetable slot (Session #{existing_slot_session.id})."
        )

    # 8. Prevent Instructor from Having Multiple Concurrent Active Sessions (Requirement 7)
    if current_user.role != "admin":
        existing_teacher_session = db.query(AttendanceSession).filter(
            AttendanceSession.teacher_id == current_user.id,
            AttendanceSession.status == "active"
        ).first()

        if existing_teacher_session:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Instructor already has an active session (Session #{existing_teacher_session.id} for {existing_teacher_session.subject}). Please close it before starting a new session."
            )

    return slot, is_substitute, original_teacher_name


def create_authorized_session(
    current_user: User,
    face_image_b64: Optional[str],
    db: Session,
    timetable_entry_id: Optional[int] = None,
    subject: Optional[str] = None,
    section: Optional[str] = None,
    simulated_date: Optional[date] = None,
    simulated_time: Optional[time] = None,
    ip_address: Optional[str] = None
) -> AttendanceSession:
    """
    Orchestrates Requirements 1-8:
    1. Validates teacher assignment and timetable slot.
    2. Enforces teacher face verification before session can start.
    3. Links session to timetable entry, teacher, subject, semester, section, and academic year.
    4. Sets server start time and 15-minute deadline.
    5. Prevents duplicate active sessions.
    6. Logs audit trail.
    """
    slot, is_substitute, orig_teacher_name = validate_session_slot_and_teacher(
        current_user=current_user,
        db=db,
        timetable_entry_id=timetable_entry_id,
        subject=subject,
        section=section,
        simulated_date=simulated_date,
        simulated_time=simulated_time
    )

    if current_user.role in ("teacher", "faculty") or face_image_b64:
        verify_teacher_biometrics(current_user, face_image_b64, db, ip_address)

    now_utc = datetime.now(timezone.utc)
    deadline_utc = now_utc + timedelta(minutes=15)

    academic_year_id = None
    if slot.semester and slot.semester.academic_year_id:
        academic_year_id = slot.semester.academic_year_id
    else:
        curr_ay = db.query(AcademicYear).filter(AcademicYear.is_current == True).first()
        academic_year_id = curr_ay.id if curr_ay else None

    new_session = AttendanceSession(
        subject=slot.subject.name if slot.subject else (subject or "Subject"),
        section=slot.section,
        started_at=now_utc,
        created_by=current_user.id,
        teacher_id=current_user.id if current_user.role in ("teacher", "faculty") else slot.teacher_id,
        timetable_entry_id=slot.id,
        semester_id=slot.semester_id,
        subject_id=slot.subject_id,
        academic_year_id=academic_year_id,
        recognition_window_end=deadline_utc,
        status="active"
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    log_audit_event(
        db=db,
        user_id=current_user.id,
        action="START_AUTHORIZED_SESSION",
        entity_type="session",
        entity_id=new_session.id,
        details={
            "timetable_entry_id": slot.id,
            "subject": new_session.subject,
            "section": new_session.section,
            "is_substitute": is_substitute,
            "original_teacher": orig_teacher_name,
            "started_at": now_utc.isoformat(),
            "deadline_window_minutes": 15
        },
        ip_address=ip_address
    )

    return new_session


def close_session_with_audit(
    session_id: int,
    current_user: User,
    db: Session,
    reason: Optional[str] = None,
    require_review: bool = False,
    ip_address: Optional[str] = None
) -> AttendanceSession:
    """
    Implements session closure and audit logging (Requirement 8, 9).
    Supports states: 'closed', 'review-required'.
    """
    session = db.query(AttendanceSession).filter(AttendanceSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance session not found.")

    if current_user.role != "admin" and session.created_by != current_user.id and session.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only terminate attendance sessions that you authorized."
        )

    if session.status in ("closed", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session #{session_id} is already closed."
        )

    now_utc = datetime.now(timezone.utc)
    new_status = "review-required" if require_review else "closed"

    session.status = new_status
    session.ended_at = now_utc
    if reason:
        session.review_reason = reason.strip()

    db.commit()
    db.refresh(session)

    present_count = db.query(Attendance).filter(
        Attendance.session_id == session.id,
        Attendance.status == "present"
    ).count()

    action_name = "FLAG_SESSION_REVIEW" if require_review else "CLOSE_SESSION"
    log_audit_event(
        db=db,
        user_id=current_user.id,
        action=action_name,
        entity_type="session",
        entity_id=session.id,
        details={
            "subject": session.subject,
            "section": session.section,
            "new_status": new_status,
            "review_reason": session.review_reason,
            "total_present": present_count,
            "duration_seconds": round((now_utc - session.started_at.replace(tzinfo=timezone.utc if session.started_at.tzinfo is None else session.started_at.tzinfo)).total_seconds(), 1)
        },
        ip_address=ip_address
    )

    return session


def format_session_out(session: AttendanceSession, db: Session) -> SessionOut:
    """Enriches AttendanceSession entity into SessionOut schema with deadline information."""
    present_count = db.query(Attendance).filter(
        Attendance.session_id == session.id,
        Attendance.status == "present"
    ).count()

    now_utc = datetime.now(timezone.utc)
    remaining_secs = None
    is_deadline_passed = False

    if session.recognition_window_end:
        rw_end = session.recognition_window_end
        if rw_end.tzinfo is None:
            rw_end = rw_end.replace(tzinfo=timezone.utc)
        diff = (rw_end - now_utc).total_seconds()
        remaining_secs = max(0, int(diff))
        is_deadline_passed = (diff <= 0)

    teacher_name = None
    if session.teacher:
        teacher_name = session.teacher.full_name or session.teacher.username

    return SessionOut(
        id=session.id,
        subject=session.subject,
        section=session.section,
        started_at=session.started_at,
        ended_at=session.ended_at,
        created_by=session.created_by,
        status=session.status,
        total_present=present_count,
        teacher_id=session.teacher_id,
        teacher_name=teacher_name,
        timetable_entry_id=session.timetable_entry_id,
        semester_id=session.semester_id,
        subject_id=session.subject_id,
        academic_year_id=session.academic_year_id,
        recognition_window_end=session.recognition_window_end,
        review_reason=session.review_reason,
        is_deadline_passed=is_deadline_passed,
        remaining_deadline_seconds=remaining_secs
    )
