from datetime import datetime
from typing import Optional, Literal, List
from pydantic import BaseModel, ConfigDict, Field


class AttendanceCorrectionCreate(BaseModel):
    session_id: int
    student_id: int
    attendance_id: Optional[int] = None
    requested_status: Literal["present", "absent", "late"] = "present"
    reason: str = Field(..., min_length=5, description="Required justification for the correction")
    evidence_notes: Optional[str] = None


class AttendanceCorrectionReview(BaseModel):
    decision: Literal["approved", "rejected", "approve", "reject"]
    review_notes: str = Field(..., min_length=3, description="Reviewer justification for decision")


class AttendanceCorrectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    student_id: int
    attendance_id: Optional[int] = None

    requested_by: int
    requested_status: str
    previous_status: Optional[str] = None
    reason: str
    evidence_notes: Optional[str] = None

    status: str  # 'pending', 'approved', 'rejected'
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    # Informational display names
    student_name: Optional[str] = None
    roll_number: Optional[str] = None
    section: Optional[str] = None
    subject: Optional[str] = None
    requester_name: Optional[str] = None
    reviewer_name: Optional[str] = None


class AttendanceCorrectionListResponse(BaseModel):
    total: int
    corrections: List[AttendanceCorrectionOut]
