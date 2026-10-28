import json
import datetime
from datetime import timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.database import get_db
from app.models.attendance import Attendance
from app.models.attendance_session import AttendanceSession
from app.models.student import Student
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.attendance_correction import AttendanceCorrection
from app.schemas.correction import (
    AttendanceCorrectionCreate,
    AttendanceCorrectionReview,
    AttendanceCorrectionOut,
    AttendanceCorrectionListResponse,
)
from app.auth.deps import (
    get_current_user,
    get_current_admin,
    verify_teacher_class_access,
)

router = APIRouter(prefix="/attendance/corrections", tags=["Attendance Corrections"])


def format_correction_out(c: AttendanceCorrection) -> AttendanceCorrectionOut:
    """Helper to format correction with human-readable metadata."""
    std = c.student
    sess = c.session
    req_u = c.requester
    rev_u = c.reviewer

    return AttendanceCorrectionOut(
        id=c.id,
        session_id=c.session_id,
        student_id=c.student_id,
        attendance_id=c.attendance_id,
        requested_by=c.requested_by,
        requested_status=c.requested_status,
        previous_status=c.previous_status,
        reason=c.reason,
        evidence_notes=c.evidence_notes,
        status=c.status,
        reviewed_by=c.reviewed_by,
        reviewed_at=c.reviewed_at,
        review_notes=c.review_notes,
        created_at=c.created_at,
        updated_at=c.updated_at,
        student_name=std.name if std else None,
        roll_number=std.roll_number if std else None,
        section=std.section if std else None,
        subject=sess.subject if sess else None,
        requester_name=req_u.full_name or req_u.username if req_u else None,
        reviewer_name=rev_u.full_name or rev_u.username if rev_u else None,
    )


