import json
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.face_enrollment import FaceEnrollment
from app.models.face_sample import FaceSample
from app.models.substitute_auth import SubstituteAuthorization
from app.models.audit_log import AuditLog
from app.models.academic_year import AcademicYear
from app.models.timetable import TimetableEntry
from app.models.student import Student
from app.models.user import User
from app.schemas.enrollment import (
    FaceEnrollmentCreate, FaceEnrollmentUpdate, FaceEnrollmentOut,
    FaceEnrollmentDetailOut, FaceEnrollmentRegisterRequest, EnrollmentRenewRequest,
    SubstituteAuthCreate, SubstituteAuthUpdate, SubstituteAuthOut,
    AuditLogOut
)
from app.auth.deps import get_current_user, get_current_admin
from app.face.detector import detector
from app.face.storage import storage

router = APIRouter(tags=["Enrollment & Authorizations"])


def _format_enrollment_detail(e: FaceEnrollment, db: Session) -> FaceEnrollmentDetailOut:
    today = date.today()
    # Auto-expire if past valid_until
    if e.status == "active" and e.valid_until < today:
        e.status = "expired"
        db.commit()

    person_name = None
    identifier = None
    person_type = "student"

    if e.student_id:
        if e.student:
            person_name = e.student.name
            identifier = e.student.roll_number
        person_type = "student"
    elif e.user_id:
        if e.user:
            person_name = e.user.full_name or e.user.username
            identifier = e.user.username
        person_type = "teacher"

    ay_name = e.academic_year.name if e.academic_year else None
    samples_count = len(e.face_samples)
    is_valid_today = (e.status == "active" and e.valid_from <= today <= e.valid_until)

    return FaceEnrollmentDetailOut(
        id=e.id,
        user_id=e.user_id,
        student_id=e.student_id,
        academic_year_id=e.academic_year_id,
        enrolled_at=e.enrolled_at,
        valid_from=e.valid_from,
        valid_until=e.valid_until,
        status=e.status,
        enrolled_by=e.enrolled_by,
        notes=e.notes,
        created_at=e.created_at,
        person_name=person_name,
        identifier=identifier,
        academic_year_name=ay_name,
        samples_count=samples_count,
        is_valid_today=is_valid_today,
        person_type=person_type
    )


# ─── Face Enrollments ────────────────────────────────────────────────────────

