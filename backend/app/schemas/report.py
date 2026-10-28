from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class StudentAttendanceStats(BaseModel):
    student_id: int
    roll_number: str
    name: str
    section: str
    email: Optional[str] = None
    total_lectures: int
    present_count: int
    percentage: float

class SubjectAttendanceStats(BaseModel):
    subject: str
    section: str
    total_sessions: int
    total_attendances_marked: int
    average_attendance_per_session: float

class DailyAttendanceStats(BaseModel):
    date: str
    total_present: int
    total_sessions: int
    subjects_covered: List[str]

class MonthlyTrendStats(BaseModel):
    month: str
    total_present: int
    total_sessions: int

class SemesterAttendanceStats(BaseModel):
    semester_id: Optional[int] = None
    semester_name: str
    academic_year_name: Optional[str] = None
    total_sessions: int
    total_records: int
    present_count: int
    absent_count: int
    average_attendance_rate: float

class SectionAttendanceStats(BaseModel):
    section: str
    total_students: int
    total_sessions: int
    present_count: int
    absent_count: int
    attendance_percentage: float

class ComprehensiveReportOut(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    overall: Dict[str, Any]
    date_wise: List[DailyAttendanceStats]
    subject_wise: List[SubjectAttendanceStats]
    semester_wise: List[SemesterAttendanceStats]
    section_wise: List[SectionAttendanceStats]

class DashboardStatsOut(BaseModel):
    total_students: int
    present_today: int
    total_attendance_records: int
    total_sessions: int
    active_session: Optional[Dict[str, Any]] = None
    subjects_count: int
    model_trained: bool
    model_samples: int
    recent_activity: List[Dict[str, Any]]
    subject_distribution: List[Dict[str, Any]]
    daily_trends: List[Dict[str, Any]]


class StudentPunchRecord(BaseModel):
    id: int
    date: str
    period: str
    period_number: Optional[int] = None
    lecture_title: Optional[str] = None
    subject: str
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    teacher_name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    punch_time: str
    time: Optional[str] = None
    status: str
    confidence_score: Optional[float] = None
    session_id: Optional[int] = None
    session_status: Optional[str] = None
    session_finalized: bool = True
    is_finalized: Optional[bool] = None
    correction_status: Optional[str] = None
    correction_id: Optional[int] = None


class DailyPunchLecture(BaseModel):
    period_number: Optional[int] = None
    period_label: str
    subject_code: str
    subject_name: str
    teacher_name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    punch_time: str
    status: str
    confidence_score: Optional[float] = None
    attendance_id: Optional[int] = None
    session_id: Optional[int] = None
    session_status: Optional[str] = None
    is_finalized: bool = True
    correction_status: Optional[str] = None
    correction_id: Optional[int] = None


class DailyPunchRecord(BaseModel):
    date: str
    day_number: str
    day_name: str
    month_name: str
    year: int
    month_key: str
    total_lectures: int
    attended_count: int
    absent_count: int
    in_progress_count: int = 0
    under_review_count: int = 0
    status_type: str
    status_label: str
    timetable_info: Optional[str] = None
    lectures: List[DailyPunchLecture]


class MonthlyPunchGroup(BaseModel):
    month_title: str
    total_lectures: int
    attended_lectures: int
    absent_lectures: int
    percentage: float
    summary_text: str
    dates: List[DailyPunchRecord]


class StudentSubjectStat(BaseModel):
    subject: str
    subject_code: Optional[str] = None
    total_classes: int
    present_count: int
    absent_count: int
    percentage: float
    is_eligible: bool = True


class StudentMonthlyStat(BaseModel):
    month: str
    total_classes: int
    present_count: int
    absent_count: int
    percentage: float


class StudentRegistrationValidity(BaseModel):
    enrollment_status: str
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    days_remaining: Optional[int] = None
    is_valid: bool = False
    academic_year_name: Optional[str] = None


class StudentProfile(BaseModel):
    id: int
    name: str
    roll_number: str
    section: str
    email: Optional[str] = None


class StudentDashboardStats(BaseModel):
    total_lectures: int
    total_classes: Optional[int] = None
    present_count: int
    total_present: Optional[int] = None
    absent_count: int
    total_absent: Optional[int] = None
    overall_percentage: float
    standing: str
    standing_status: Optional[str] = None
    min_attendance_met: bool
    is_eligible_for_exams: Optional[bool] = None


class StudentDashboardOut(BaseModel):
    student: StudentProfile
    profile: Optional[StudentProfile] = None
    validity: StudentRegistrationValidity
    stats: StudentDashboardStats
    subject_wise: List[StudentSubjectStat]
    subject_stats: Optional[List[StudentSubjectStat]] = None
    monthly_summaries: List[StudentMonthlyStat]
    monthly_stats: Optional[List[StudentMonthlyStat]] = None
    punch_history: List[StudentPunchRecord]
    daily_punch_records: Optional[List[DailyPunchRecord]] = None
    monthly_punch_groups: Optional[List[MonthlyPunchGroup]] = None

