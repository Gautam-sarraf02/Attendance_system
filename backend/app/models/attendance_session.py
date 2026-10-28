import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subject = Column(String(100), nullable=False, index=True)
    section = Column(String(50), nullable=False, index=True)
    started_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
    ended_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(50), default="active", nullable=False)  # 'active' or 'completed'

    # Phase 1 & 5 additions: timetable, academic year, subject integration & recognition window
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    timetable_entry_id = Column(Integer, ForeignKey("timetable_entries.id", ondelete="SET NULL"), nullable=True, index=True)
    semester_id = Column(Integer, ForeignKey("semesters.id", ondelete="SET NULL"), nullable=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True)
    academic_year_id = Column(Integer, ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True, index=True)
    recognition_window_end = Column(DateTime, nullable=True)  # started_at + 15min; deadline for attendance
    review_reason = Column(String(255), nullable=True)

    # Relationships
    attendance_records = relationship("Attendance", back_populates="session", cascade="all, delete-orphan")
    teacher = relationship("User", foreign_keys=[teacher_id], backref="taught_sessions")
    created_by_user = relationship("User", foreign_keys=[created_by], backref="created_sessions")
    timetable_entry = relationship("TimetableEntry", backref="sessions")
    semester = relationship("Semester", backref="attendance_sessions")
    subject_ref = relationship("Subject", foreign_keys=[subject_id], backref="attendance_sessions")
    academic_year = relationship("AcademicYear", foreign_keys=[academic_year_id], backref="attendance_sessions")

