import datetime as dt
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class AttendanceSimple(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    session_id: Optional[int] = None
    subject: str
    date: dt.date
    time: dt.time
    status: str
    confidence_score: Optional[float] = None
    created_at: dt.datetime

class AttendanceDetail(BaseModel):
    id: int
    student_id: int
    roll_number: str
    student_name: str
    section: str
    subject: str
    date: str
    time: str
    status: str
    confidence_score: Optional[float] = None
    session_id: Optional[int] = None

class AttendanceHistoryResponse(BaseModel):
    total: int
    records: List[AttendanceDetail]

class ManualAttendanceCreate(BaseModel):
    student_id: int
    subject: str
    session_id: Optional[int] = None
    status: str = "present"
    date: Optional[dt.date] = None
