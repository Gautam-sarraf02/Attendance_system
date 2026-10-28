import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False, index=True)  # e.g. "CS501"
    name = Column(String(150), nullable=False)  # e.g. "Computer Vision"
    semester_id = Column(Integer, ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False, index=True)
    section = Column(String(50), nullable=False)  # e.g. "CSE-A"
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("code", "section", name="uq_subject_section"),
    )

    # Relationships
    semester = relationship("Semester", back_populates="subjects")
    timetable_entries = relationship("TimetableEntry", back_populates="subject", cascade="all, delete-orphan")
