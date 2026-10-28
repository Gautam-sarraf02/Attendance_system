import datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class FaceEnrollment(Base):
    __tablename__ = "face_enrollments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Exactly one of user_id or student_id must be set.
    # user_id is for teachers; student_id is for students.
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True)

    academic_year_id = Column(Integer, ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True)
    enrolled_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
    valid_from = Column(Date, nullable=False)
    valid_until = Column(Date, nullable=False)
    status = Column(String(20), default="active", nullable=False)  # 'active', 'expired', 'renewed', 'revoked'
    enrolled_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # admin who enrolled
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    # One active enrollment per person per academic year
    __table_args__ = (
        UniqueConstraint("user_id", "academic_year_id", name="uq_user_enrollment_year"),
        UniqueConstraint("student_id", "academic_year_id", name="uq_student_enrollment_year"),
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="face_enrollments")
    student = relationship("Student", foreign_keys=[student_id], backref="face_enrollments")
    academic_year = relationship("AcademicYear", back_populates="face_enrollments")
    enrolled_by_user = relationship("User", foreign_keys=[enrolled_by])
    face_samples = relationship("FaceSample", back_populates="enrollment", cascade="all, delete-orphan")
