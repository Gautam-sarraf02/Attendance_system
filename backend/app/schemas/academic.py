import datetime as dt
from datetime import date, time, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, field_validator


# ─── Academic Year ───────────────────────────────────────────────

class AcademicYearCreate(BaseModel):
    name: str  # e.g. "2026-2027"
    start_date: date
    end_date: date
    is_current: bool = False

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v, info):
        if "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class AcademicYearUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None


class AcademicYearOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_date: date
    end_date: date
    is_current: bool
    created_at: datetime


# ─── Semester ────────────────────────────────────────────────────

class SemesterCreate(BaseModel):
    name: str  # e.g. "Semester 5"
    academic_year_id: int
    start_date: date
    end_date: date
    is_active: bool = True


class SemesterUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None


class SemesterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    academic_year_id: int
    start_date: date
    end_date: date
    is_active: bool
    created_at: datetime


# ─── Subject ─────────────────────────────────────────────────────

class SubjectCreate(BaseModel):
    code: str  # e.g. "CS501"
    name: str  # e.g. "Computer Vision"
    semester_id: int
    section: str  # e.g. "CSE-A"
    is_active: bool = True


class SubjectUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    section: Optional[str] = None
    is_active: Optional[bool] = None


class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    semester_id: int
    section: str
    is_active: bool
    created_at: datetime


# ─── Timetable Entry ────────────────────────────────────────────

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class TimetableEntryCreate(BaseModel):
    subject_id: int
    teacher_id: int
    section: str
    semester_id: int
    day_of_week: int  # 0=Monday … 6=Sunday
    period_number: int  # 1, 2, 3, …
    start_time: time
    end_time: time

    @field_validator("day_of_week")
    @classmethod
    def valid_day(cls, v):
        if v < 0 or v > 6:
            raise ValueError("day_of_week must be 0 (Monday) through 6 (Sunday)")
        return v

    @field_validator("period_number")
    @classmethod
    def positive_period(cls, v):
        if v < 1:
            raise ValueError("period_number must be ≥ 1")
        return v

    @field_validator("end_time")
    @classmethod
    def end_after_start_time(cls, v, info):
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("end_time must be after start_time")
        return v


class TimetableEntryUpdate(BaseModel):
    subject_id: Optional[int] = None
    teacher_id: Optional[int] = None
    section: Optional[str] = None
    day_of_week: Optional[int] = None
    period_number: Optional[int] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_active: Optional[bool] = None


class TimetableEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    teacher_id: Optional[int] = None
    section: str
    semester_id: int
    day_of_week: int
    period_number: int
    start_time: time
    end_time: time
    is_active: bool = True
    created_at: datetime

    @property
    def day_name(self) -> str:
        return DAY_NAMES[self.day_of_week] if 0 <= self.day_of_week <= 6 else "Unknown"


class TimetableEntryDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    teacher_id: Optional[int] = None
    teacher_name: Optional[str] = None
    teacher_username: Optional[str] = None
    section: str
    semester_id: int
    semester_name: Optional[str] = None
    academic_year_id: Optional[int] = None
    academic_year_name: Optional[str] = None
    day_of_week: int
    day_name: str
    period_number: int
    start_time: time
    end_time: time
    is_active: bool = True
    created_at: datetime


# ─── Timetable Import ───────────────────────────────────────────

class TimetableImportRowResolved(BaseModel):
    semester_id: int
    semester_name: str
    subject_id: int
    subject_code: str
    subject_name: str
    teacher_id: int
    teacher_name: str
    section: str
    day_of_week: int
    day_name: str
    period_number: int
    start_time: str
    end_time: str


class TimetableImportPreviewRow(BaseModel):
    row_index: int
    status: str  # "valid", "conflict", "error"
    errors: List[str] = []
    raw_data: Dict[str, Any] = {}
    resolved: Optional[TimetableImportRowResolved] = None


class TimetableImportPreviewResponse(BaseModel):
    total_rows: int
    valid_count: int
    conflict_count: int
    error_count: int
    rows: List[TimetableImportPreviewRow]


class TimetableImportCommitRequest(BaseModel):
    rows: List[TimetableImportRowResolved]
    replace_conflicts: bool = False


# ─── Holidays ───────────────────────────────────────────────────

class HolidayCreate(BaseModel):
    name: str
    date: dt.date
    academic_year_id: Optional[int] = None
    description: Optional[str] = None


class HolidayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    date: dt.date
    academic_year_id: Optional[int] = None
    description: Optional[str] = None
    created_at: datetime


# ─── Scheduled Class Lookup ─────────────────────────────────────

class ScheduledClassLookupEntry(BaseModel):
    id: int
    subject_id: int
    subject_name: str
    subject_code: str
    section: str
    semester_id: int
    semester_name: str
    day_of_week: int
    day_name: str
    period_number: int
    start_time: str
    end_time: str
    teacher_id: Optional[int] = None
    teacher_name: Optional[str] = None
    is_substituted: bool = False
    effective_teacher_id: Optional[int] = None
    effective_teacher_name: Optional[str] = None
    substitution_reason: Optional[str] = None


class ScheduledClassLookupResponse(BaseModel):
    date: Optional[str] = None
    day_of_week: int
    day_name: str
    is_holiday: bool = False
    holiday_name: Optional[str] = None
    is_outside_semester: bool = False
    status_message: Optional[str] = None
    total_entries: int
    entries: List[ScheduledClassLookupEntry]