@router.post("", response_model=AttendanceCorrectionOut, status_code=status.HTTP_201_CREATED)
def request_attendance_correction(
    payload: AttendanceCorrectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit a controlled attendance correction request.
    Manual correction is an exceptional workflow that requires explicit reasons and administrative approval.
    """
    # 1. Verify Session & Student exist
    sess = db.query(AttendanceSession).filter(AttendanceSession.id == payload.session_id).first()
    if not sess:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Attendance session #{payload.session_id} not found.")

    student = db.query(Student).filter(Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student #{payload.student_id} not found.")

    # 2. Access control:
    # - Student can only request correction for their own account
    if current_user.role == "student":
        if current_user.student_id != payload.student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students can only request attendance corrections for themselves."
            )
    # - Teacher can only request for sessions they taught or are assigned
    elif current_user.role in ("teacher", "faculty"):
        if sess.teacher_id != current_user.id and sess.created_by != current_user.id:
            # Check class assignment access
            verify_teacher_class_access(current_user, db, subject=sess.subject, section=sess.section, session_id=sess.id)

    # 3. Check for existing pending request to avoid duplicates
    existing_pending = db.query(AttendanceCorrection).filter(
        AttendanceCorrection.session_id == payload.session_id,
        AttendanceCorrection.student_id == payload.student_id,
        AttendanceCorrection.status == "pending"
    ).first()
    if existing_pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pending correction request already exists for this student and session."
        )

    # 4. Check current attendance record status if exists
    att_rec = db.query(Attendance).filter(
        Attendance.session_id == payload.session_id,
        Attendance.student_id == payload.student_id
    ).first()
    previous_status = att_rec.status if att_rec else "unrecorded"
    att_id = att_rec.id if att_rec else payload.attendance_id

    # 5. Create correction record
    correction = AttendanceCorrection(
        session_id=payload.session_id,
        student_id=payload.student_id,
        attendance_id=att_id,
        requested_by=current_user.id,
        requested_status=payload.requested_status,
        previous_status=previous_status,
        reason=payload.reason.strip(),
        evidence_notes=payload.evidence_notes.strip() if payload.evidence_notes else None,
        status="pending"
    )
    db.add(correction)
    db.commit()
    db.refresh(correction)

    # 6. Audit logging for request
    log = AuditLog(
        user_id=current_user.id,
        action="REQUEST_ATTENDANCE_CORRECTION",
        entity_type="attendance_correction",
        entity_id=correction.id,
        details=json.dumps({
            "session_id": sess.id,
            "subject": sess.subject,
            "section": sess.section,
            "student_id": student.id,
            "student_name": student.name,
            "roll_number": student.roll_number,
            "requested_status": payload.requested_status,
            "previous_status": previous_status,
            "reason": payload.reason,
            "requested_by": current_user.username
        })
    )
    db.add(log)
    db.commit()

    return format_correction_out(correction)


@router.get("", response_model=AttendanceCorrectionListResponse)
def list_attendance_corrections(
    session_id: Optional[int] = None,
    student_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List attendance correction requests.
    - Admins see all requests.
    - Teachers see requests for their sessions.
    - Students see only their own requests.
    """
    query = db.query(AttendanceCorrection).join(AttendanceSession, AttendanceCorrection.session_id == AttendanceSession.id)

    if current_user.role == "student":
        query = query.filter(AttendanceCorrection.student_id == current_user.student_id)
    elif current_user.role in ("teacher", "faculty"):
        query = query.filter(
            or_(
                AttendanceCorrection.requested_by == current_user.id,
                AttendanceSession.teacher_id == current_user.id,
                AttendanceSession.created_by == current_user.id
            )
        )

    if session_id:
        query = query.filter(AttendanceCorrection.session_id == session_id)
    if student_id:
        query = query.filter(AttendanceCorrection.student_id == student_id)
    if status_filter:
        query = query.filter(AttendanceCorrection.status == status_filter)

    total = query.count()
    items = query.order_by(desc(AttendanceCorrection.created_at)).offset(skip).limit(limit).all()

    return AttendanceCorrectionListResponse(
        total=total,
        corrections=[format_correction_out(c) for c in items]
    )


@router.get("/{correction_id}", response_model=AttendanceCorrectionOut)
def get_attendance_correction_by_id(
    correction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    correction = db.query(AttendanceCorrection).filter(AttendanceCorrection.id == correction_id).first()
    if not correction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Correction request not found.")

    if current_user.role == "student" and correction.student_id != current_user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    return format_correction_out(correction)


@router.put("/{correction_id}/review", response_model=AttendanceCorrectionOut)
def review_attendance_correction(
    correction_id: int,
    review_in: AttendanceCorrectionReview,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """
    Controlled Review & Approval:
    - Only Administrator can approve or reject attendance corrections.
    - Every approval or rejection is permanently logged in the audit trail with reviewer, timestamp, and notes.
    - On approval, the underlying Attendance record is updated or inserted atomically.
    """
    correction = db.query(AttendanceCorrection).filter(AttendanceCorrection.id == correction_id).first()
    if not correction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Correction request not found.")

    if correction.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Correction request is already {correction.status}. Cannot re-review."
        )

    now_utc = datetime.datetime.now(timezone.utc)
    sess = correction.session
    student = correction.student

    if review_in.decision.lower() in ("approved", "approve"):
        # 1. Update or create the attendance record
        att_rec = db.query(Attendance).filter(
            Attendance.session_id == correction.session_id,
            Attendance.student_id == correction.student_id
        ).first()

        if att_rec:
            correction.previous_status = att_rec.status
            att_rec.status = correction.requested_status
        else:
            correction.previous_status = "unrecorded"
            att_date = sess.started_at.date() if hasattr(sess.started_at, 'date') else datetime.date.today()
            att_rec = Attendance(
                student_id=correction.student_id,
                session_id=correction.session_id,
                subject=sess.subject,
                date=att_date,
                time=datetime.datetime.now().time(),
                status=correction.requested_status,
                confidence_score=None
            )
            db.add(att_rec)
            db.flush()

        correction.attendance_id = att_rec.id
        correction.status = "approved"
        correction.reviewed_by = current_admin.id
        correction.reviewed_at = now_utc
        correction.review_notes = review_in.review_notes.strip()

        db.commit()
        db.refresh(correction)

        # 2. Strict audit logging of approval
        log = AuditLog(
            user_id=current_admin.id,
            action="APPROVE_ATTENDANCE_CORRECTION",
            entity_type="attendance_correction",
            entity_id=correction.id,
            details=json.dumps({
                "correction_id": correction.id,
                "session_id": correction.session_id,
                "student_id": student.id,
                "student_name": student.name,
                "roll_number": student.roll_number,
                "new_status": correction.requested_status,
                "previous_status": correction.previous_status,
                "approved_by_id": current_admin.id,
                "approved_by_username": current_admin.username,
                "approved_at": now_utc.isoformat(),
                "review_notes": review_in.review_notes,
                "request_reason": correction.reason
            })
        )
        db.add(log)
        db.commit()

    elif review_in.decision == "rejected":
        correction.status = "rejected"
        correction.reviewed_by = current_admin.id
        correction.reviewed_at = now_utc
        correction.review_notes = review_in.review_notes.strip()

        db.commit()
        db.refresh(correction)

        # Audit logging of rejection
        log = AuditLog(
            user_id=current_admin.id,
            action="REJECT_ATTENDANCE_CORRECTION",
            entity_type="attendance_correction",
            entity_id=correction.id,
            details=json.dumps({
                "correction_id": correction.id,
                "session_id": correction.session_id,
                "student_id": student.id,
                "student_name": student.name,
                "roll_number": student.roll_number,
                "rejected_by_id": current_admin.id,
                "rejected_by_username": current_admin.username,
                "rejected_at": now_utc.isoformat(),
                "rejection_reason": review_in.review_notes,
                "request_reason": correction.reason
            })
        )
        db.add(log)
        db.commit()

    return format_correction_out(correction)
