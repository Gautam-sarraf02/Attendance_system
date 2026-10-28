from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


# ─── Face Enrollment ─────────────────────────────────────────────

class FaceEnrollmentCreate(BaseModel):
    user_id: Optional[int] = None  # For teacher enrollments
    student_id: Optional[int] = None  # For student enrollments
    academic_year_id: int
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    notes: Optional[str] = None


class FaceEnrollmentUpdate(BaseModel):
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    status: Optional[str] = None  # 'active', 'expired', 'renewed', 'revoked'
    notes: Optional[str] = None


class FaceEnrollmentRegisterRequest(BaseModel):
    person_type: str = "student"  # 'student' or 'teacher'
    student_id: Optional[int] = None
    user_id: Optional[int] = None
    academic_year_id: int
    images: list[str]  # Base64 captured face images
    notes: Optional[str] = None
    re_enroll: Optional[bool] = False


class EnrollmentRenewRequest(BaseModel):
    academic_year_id: int
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    notes: Optional[str] = None


class FaceEnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    student_id: Optional[int] = None
    academic_year_id: int
    enrolled_at: datetime
    valid_from: date
    valid_until: date
    status: str
    enrolled_by: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime


class FaceEnrollmentDetailOut(FaceEnrollmentOut):
    person_name: Optional[str] = None
    identifier: Optional[str] = None
    academic_year_name: Optional[str] = None
    samples_count: int = 0
    is_valid_today: bool = False
    person_type: str = "student"



# ─── Substitute Authorization ───────────────────────────────────

class SubstituteAuthCreate(BaseModel):
    timetable_entry_id: int
    original_teacher_id: int
    substitute_teacher_id: int
    date: date
    reason: Optional[str] = None


class SubstituteAuthUpdate(BaseModel):
    status: Optional[str] = None  # 'authorized', 'used', 'cancelled'
    reason: Optional[str] = None


class SubstituteAuthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timetable_entry_id: int
    original_teacher_id: int
    substitute_teacher_id: int
    date: date
    reason: Optional[str] = None
    authorized_by: Optional[int] = None
    status: str
    created_at: datetime


# ─── Audit Log ───────────────────────────────────────────────────

class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogFilter(BaseModel):
    """Query parameters for filtering audit logs."""
    user_id: Optional[int] = None
    action: Optional[str] = None
    entity_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