@router.get("/enrollments", response_model=List[FaceEnrollmentDetailOut])
def list_face_enrollments(
    academic_year_id: Optional[int] = None,
    student_id: Optional[int] = None,
    user_id: Optional[int] = None,
    status_val: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List face enrollments:
    - Admin & Teacher can inspect enrollments.
    - Students can ONLY view their own enrollment records.
    """
    query = db.query(FaceEnrollment)

    if current_user.role == "student":
        # Strict isolation: students only see their own enrollments
        query = query.filter(FaceEnrollment.student_id == current_user.student_id)
    else:
        if student_id:
            query = query.filter(FaceEnrollment.student_id == student_id)
        if user_id:
            query = query.filter(FaceEnrollment.user_id == user_id)

    if academic_year_id:
        query = query.filter(FaceEnrollment.academic_year_id == academic_year_id)
    if status_val:
        query = query.filter(FaceEnrollment.status == status_val)

    enrollments = query.order_by(FaceEnrollment.created_at.desc()).all()
    return [_format_enrollment_detail(e, db) for e in enrollments]


@router.post("/enrollments", response_model=FaceEnrollmentDetailOut, status_code=status.HTTP_201_CREATED)
def create_face_enrollment(
    enroll_in: FaceEnrollmentCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can create face enrollment records."""
    # 1. Validate Academic Year
    year = db.query(AcademicYear).filter(AcademicYear.id == enroll_in.academic_year_id).first()
    if not year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found.")

    if not enroll_in.student_id and not enroll_in.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either student_id or user_id must be provided for enrollment."
        )

    if enroll_in.student_id and enroll_in.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot enroll both student and teacher in the same record. Select one."
        )

    # 2. Check duplicate enrollment for this academic year
    if enroll_in.student_id:
        existing = db.query(FaceEnrollment).filter(
            FaceEnrollment.student_id == enroll_in.student_id,
            FaceEnrollment.academic_year_id == enroll_in.academic_year_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A face enrollment already exists for this student in academic year '{year.name}'."
            )
    if enroll_in.user_id:
        existing = db.query(FaceEnrollment).filter(
            FaceEnrollment.user_id == enroll_in.user_id,
            FaceEnrollment.academic_year_id == enroll_in.academic_year_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A face enrollment already exists for this teacher in academic year '{year.name}'."
            )

    # 3. Enforce 1 academic year validity
    valid_from = enroll_in.valid_from or year.start_date
    valid_until = enroll_in.valid_until or year.end_date

    if valid_until <= valid_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enrollment valid_until date must be after valid_from date."
        )

    duration_days = (valid_until - valid_from).days
    if duration_days > 366:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Enrollment validity period cannot exceed one academic year (366 days). Specified duration: {duration_days} days."
        )

    enrollment = FaceEnrollment(
        user_id=enroll_in.user_id,
        student_id=enroll_in.student_id,
        academic_year_id=enroll_in.academic_year_id,
        valid_from=valid_from,
        valid_until=valid_until,
        status="active",
        enrolled_by=current_admin.id,
        notes=enroll_in.notes
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return _format_enrollment_detail(enrollment, db)


@router.post("/enrollments/register", status_code=status.HTTP_201_CREATED)
def register_face_enrollment_camera(
    payload: FaceEnrollmentRegisterRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """
    Biometric Face Registration (Camera / Upload):
    - Validates image quality (dimensions, single face, blur, lighting).
    - Stores protected face templates with 0o600 permissions.
    - Associates enrollment with the correct user and academic year.
    - Enforces 1 academic year validity and prevents duplicate active enrollments.
    """
    # 1. Validate Academic Year
    year = db.query(AcademicYear).filter(AcademicYear.id == payload.academic_year_id).first()
    if not year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found.")

    if not payload.images or len(payload.images) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 1 face capture image is required for biometric enrollment (3+ recommended)."
        )

    # 2. Validate person
    student = None
    teacher = None
    entity_id = None
    is_user = False

    if payload.person_type == "student":
        if not payload.student_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="student_id is required.")
        student = db.query(Student).filter(Student.id == payload.student_id).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
        entity_id = student.id
        is_user = False

        # Duplicate check
        existing = db.query(FaceEnrollment).filter(
            FaceEnrollment.student_id == student.id,
            FaceEnrollment.academic_year_id == year.id
        ).first()
        if existing and not payload.re_enroll:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An active enrollment already exists for {student.name} in academic year '{year.name}'. Please renew or update it."
            )
    elif payload.person_type in ("teacher", "faculty", "user"):
        if not payload.user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required for teacher enrollment.")
        teacher = db.query(User).filter(User.id == payload.user_id).first()
        if not teacher:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher user not found.")
        entity_id = teacher.id
        is_user = True

        # Duplicate check
        existing = db.query(FaceEnrollment).filter(
            FaceEnrollment.user_id == teacher.id,
            FaceEnrollment.academic_year_id == year.id
        ).first()
        if existing and not payload.re_enroll:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An active enrollment already exists for {teacher.full_name or teacher.username} in academic year '{year.name}'. Please renew or update it."
            )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid person_type '{payload.person_type}'.")

    # 3. Create or reuse FaceEnrollment record with 1-academic-year validity
    if existing and payload.re_enroll:
        enrollment = existing
        enrollment.status = "active"
        enrollment.valid_from = year.start_date
        enrollment.valid_until = year.end_date
        enrollment.enrolled_by = current_admin.id
        if payload.notes:
            enrollment.notes = payload.notes
        # Clean up existing samples for fresh re-enrollment
        db.query(FaceSample).filter(FaceSample.enrollment_id == enrollment.id).delete()
        storage.delete_entity_samples(entity_id, is_user=is_user)
        db.commit()
        db.refresh(enrollment)
    else:
        enrollment = FaceEnrollment(
            user_id=teacher.id if is_user else None,
            student_id=student.id if not is_user else None,
            academic_year_id=year.id,
            valid_from=year.start_date,
            valid_until=year.end_date,
            status="active",
            enrolled_by=current_admin.id,
            notes=payload.notes
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)

    # 4. Process images, validate biometric quality, and save protected templates
    saved_count = 0
    errors = []
    quality_reports = []

    current_samples_count = storage.count_entity_samples(entity_id, is_user=is_user)

    for idx, b64_str in enumerate(payload.images, start=1):
        try:
            cv_img = detector.decode_image_base64(b64_str)
            norm_face, metrics = detector.validate_enrollment_quality(cv_img)
            quality_reports.append(metrics)

            sample_idx = current_samples_count + idx
            file_path, file_name = storage.save_face_sample(
                entity_id=entity_id,
                face_image=norm_face,
                sample_index=sample_idx,
                is_user=is_user
            )

            face_sample = FaceSample(
                student_id=student.id if not is_user else None,
                user_id=teacher.id if is_user else None,
                enrollment_id=enrollment.id,
                image_path=file_path,
                file_name=file_name
            )
            db.add(face_sample)
            saved_count += 1
        except Exception as e:
            errors.append(f"Sample {idx}: {str(e)}")

    if saved_count > 0:
        db.commit()
    else:
        # Roll back enrollment if zero samples passed validation
        db.delete(enrollment)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Biometric quality validation failed for all images: {'; '.join(errors)}"
        )

    person_display = student.name if student else (teacher.full_name or teacher.username)
    return {
        "success": True,
        "message": f"Successfully enrolled face for {person_display} in academic year {year.name}.",
        "samples_saved": saved_count,
        "total_samples": current_samples_count + saved_count,
        "quality_metrics": quality_reports,
        "warnings": errors if errors else None,
        "enrollment": _format_enrollment_detail(enrollment, db)
    }


