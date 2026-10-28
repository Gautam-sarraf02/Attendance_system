import datetime as dt
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class SessionCreate(BaseModel):
    subject: str
    section: str
    timetable_entry_id: Optional[int] = None
    semester_id: Optional[int] = None
    face_image: Optional[str] = None  # Base64 camera frame for teacher verification


class AuthorizedSessionStartRequest(BaseModel):
    timetable_entry_id: Optional[int] = None
    subject: Optional[str] = None
    section: Optional[str] = None
    face_image: str  # Base64 captured face from live camera
    client_timestamp: Optional[str] = None  # Informational, server clock is authoritative


class SessionCloseRequest(BaseModel):
    reason: Optional[str] = None
    require_review: bool = False
    notes: Optional[str] = None


class SessionFinalizeRequest(BaseModel):
    camera_failed: bool = False
    technical_issue: bool = False
    reason: Optional[str] = None
    notes: Optional[str] = None


class SessionFinalizeOut(BaseModel):
    session_id: int
    status: str
    present_count: int
    absent_count: int
    total_eligible_students: int
    review_required: bool
    review_reason: Optional[str] = None
    finalized_at: dt.datetime
    message: str


class TeacherSlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timetable_entry_id: int
    subject_id: int
    subject_code: str
    subject_name: str
    semester_id: int
    semester_name: str
    academic_year_id: int
    academic_year_name: str
    section: str
    day_of_week: int
    day_name: str
    period_number: int
    start_time: str
    end_time: str
    is_substitute: bool = False
    original_teacher_name: Optional[str] = None
    can_start_now: bool = True
    time_status: str = "open"  # 'open', 'upcoming', 'passed'


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    section: str
    started_at: dt.datetime
    ended_at: Optional[dt.datetime] = None
    created_by: Optional[int] = None
    status: str  # 'scheduled', 'active', 'closed', 'review-required', 'completed'
    total_present: int = 0

    # Extended links & verification details
    teacher_id: Optional[int] = None
    teacher_name: Optional[str] = None
    timetable_entry_id: Optional[int] = None
    semester_id: Optional[int] = None
    subject_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    recognition_window_end: Optional[dt.datetime] = None
    review_reason: Optional[str] = None
    is_deadline_passed: Optional[bool] = None
    remaining_deadline_seconds: Optional[int] = None
