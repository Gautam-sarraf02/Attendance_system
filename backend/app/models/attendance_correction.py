import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class AttendanceCorrection(Base):
    __tablename__ = "attendance_corrections"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    attendance_id = Column(Integer, ForeignKey("attendance.id", ondelete="SET NULL"), nullable=True, index=True)

    requested_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_status = Column(String(20), default="present", nullable=False)  # 'present', 'absent', 'late'
    previous_status = Column(String(20), nullable=True)  # Status before correction (e.g. 'absent' or None)
    reason = Column(Text, nullable=False)  # Justification / exception details
    evidence_notes = Column(Text, nullable=True)  # References, doctor's note, camera glitch notes

    status = Column(String(20), default="pending", nullable=False, index=True)  # 'pending', 'approved', 'rejected'
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)  # Reason for approval/rejection

    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    # Relationships
    session = relationship("AttendanceSession", backref="corrections")
    student = relationship("Student", backref="attendance_corrections")
    attendance = relationship("Attendance", backref="corrections")
    requester = relationship("User", foreign_keys=[requested_by], backref="requested_corrections")
    reviewer = relationship("User", foreign_keys=[reviewed_by], backref="reviewed_corrections")
