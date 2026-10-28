import datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class SubstituteAuthorization(Base):
    __tablename__ = "substitute_authorizations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timetable_entry_id = Column(Integer, ForeignKey("timetable_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    original_teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    substitute_teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)  # The specific date of substitution
    reason = Column(String(500), nullable=True)
    authorized_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # admin
    status = Column(String(20), default="authorized", nullable=False)  # 'authorized', 'used', 'cancelled'
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    # Prevent duplicate authorization for the same slot on the same date
    __table_args__ = (
        UniqueConstraint("timetable_entry_id", "date", name="uq_substitute_slot_date"),
    )

    # Relationships
    timetable_entry = relationship("TimetableEntry", back_populates="substitute_authorizations")
    original_teacher = relationship("User", foreign_keys=[original_teacher_id], backref="substituted_from")
    substitute_teacher = relationship("User", foreign_keys=[substitute_teacher_id], backref="substituted_to")
    authorized_by_user = relationship("User", foreign_keys=[authorized_by])