@router.post("/enrollments/{enrollment_id}/renew", response_model=FaceEnrollmentDetailOut)
def renew_face_enrollment(
    enrollment_id: int,
    renew_in: EnrollmentRenewRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """
    Renews face enrollment for a subsequent academic year.
    Marks old enrollment as 'renewed' and creates new 'active' enrollment.
    """
    old_enrollment = db.query(FaceEnrollment).filter(FaceEnrollment.id == enrollment_id).first()
    if not old_enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment record not found.")

    new_year = db.query(AcademicYear).filter(AcademicYear.id == renew_in.academic_year_id).first()
    if not new_year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target academic year not found.")

    # Prevent duplicate active enrollment in target year
    if old_enrollment.student_id:
        existing = db.query(FaceEnrollment).filter(
            FaceEnrollment.student_id == old_enrollment.student_id,
            FaceEnrollment.academic_year_id == new_year.id,
            FaceEnrollment.status == "active"
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An active enrollment already exists for this student in academic year '{new_year.name}'."
            )
    elif old_enrollment.user_id:
        existing = db.query(FaceEnrollment).filter(
            FaceEnrollment.user_id == old_enrollment.user_id,
            FaceEnrollment.academic_year_id == new_year.id,
            FaceEnrollment.status == "active"
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An active enrollment already exists for this teacher in academic year '{new_year.name}'."
            )

    valid_from = renew_in.valid_from or new_year.start_date
    valid_until = renew_in.valid_until or new_year.end_date

    # Mark old enrollment as renewed
    old_enrollment.status = "renewed"

    # Create new active enrollment
    new_enrollment = FaceEnrollment(
        user_id=old_enrollment.user_id,
        student_id=old_enrollment.student_id,
        academic_year_id=new_year.id,
        valid_from=valid_from,
        valid_until=valid_until,
        status="active",
        enrolled_by=current_admin.id,
        notes=renew_in.notes or f"Renewed from enrollment #{old_enrollment.id}"
    )
    db.add(new_enrollment)
    db.commit()
    db.refresh(new_enrollment)

    # Link existing face samples to the new enrollment as well
    for sample in old_enrollment.face_samples:
        sample.enrollment_id = new_enrollment.id
    db.commit()

    return _format_enrollment_detail(new_enrollment, db)


@router.post("/enrollments/{enrollment_id}/revoke", response_model=FaceEnrollmentDetailOut)
def revoke_face_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can revoke face enrollments (e.g. withdrawal or disciplinary)."""
    enrollment = db.query(FaceEnrollment).filter(FaceEnrollment.id == enrollment_id).first()
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment record not found.")

    enrollment.status = "revoked"
    db.commit()
    db.refresh(enrollment)
    return _format_enrollment_detail(enrollment, db)


@router.put("/enrollments/{enrollment_id}", response_model=FaceEnrollmentDetailOut)
def update_face_enrollment(
    enrollment_id: int,
    enroll_in: FaceEnrollmentUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can update face enrollment status or validity."""
    enrollment = db.query(FaceEnrollment).filter(FaceEnrollment.id == enrollment_id).first()
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment record not found.")

    if enroll_in.valid_from is not None:
        enrollment.valid_from = enroll_in.valid_from
    if enroll_in.valid_until is not None:
        enrollment.valid_until = enroll_in.valid_until
    if enroll_in.status is not None:
        enrollment.status = enroll_in.status
    if enroll_in.notes is not None:
        enrollment.notes = enroll_in.notes

    db.commit()
    db.refresh(enrollment)
    return _format_enrollment_detail(enrollment, db)


@router.delete("/enrollments/{enrollment_id}")
def delete_face_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can delete face enrollments."""
    enrollment = db.query(FaceEnrollment).filter(FaceEnrollment.id == enrollment_id).first()
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment record not found.")

    # Securely delete biometric template files
    if enrollment.student_id:
        storage.delete_entity_samples(enrollment.student_id, is_user=False)
    elif enrollment.user_id:
        storage.delete_entity_samples(enrollment.user_id, is_user=True)

    db.delete(enrollment)
    db.commit()
    return {"success": True, "message": "Face enrollment and associated biometric templates deleted successfully."}


# ─── Substitute Teacher Authorizations ───────────────────────────────────────

@router.get("/substitutes", response_model=List[SubstituteAuthOut])
def list_substitute_authorizations(
    date_val: Optional[date] = Query(None, alias="date"),
    status_val: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List substitute teacher authorizations."""
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted: Students cannot access teacher substitutions."
        )

    query = db.query(SubstituteAuthorization)

    if current_user.role in ("teacher", "faculty"):
        query = query.filter(
            or_(
                SubstituteAuthorization.original_teacher_id == current_user.id,
                SubstituteAuthorization.substitute_teacher_id == current_user.id
            )
        )

    if date_val:
        query = query.filter(SubstituteAuthorization.date == date_val)
    if status_val:
        query = query.filter(SubstituteAuthorization.status == status_val)

    return query.order_by(SubstituteAuthorization.date.desc()).all()


