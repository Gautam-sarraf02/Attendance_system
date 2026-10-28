import datetime
from sqlalchemy import Column, Integer, String, Date, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Semester(Base):
    __tablename__ = "semesters"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), nullable=False)  # e.g. "Semester 5"
    academic_year_id = Column(Integer, ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    # Relationships
    academic_year = relationship("AcademicYear", back_populates="semesters")
    subjects = relationship("Subject", back_populates="semester", cascade="all, delete-orphan")
    timetable_entries = relationship("TimetableEntry", back_populates="semester", cascade="all, delete-orphan")
