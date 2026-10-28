import datetime as dt
from datetime import datetime, timezone, date, time
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_, func

from app.database import get_db
from app.models.attendance_session import AttendanceSession
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.user import User
from app.models.timetable import TimetableEntry
from app.models.substitute_auth import SubstituteAuthorization
from app.models.subject import Subject
from app.models.semester import Semester
from app.models.academic_year import AcademicYear
from app.schemas.session import (
    SessionCreate,
    SessionOut,
    AuthorizedSessionStartRequest,
    SessionCloseRequest,
    SessionFinalizeRequest,
    SessionFinalizeOut,
    TeacherSlotOut
)
from app.auth.deps import (
    get_current_user,
    get_current_admin,
    verify_teacher_class_access,
    get_teacher_assigned_classes,
)
from app.services.session_service import (
    create_authorized_session,
    close_session_with_audit,
    format_session_out,
    time_to_minutes,
    log_audit_event
)

router = APIRouter(prefix="/sessions", tags=["Attendance Sessions"])


@router.post("/authorized-start", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start_authorized_session_endpoint(
    payload: AuthorizedSessionStartRequest,
    request: Request,
    simulated_date: Optional[date] = Query(None, alias="date", description="Override date for testing calendar logic"),
    simulated_time_str: Optional[str] = Query(None, alias="time", description="Override time (HH:MM) for testing slot logic"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Phase 5 Core Requirement:
    - Teacher selects an assigned timetable slot or class.
    - Backend validates current timetable slot and teacher assignment.
    - Teacher MUST pass live camera registered-face verification.
    - Creates attendance session linked to timetable slot, teacher, subject, semester, section, and academic year.
    - Records start time with server clock and establishes 15-minute deadline.
    - Prevents unauthorized teachers and duplicate active sessions.
    - Records comprehensive audit trail.
    """
    client_ip = request.client.host if request.client else None

    simulated_time = None
    if simulated_time_str:
        try:
            parts = [int(p) for p in simulated_time_str.split(":")[:2]]
            simulated_time = time(hour=parts[0], minute=parts[1])
        except Exception:
            simulated_time = None

    session = create_authorized_session(
        current_user=current_user,
        face_image_b64=payload.face_image,
        db=db,
        timetable_entry_id=payload.timetable_entry_id,
        subject=payload.subject,
        section=payload.section,
        simulated_date=simulated_date,
        simulated_time=simulated_time,
        ip_address=client_ip
    )

    return format_session_out(session, db)


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start_session(
    session_in: SessionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Standard / backward-compatible session initiation endpoint:
    - If face_image is provided, runs full biometric verification.
    - If timetable_entry_id is provided, enforces timetable slot and teacher authorization.
    - If student: 403 Forbidden.
    """
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot manage attendance sessions."
        )

    client_ip = request.client.host if request.client else None

    # If teacher provided face image or timetable slot, route to authorized session logic
    if session_in.face_image or session_in.timetable_entry_id:
        session = create_authorized_session(
            current_user=current_user,
            face_image_b64=session_in.face_image,
            db=db,
            timetable_entry_id=session_in.timetable_entry_id,
            subject=session_in.subject,
            section=session_in.section,
            ip_address=client_ip
        )
        return format_session_out(session, db)

    # Enforce teacher class assignment for legacy creation
    verify_teacher_class_access(
        current_user=current_user,
        db=db,
        subject=session_in.subject,
        section=session_in.section
    )

    # Auto-complete any existing active session for backward compatibility
    existing_active = db.query(AttendanceSession).filter(
        AttendanceSession.status == "active"
    ).first()

    if existing_active:
        existing_active.status = "closed"
        existing_active.ended_at = datetime.now(timezone.utc)

    now_utc = datetime.now(timezone.utc)
    new_session = AttendanceSession(
        subject=session_in.subject.strip(),
        section=session_in.section.strip().upper(),
        started_at=now_utc,
        created_by=current_user.id,
        teacher_id=current_user.id if current_user.role in ("teacher", "faculty") else None,
        timetable_entry_id=session_in.timetable_entry_id,
        semester_id=session_in.semester_id,
        recognition_window_end=now_utc + dt.timedelta(minutes=15),
        status="active"
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return format_session_out(new_session, db)


@router.get("/teacher/assigned-slots", response_model=List[TeacherSlotOut])
def get_teacher_assigned_slots(
    target_date: Optional[date] = Query(None, alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the scheduled timetable slots for the authenticated teacher for a particular date (defaults to today).
    Includes direct instructor assignments and authorized substitute assignments.
    """
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot inspect teacher timetable schedules."
        )

    eval_date = target_date or date.today()
    eval_dow = eval_date.weekday()
    now_time = datetime.now().time()
    now_mins = time_to_minutes(now_time)

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    # 1. Direct assignments (Active slots only)
    if current_user.role == "admin":
        direct_slots = db.query(TimetableEntry).filter(
            TimetableEntry.is_active == True,
            TimetableEntry.day_of_week == eval_dow
        ).all()
    else:
        direct_slots = db.query(TimetableEntry).filter(
            TimetableEntry.is_active == True,
            TimetableEntry.teacher_id == current_user.id,
            TimetableEntry.day_of_week == eval_dow
        ).all()

    # 2. Substitute assignments (Active slots only)
    sub_auths = db.query(SubstituteAuthorization).filter(
        SubstituteAuthorization.substitute_teacher_id == current_user.id,
        SubstituteAuthorization.date == eval_date,
        SubstituteAuthorization.status.in_(["authorized", "active"])
    ).all()

    sub_slot_ids = {sa.timetable_entry_id: sa for sa in sub_auths}
    sub_slots = db.query(TimetableEntry).filter(
        TimetableEntry.id.in_(list(sub_slot_ids.keys())),
        TimetableEntry.is_active == True
    ).all() if sub_slot_ids else []

    all_slots_map = {}
    for slot in direct_slots:
        all_slots_map[slot.id] = (slot, False, None)

    for slot in sub_slots:
        sa = sub_slot_ids.get(slot.id)
        orig_user = db.query(User).filter(User.id == slot.teacher_id).first()
        orig_name = orig_user.full_name or orig_user.username if orig_user else None
        all_slots_map[slot.id] = (slot, True, orig_name)

    results: List[TeacherSlotOut] = []
    for slot_id, (slot, is_sub, orig_name) in all_slots_map.items():
        s_mins = time_to_minutes(slot.start_time)
        e_mins = time_to_minutes(slot.end_time)

        # Slot time status
        if now_mins < (s_mins - 15):
            time_status = "upcoming"
            can_start = False
        elif now_mins > e_mins:
            time_status = "passed"
            can_start = False
        else:
            time_status = "open"
            can_start = True

        sem_name = slot.semester.name if slot.semester else "Unknown Semester"
        ay_name = slot.semester.academic_year.name if (slot.semester and slot.semester.academic_year) else "Current Year"
        ay_id = slot.semester.academic_year_id if (slot.semester and slot.semester.academic_year_id) else 1

        results.append(TeacherSlotOut(
            timetable_entry_id=slot.id,
            subject_id=slot.subject_id,
            subject_code=slot.subject.code if slot.subject else "SUB",
            subject_name=slot.subject.name if slot.subject else str(slot.subject_id),
            semester_id=slot.semester_id,
            semester_name=sem_name,
            academic_year_id=ay_id,
            academic_year_name=ay_name,
            section=slot.section,
            day_of_week=slot.day_of_week,
            day_name=day_names[slot.day_of_week],
            period_number=slot.period_number,
            start_time=slot.start_time.strftime("%H:%M"),
            end_time=slot.end_time.strftime("%H:%M"),
            is_substitute=is_sub,
            original_teacher_name=orig_name,
            can_start_now=can_start,
            time_status=time_status
        ))

    results.sort(key=lambda r: (r.period_number, r.start_time))
    return results


@router.get("/active", response_model=Optional[SessionOut])
def get_active_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """View the currently active session (Admin and Teacher only)."""
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot inspect session controls."
        )

    query = db.query(AttendanceSession).filter(AttendanceSession.status == "active")

    session = query.order_by(desc(AttendanceSession.started_at)).first()
    if not session:
        return None

    if current_user.role in ("teacher", "faculty"):
        if session.created_by != current_user.id and session.teacher_id != current_user.id:
            assigned = get_teacher_assigned_classes(current_user, db)
            if assigned and (session.subject.upper(), session.section.upper()) not in assigned:
                return None

    return format_session_out(session, db)


@router.post("/{session_id}/close", response_model=SessionOut)
def close_session_endpoint(
    session_id: int,
    payload: Optional[SessionCloseRequest] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Requirement 8 & 9: Close an attendance session.
    - Transitions session state to 'closed' or 'review-required'.
    - Records server timestamp and audit event.
    """
    client_ip = request.client.host if request and request.client else None
    reason = payload.reason if payload else None
    require_review = payload.require_review if payload else False

    session = close_session_with_audit(
        session_id=session_id,
        current_user=current_user,
        db=db,
        reason=reason,
        require_review=require_review,
        ip_address=client_ip
    )
    return format_session_out(session, db)


@router.post("/{session_id}/flag-review", response_model=SessionOut)
def flag_session_review_endpoint(
    session_id: int,
    payload: SessionCloseRequest,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Requirement 8 & 9: Flag an attendance session as 'review-required'
    with reason/remarks and audit log.
    """
    client_ip = request.client.host if request and request.client else None
    session = close_session_with_audit(
        session_id=session_id,
        current_user=current_user,
        db=db,
        reason=payload.reason or "Flagged for administrative review",
        require_review=True,
        ip_address=client_ip
    )
    return format_session_out(session, db)


@router.post("/{session_id}/finalize", response_model=SessionFinalizeOut)
def finalize_session_endpoint(
    session_id: int,
    payload: Optional[SessionFinalizeRequest] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Phase 7 Requirements 6 & 7:
    - Finalize attendance after the session deadline using valid timetable and session records.
    - If camera failure or technical problems occurred, flags session as 'review-required'
      without automatically penalizing students with absences.
    - If normal finalization: marks unrecorded enrolled students in the section as absent.
    - Requires session ownership (assigned teacher, authorized substitute, or administrator).
    - Maintains comprehensive audit trail.
    """
    client_ip = request.client.host if request and request.client else None

    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot finalize attendance sessions."
        )

    session = db.query(AttendanceSession).filter(AttendanceSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance session not found.")

    # Authorization verification: Admin, session creator, assigned teacher, or authorized substitute
    if current_user.role != "admin":
        is_owner = (session.created_by == current_user.id or session.teacher_id == current_user.id)
        if not is_owner:
            sub_auth = None
            if session.timetable_entry_id:
                sub_auth = db.query(SubstituteAuthorization).filter(
                    SubstituteAuthorization.timetable_entry_id == session.timetable_entry_id,
                    SubstituteAuthorization.substitute_teacher_id == current_user.id,
                    SubstituteAuthorization.date == (session.started_at.date() if session.started_at else date.today()),
                    SubstituteAuthorization.status.in_(["authorized", "active", "used"])
                ).first()
            if not sub_auth:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Only the authorized instructor or administrator can finalize this session."
                )

    if session.status in ("closed", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session #{session_id} is already finalized/closed."
        )

    now_utc = datetime.now(timezone.utc)
    is_technical_issue = bool(payload and (payload.camera_failed or payload.technical_issue))
    tech_reason = (payload.reason or payload.notes or "Technical problem or camera failure during attendance window") if payload else "Technical problem"

    # Query all eligible students belonging to session section
    eligible_students_query = db.query(Student).filter(Student.is_active == True)
    if session.section:
        eligible_students_query = eligible_students_query.filter(
            func.trim(func.upper(Student.section)) == session.section.strip().upper()
        )
    eligible_students = eligible_students_query.all()
    total_eligible = len(eligible_students)

    if is_technical_issue:
        # Requirement 7: Handle camera failures and technical problems using a review-required state
        # rather than automatically penalizing students with absences!
        session.status = "review-required"
        session.ended_at = now_utc
        session.review_reason = tech_reason.strip()
        db.commit()
        db.refresh(session)

        present_count = db.query(Attendance).filter(
            Attendance.session_id == session.id,
            Attendance.status == "present"
        ).count()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            action="FLAG_SESSION_TECHNICAL_REVIEW",
            entity_type="session",
            entity_id=session.id,
            details={
                "subject": session.subject,
                "section": session.section,
                "review_reason": session.review_reason,
                "camera_failed": payload.camera_failed if payload else False,
                "technical_issue": payload.technical_issue if payload else False,
                "present_count": present_count,
                "students_penalized": False
            },
            ip_address=client_ip
        )

        return SessionFinalizeOut(
            session_id=session.id,
            status=session.status,
            present_count=present_count,
            absent_count=0,
            total_eligible_students=total_eligible,
            review_required=True,
            review_reason=session.review_reason,
            finalized_at=now_utc,
            message="Session flagged for review due to technical issue. Students are not penalized with absences."
        )

    # Normal finalization (Requirement 6):
    existing_records = db.query(Attendance).filter(Attendance.session_id == session.id).all()
    recorded_student_ids = {att.student_id for att in existing_records}

    session_date = session.started_at.date() if session.started_at else date.today()
    absent_time = datetime.now().time()
    new_absent_count = 0

    for student in eligible_students:
        if student.id not in recorded_student_ids:
            absent_record = Attendance(
                student_id=student.id,
                session_id=session.id,
                subject=session.subject,
                date=session_date,
                time=absent_time,
                status="absent",
                confidence_score=0.0
            )
            db.add(absent_record)
            new_absent_count += 1

    session.status = "closed"
    session.ended_at = now_utc
    if payload and payload.reason:
        session.review_reason = payload.reason.strip()
    db.commit()
    db.refresh(session)

    present_count = db.query(Attendance).filter(
        Attendance.session_id == session.id,
        Attendance.status == "present"
    ).count()

    absent_count = db.query(Attendance).filter(
        Attendance.session_id == session.id,
        Attendance.status == "absent"
    ).count()

    log_audit_event(
        db=db,
        user_id=current_user.id,
        action="FINALIZE_SESSION_ATTENDANCE",
        entity_type="session",
        entity_id=session.id,
        details={
            "subject": session.subject,
            "section": session.section,
            "present_count": present_count,
            "absent_count": absent_count,
            "newly_marked_absent": new_absent_count,
            "total_eligible_students": total_eligible,
            "finalized_at": now_utc.isoformat()
        },
        ip_address=client_ip
    )

    return SessionFinalizeOut(
        session_id=session.id,
        status=session.status,
        present_count=present_count,
        absent_count=absent_count,
        total_eligible_students=total_eligible,
        review_required=False,
        review_reason=session.review_reason,
        finalized_at=now_utc,
        message=f"Attendance finalized successfully. {present_count} present, {absent_count} absent."
    )


@router.post("/{session_id}/stop", response_model=SessionOut)
def stop_session(
    session_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Legacy endpoint: Stop/close an attendance session."""
    client_ip = request.client.host if request and request.client else None
    session = close_session_with_audit(
        session_id=session_id,
        current_user=current_user,
        db=db,
        ip_address=client_ip
    )
    # Legacy status compatibility for test_api
    session.status = "completed"
    db.commit()
    db.refresh(session)
    return format_session_out(session, db)


@router.get("/{session_id}/status", response_model=SessionOut)
def get_session_status(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the current state, 15-minute deadline countdown, and present count for a session."""
    session = db.query(AttendanceSession).filter(AttendanceSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    return format_session_out(session, db)


@router.get("", response_model=List[SessionOut])
def list_sessions(
    limit: int = 50,
    skip: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List sessions with role-based isolation."""
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot list lecture sessions."
        )

    query = db.query(AttendanceSession)

    if current_user.role in ("teacher", "faculty"):
        assigned = get_teacher_assigned_classes(current_user, db)
        if assigned:
            assigned_filters = [
                (AttendanceSession.subject == subj) & (AttendanceSession.section == sec)
                for subj, sec in assigned
            ]
            query = query.filter(
                or_(
                    AttendanceSession.created_by == current_user.id,
                    AttendanceSession.teacher_id == current_user.id,
                    *assigned_filters
                )
            )
        else:
            query = query.filter(
                or_(
                    AttendanceSession.created_by == current_user.id,
                    AttendanceSession.teacher_id == current_user.id
                )
            )

    sessions = query.order_by(desc(AttendanceSession.started_at)).offset(skip).limit(limit).all()
    return [format_session_out(s, db) for s in sessions]