@router.post("/substitutes", response_model=SubstituteAuthOut, status_code=status.HTTP_201_CREATED)
def create_substitute_authorization(
    sub_in: SubstituteAuthCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can authorize substitute teachers."""
    entry = db.query(TimetableEntry).filter(TimetableEntry.id == sub_in.timetable_entry_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timetable slot entry not found.")

    orig = db.query(User).filter(User.id == sub_in.original_teacher_id).first()
    if not orig:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original teacher user not found.")

    sub = db.query(User).filter(User.id == sub_in.substitute_teacher_id).first()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Substitute teacher user not found.")

    # Prevent duplicate authorization for same slot and date
    existing = db.query(SubstituteAuthorization).filter(
        SubstituteAuthorization.timetable_entry_id == sub_in.timetable_entry_id,
        SubstituteAuthorization.date == sub_in.date
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Substitute authorization already exists for timetable slot on {sub_in.date}."
        )

    auth_record = SubstituteAuthorization(
        timetable_entry_id=sub_in.timetable_entry_id,
        original_teacher_id=sub_in.original_teacher_id,
        substitute_teacher_id=sub_in.substitute_teacher_id,
        date=sub_in.date,
        reason=sub_in.reason,
        authorized_by=current_admin.id,
        status="authorized"
    )
    db.add(auth_record)
    db.commit()
    db.refresh(auth_record)

    # Maintain complete audit trail (Requirement 5)
    audit = AuditLog(
        user_id=current_admin.id,
        action="AUTHORIZE_SUBSTITUTE_TEACHER",
        entity_type="substitute_authorization",
        entity_id=auth_record.id,
        details=json.dumps({
            "original_teacher_id": orig.id,
            "original_teacher_name": orig.full_name or orig.username,
            "substitute_teacher_id": sub.id,
            "substitute_teacher_name": sub.full_name or sub.username,
            "timetable_entry_id": entry.id,
            "subject": entry.subject.name if entry.subject else None,
            "section": entry.section,
            "date": str(sub_in.date),
            "reason": sub_in.reason
        }),
        created_at=datetime.now(timezone.utc)
    )
    db.add(audit)
    db.commit()

    return auth_record


@router.put("/substitutes/{sub_id}", response_model=SubstituteAuthOut)
def update_substitute_authorization(
    sub_id: int,
    sub_in: SubstituteAuthUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    auth_record = db.query(SubstituteAuthorization).filter(SubstituteAuthorization.id == sub_id).first()
    if not auth_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Substitute authorization not found.")

    if sub_in.status is not None:
        auth_record.status = sub_in.status
    if sub_in.reason is not None:
        auth_record.reason = sub_in.reason

    db.commit()
    db.refresh(auth_record)

    audit = AuditLog(
        user_id=current_admin.id,
        action="UPDATE_SUBSTITUTE_AUTHORIZATION",
        entity_type="substitute_authorization",
        entity_id=auth_record.id,
        details=json.dumps({
            "status": auth_record.status,
            "reason": auth_record.reason
        }),
        created_at=datetime.now(timezone.utc)
    )
    db.add(audit)
    db.commit()

    return auth_record


@router.delete("/substitutes/{sub_id}")
def delete_substitute_authorization(
    sub_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    auth_record = db.query(SubstituteAuthorization).filter(SubstituteAuthorization.id == sub_id).first()
    if not auth_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Substitute authorization not found.")

    auth_id = auth_record.id
    tt_id = auth_record.timetable_entry_id
    auth_date = str(auth_record.date)

    db.delete(auth_record)
    audit = AuditLog(
        user_id=current_admin.id,
        action="REVOKE_SUBSTITUTE_AUTHORIZATION",
        entity_type="substitute_authorization",
        entity_id=auth_id,
        details=json.dumps({
            "timetable_entry_id": tt_id,
            "date": auth_date
        }),
        created_at=datetime.now(timezone.utc)
    )
    db.add(audit)
    db.commit()

    return {"success": True, "message": "Substitute authorization deleted successfully."}


# ─── Audit Logs ─────────────────────────────────────────────────────────────

@router.get("/audit-logs", response_model=List[AuditLogOut])
def list_audit_logs(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    query = db.query(AuditLog)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))

    return query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()
