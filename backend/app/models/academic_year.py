import datetime
from sqlalchemy import Column, Integer, String, Date, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class AcademicYear(Base):
    __tablename__ = "academic_years"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)  # e.g. "2026-2027"
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_current = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    # Relationships
    semesters = relationship("Semester", back_populates="academic_year", cascade="all, delete-orphan")
    face_enrollments = relationship("FaceEnrollment", back_populates="academic_year", cascade="all, delete-orphan")
