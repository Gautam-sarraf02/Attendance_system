import datetime
from sqlalchemy import Column, Integer, String, Time, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class TimetableEntry(Base):
    __tablename__ = "timetable_entries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    section = Column(String(50), nullable=False, index=True)  # e.g. "CSE-A"
    semester_id = Column(Integer, ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    period_number = Column(Integer, nullable=False)  # 1, 2, 3, ...
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    # Prevent duplicate slots: same section, same day, same period, same semester
    __table_args__ = (
        UniqueConstraint("section", "semester_id", "day_of_week", "period_number",
                         name="uq_timetable_slot"),
    )

    # Relationships
    subject = relationship("Subject", back_populates="timetable_entries")
    teacher = relationship("User", foreign_keys=[teacher_id], backref="timetable_entries")
    semester = relationship("Semester", back_populates="timetable_entries")
    substitute_authorizations = relationship("SubstituteAuthorization", back_populates="timetable_entry", cascade="all, delete-orphan")


def normalize_section(sec: str | None) -> str:
    """Normalizes section strings by removing department/section prefixes (CSE-A -> A)."""
    if not sec:
        return ""
    s = sec.strip().upper()
    for prefix in ("CSE-", "SECTION-", "SECTION ", "SEC-", "IT-", "ECE-"):
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
    return s


def get_section_variants(sec: str | None) -> list[str]:
    """Returns all plausible section aliases for querying (e.g. ['A', 'CSE-A'])."""
    if not sec:
        return []
    raw = sec.strip().upper()
    clean = normalize_section(raw)
    variants = [raw]
    if clean and clean not in variants:
        variants.append(clean)
    if clean and f"CSE-{clean}" not in variants:
        variants.append(f"CSE-{clean}")
    return variants
