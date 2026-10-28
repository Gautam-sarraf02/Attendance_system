import datetime
from sqlalchemy import Column, Integer, String, Date, Time, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    subject = Column(String(100), nullable=False, index=True)
    date = Column(Date, default=lambda: datetime.date.today(), nullable=False, index=True)
    time = Column(Time, default=lambda: datetime.datetime.now().time(), nullable=False)
    status = Column(String(50), default="present", nullable=False)  # 'present', 'absent', 'late'
    confidence_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    # Unique constraint per student per session to prevent duplicates
    __table_args__ = (
        UniqueConstraint("student_id", "session_id", name="uq_student_session"),
    )

    student = relationship("Student", back_populates="attendance_records")
    session = relationship("AttendanceSession", back_populates="attendance_records")
